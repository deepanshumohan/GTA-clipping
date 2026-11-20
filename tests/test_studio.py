import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/video-to-reels/scripts'))
import studio_jobs
import reels


@pytest.fixture
def media(tmp_path):
    video = tmp_path / 'source.mp4'
    reels.run([reels.ffmpeg(), '-v', 'error', '-f', 'lavfi', '-i',
               'testsrc2=size=320x180:rate=10:duration=3', '-f', 'lavfi', '-i',
               'sine=frequency=440:duration=3', '-c:v', 'libx264', '-c:a', 'aac', str(video)])
    return video


def test_audio_detector_decodes_real_signal(tmp_path):
    import wave
    rng = np.random.default_rng(1)
    samples = rng.normal(0, 100, 16000 * 10)
    samples[5*16000:6*16000] *= 15
    audio = tmp_path / 'spike.wav'
    with wave.open(str(audio), 'wb') as out:
        out.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        out.writeframes(samples.astype(np.int16).tobytes())
    peaks = reels.detect_audio_spikes_core(audio, before=1, after=1)
    assert len(peaks) == 1
    assert peaks[0]['time'] == 5
    assert peaks[0]['ratio'] > 10


def test_cache_tracks_source_and_settings(tmp_path):
    video = tmp_path / 'video.mp4'
    video.write_bytes(b'first')
    args = SimpleNamespace(model='base', language=None, device='cpu', compute_type='int8')
    first = reels.transcript_cache_key(video, args)
    video.write_bytes(b'other')
    assert reels.transcript_cache_key(video, args) != first
    second = reels.transcript_cache_key(video, args)
    args.model = 'small'
    assert reels.transcript_cache_key(video, args) != second


def test_preparation_review_render_end_to_end(tmp_path):
    video = tmp_path / 'long.mp4'
    reels.run([reels.ffmpeg(), '-v', 'error', '-f', 'lavfi', '-i',
               'testsrc2=size=160x90:rate=10:duration=18', '-f', 'lavfi', '-i',
               'sine=duration=18', '-c:v', 'libx264', '-c:a', 'aac', str(video)])
    manager = studio_jobs.JobManager(tmp_path / 'jobs')
    settings = SimpleNamespace(model='base', language=None, device='cpu', compute_type='auto')
    key = reels.transcript_cache_key(video, settings)
    reels.save(manager.root / '.cache' / (key + '.json'), {
        'source': str(video), 'cache_key': key,
        'segments': [{'start': 0, 'end': 18, 'text': 'A complete example sentence.', 'words': []}]})
    job = manager.submit(dict(video=str(video), count=1, layout='crop', device='cpu', model='base'))

    def wait_for(status):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            current = manager.get(job['id'])
            if current['status'] == status:
                return current
            assert current['status'] not in ('failed', 'cancelled'), current
            time.sleep(.05)
        pytest.fail(str(manager.get(job['id'])))

    ready = wait_for('review')
    directory = Path(ready['directory'])
    manifest = reels.load(directory / 'cuts.json')
    manifest.update(width=180, height=320, fps=10)
    manifest['reels'][0]['ranges'] = [[0, 1]]
    manager.approve(job['id'], manifest, reels.load(directory / 'transcript.json'))
    wait_for('completed')
    qa = reels.load(directory / 'exports/qa.json')
    assert qa['checks'][0]['decode_ok']
    assert qa['checks'][0]['audio_ok']
    assert qa['checks'][0]['duration_ok']


def test_unique_jobs_cancel_and_restart(tmp_path):
    manager = studio_jobs.JobManager(tmp_path, start_worker=False)
    first, second = manager.submit({'video': 'a'}), manager.submit({'video': 'b'})
    assert first['directory'] != second['directory']
    manager.cancel(first['id'])
    restarted = studio_jobs.JobManager(tmp_path, start_worker=False)
    assert restarted.get(first['id'])['status'] == 'cancelled'
    assert restarted.get(second['id'])['status'] == 'interrupted'


