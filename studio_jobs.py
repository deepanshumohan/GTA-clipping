"""Persistent single-worker queue. Each pipeline runs in a cancellable child process."""
import copy
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / 'skills/video-to-reels/scripts/reels.py'
TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


class JobManager:
    def __init__(self, root=ROOT / 'reels_output', start_worker=True):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs = {}
        self.processes = {}
        self.queue = queue.Queue()
        for path in self.root.glob('job-*/job.json'):
            try:
                job = json.loads(path.read_text(encoding='utf-8'))
                if job['status'] not in TERMINAL | {'review'}:
                    job.update(status='interrupted', error='Studio restarted; submit a new job.')
                self.jobs[job['id']] = job
                self._save(job)
            except (ValueError, KeyError, OSError):
                continue
        if start_worker:
            threading.Thread(target=self._worker, daemon=True).start()

    def _save(self, job):
        path = Path(job['directory']) / 'job.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(job, indent=2), encoding='utf-8')
        tmp.replace(path)

    def get(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError(job_id)
            return copy.deepcopy(self.jobs[job_id])

    def list(self):
        with self.lock:
            return [copy.deepcopy(j) for j in reversed(list(self.jobs.values()))]

    def submit(self, request):
        job_id = 'job-' + uuid.uuid4().hex
        directory = self.root / job_id
        directory.mkdir()
        job = dict(id=job_id, directory=str(directory), request=request,
                   status='queued', stage='Waiting', progress=0, logs=[], error=None,
                   created=time.time(), phase='prepare')
        with self.lock:
            self.jobs[job_id] = job
            self._save(job)
            self.queue.put(job_id)
        return self.get(job_id)

    def log(self, job_id, line):
        with self.lock:
            job = self.jobs[job_id]
            job['logs'] = (job['logs'] + [line])[-1000:]
            for marker, stage, progress in [('[1/5]', 'Source', 5), ('[2/5]', 'Framing', 15),
                    ('[3/5]', 'Transcription', 25), ('[4/5]', 'Candidates', 60),
                    ('[5/5]', 'Rendering', 70)]:
                if marker in line:
                    job.update(stage=stage, progress=progress)
            self._save(job)

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs[job_id]
            if job['status'] in TERMINAL:
                return self.get(job_id)
            job.update(status='cancelled', stage='Cancelled')
            process = self.processes.get(job_id)
            if process and process.poll() is None:
                # Kill descendants too, including a running FFmpeg/Whisper child.
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   capture_output=True)
                else:
                    import signal
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            self._save(job)
            return self.get(job_id)

    def approve(self, job_id, manifest, transcript):
        # Caller validates media/schema before committing the reviewed package.
        with self.lock:
            job = self.jobs[job_id]
            if job['status'] != 'review':
                raise ValueError('Job must be awaiting review')
            directory = Path(job['directory'])
            manifest['transcript'] = 'reviewed-transcript.json'
            (directory / 'reviewed-transcript.json').write_text(json.dumps(transcript), encoding='utf-8')
            (directory / 'reviewed-cuts.json').write_text(json.dumps(manifest), encoding='utf-8')
            job.update(status='queued', phase='render', stage='Waiting to render', progress=65)
            self._save(job)
            self.queue.put(job_id)
            return self.get(job_id)

    def _command(self, job):
        request, directory = job['request'], Path(job['directory'])
        base = [sys.executable, '-u', str(SCRIPT)]
        if job['phase'] == 'prepare':
            command = base + ['auto', '--prepare-only', '--exact-output', '--out', str(directory),
                              '--cache-dir', str(self.root / '.cache')]
            for key in ('video', 'url', 'chat', 'count', 'preset', 'layout', 'encoder', 'bgm',
                        'bgm_volume', 'words_per_group', 'model', 'device', 'skip_intro'):
                if request.get(key) is not None:
                    command += ['--' + key.replace('_', '-'), str(request[key])]
            command += ['--word-pop' if request.get('word_pop', True) else '--no-word-pop',
                        '--uppercase' if request.get('uppercase', True) else '--no-uppercase']
            return command
        manifest = json.loads((directory / 'reviewed-cuts.json').read_text(encoding='utf-8'))
        command = base + ['render', '--video', manifest['source'], '--manifest',
                         str(directory / 'reviewed-cuts.json'), '--out', str(directory / 'exports'),
                         '--encoder', request.get('encoder', 'auto')]
        if request.get('bgm'):
            command += ['--bgm', request['bgm'], '--bgm-volume', str(request.get('bgm_volume', .2))]
        return command

    def _execute(self, job_id, command):
        with self.lock:
            if self.jobs[job_id]['status'] == 'cancelled':
                return False
            options = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NO_WINDOW}
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, **options)
            self.processes[job_id] = process
        try:
            for line in process.stdout:
                self.log(job_id, line.rstrip())
            code = process.wait()
            if self.get(job_id)['status'] == 'cancelled':
                return False
            if code:
                raise RuntimeError(f'Pipeline exited with code {code}; see job logs.')
            return True
        finally:
            process.stdout.close()
            with self.lock:
                self.processes.pop(job_id, None)

    def _worker(self):
        while True:
            job_id = self.queue.get()
            try:
                with self.lock:
                    job = self.jobs[job_id]
                    if job['status'] == 'cancelled':
                        continue
                    job.update(status='running', stage='Rendering' if job['phase'] == 'render' else 'Preparing source')
                    self._save(job)
                if not self._execute(job_id, self._command(job)):
                    continue
                if job['phase'] == 'render':
                    with self.lock:
                        job.update(stage='Technical QA', progress=90)
                        self._save(job)
                    if not self._execute(job_id, [sys.executable, '-u', str(SCRIPT), 'verify',
                                                 '--folder', str(Path(job['directory']) / 'exports')]):
                        continue
                with self.lock:
                    if job['status'] != 'cancelled':
                        ready = job['phase'] == 'prepare'
                        job.update(status='review' if ready else 'completed',
                                   stage='Review candidates' if ready else 'Completed',
                                   progress=65 if ready else 100)
                        self._save(job)
            except Exception as exc:
                with self.lock:
                    job = self.jobs[job_id]
                    if job['status'] != 'cancelled':
                        job.update(status='failed', error=str(exc), stage='Failed')
                        self._save(job)
            finally:
                self.queue.task_done()