def test_concurrent_submission_isolated(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    manager = studio_jobs.JobManager(tmp_path, start_worker=False)
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(pool.map(lambda _: manager.submit({'video': 'a'}), range(20)))
    assert len({j['id'] for j in jobs}) == 20
    assert manager.queue.qsize() == 20


def test_cancel_stops_running_child(tmp_path):
    import threading
    manager = studio_jobs.JobManager(tmp_path, start_worker=False)
    job = manager.submit({})
    runner = threading.Thread(target=manager._execute, args=(job['id'],
        [sys.executable, '-c', 'import time; time.sleep(20)']))
    runner.start()
    deadline = time.monotonic() + 5
    while job['id'] not in manager.processes and time.monotonic() < deadline:
        time.sleep(.01)
    try:
        assert job['id'] in manager.processes
    finally:
        manager.cancel(job['id'])
        runner.join(timeout=5)
    assert not runner.is_alive()
    assert manager.get(job['id'])['status'] == 'cancelled'


def test_chat_and_audio_share_candidate_pool(tmp_path, monkeypatch):
    transcript = tmp_path / 'transcript.json'
    reels.save(transcript, {'segments': [
        {'start': i*5, 'end': (i+1)*5, 'text': 'A complete sentence.', 'words': []}
        for i in range(12)]})
    monkeypatch.setattr(reels, 'detect_audio_spikes_core',
                        lambda *a, **k: [{'time': 5, 'ratio': 2}])
    monkeypatch.setattr(reels, 'parse_chat_file', lambda _: [])
    monkeypatch.setattr(reels, 'find_chat_spikes_core', lambda *a, **k:
        ([{'start': 45, 'end': 60, 'ratio': 10}], 0, 60))
    args = SimpleNamespace(transcript=str(transcript), video='source.mp4',
        out=str(tmp_path / 'cuts.json'), min_duration=15, max_duration=15,
        max_reels=2, default_layout='fit', subtitle_preset='classic', uppercase=False)
    reels.suggest_moments(args)
    without_chat = reels.load(args.out)['reels'][0]['ranges'][0][0]
    args.chat = 'chat.json'
    reels.suggest_moments(args)
    selected = reels.load(args.out)['reels']
    assert selected[0]['ranges'][0][0] > without_chat
    a, b = [r['ranges'][0] for r in selected]
    assert min(a[1], b[1]) <= max(a[0], b[0])


def test_render_verify_and_preserve_exports(media, tmp_path):
    manifest = tmp_path / 'cuts.json'
    reels.save(manifest, {'width': 180, 'height': 320, 'fps': 10,
        'reels': [{'name': 'clip', 'ranges': [[0, 1]], 'layout': 'crop',
                   'burn_captions': False}]})
    args = SimpleNamespace(video=str(media), manifest=str(manifest),
        out=str(tmp_path / 'exports'), encoder='libx264', preset='ultrafast',
        overwrite=False, bgm=None, bgm_volume=.2)
    reels.render(args)
    reels.verify(SimpleNamespace(folder=args.out))
    qa = reels.load(Path(args.out) / 'qa.json')['checks'][0]
    assert qa['decode_ok'] and qa['duration_ok'] and qa['audio_ok']
    assert 'loudness' in qa['diagnostics']
    with pytest.raises(FileExistsError):
        reels.render(args)


def test_hardware_failure_retries_cpu(media, tmp_path, monkeypatch):
    manifest = tmp_path / 'cuts.json'
    reels.save(manifest, {'width': 180, 'height': 320, 'fps': 10,
        'reels': [{'name': 'retry', 'ranges': [[0, .5]], 'layout': 'crop', 'burn_captions': False}]})
    monkeypatch.setattr(reels, 'detect_hardware_encoder', lambda: 'h264_nvenc')
    original = reels.run
    calls = []
    def fail_gpu(command, **kwargs):
        calls.append(command)
        if 'h264_nvenc' in command:
            raise subprocess.CalledProcessError(1, command)
        return original(command, **kwargs)
    monkeypatch.setattr(reels, 'run', fail_gpu)
    reels.render(SimpleNamespace(video=str(media), manifest=str(manifest),
        out=str(tmp_path / 'retry'), encoder='auto', overwrite=False, bgm=None))
    assert len(calls) == 2
    assert 'libx264' in calls[-1]


def test_cli_dispatch_once(tmp_path):
    # A second dispatch would be observable as two JSON outputs.
    path = tmp_path / 'chat.json'
    path.write_text('[]')
    source = Path(reels.__file__).read_text(encoding='utf-8')
    assert source.count('    args.func(args)') == 1


def test_web_review_validation_and_exports(media, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import web_ui
    manager = studio_jobs.JobManager(tmp_path / 'jobs', start_worker=False)
    monkeypatch.setattr(web_ui, 'JOBS', manager)
    client = TestClient(web_ui.app)
    assert client.post('/api/render-auto', json={}).status_code == 422
    assert client.post('/api/render-auto', json={'video': str(media), 'count': 0}).status_code == 422
    result = client.post('/api/render-auto', json={'video': str(media)}).json()
    job_id = result['id']
    directory = Path(result['directory'])
    manifest = {'width': 180, 'height': 320, 'fps': 10, 'source': str(media),
        'reels': [{'name': 'clip', 'ranges': [[0, 1]], 'burn_captions': False}]}
    transcript = {'source': str(media), 'segments': []}
    reels.save(directory / 'cuts.json', manifest)
    reels.save(directory / 'transcript.json', transcript)
    manager.jobs[job_id]['status'] = 'review'
    assert client.get(f'/api/jobs/{job_id}/review').status_code == 200
    preview = client.post(f'/api/jobs/{job_id}/preview', json={'manifest': manifest, 'transcript': transcript})
    assert preview.status_code == 200
    assert preview.headers['content-type'] == 'video/mp4'
    assert len(preview.content) > 1000
    manifest['reels'][0]['ranges'] = [[0, 99]]
    assert client.post(f'/api/jobs/{job_id}/approve', json={'manifest': manifest, 'transcript': transcript}).status_code == 422
    manifest['reels'][0]['ranges'] = [[0, 1]]
    assert client.post(f'/api/jobs/{job_id}/approve', json={'manifest': manifest, 'transcript': transcript}).status_code == 200
    assert manager.get(job_id)['phase'] == 'render'
    assert client.get('/api/exports', params={'folder': str(tmp_path)}).status_code == 422
    assert client.post('/api/render-auto', json={'video': str(media)}, headers={'origin': 'https://example.com'}).status_code == 403
