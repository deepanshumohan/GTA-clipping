"""GTA-Clipping & Video-to-Reels Studio - Interactive Web Dashboard.
Run:
    python web_ui.py
Open:
    http://127.0.0.1:8000
"""
import json
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
from studio_jobs import JobManager, ROOT

JOBS = JobManager()

# Import core reels functions
sys.path.insert(0, str(Path(__file__).parent / "skills" / "video-to-reels" / "scripts"))
import reels

app = FastAPI(title="GTA-Clipping & Video-to-Reels Studio")


@app.middleware('http')
async def same_origin_mutations(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and origin:
        from urllib.parse import urlsplit
        if urlsplit(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail': 'Cross-origin writes are disabled'}, status_code=403)
    return await call_next(request)


class AutoRunRequest(BaseModel):
    video: Optional[str] = None
    url: Optional[str] = None
    chat: Optional[str] = None
    count: int = Field(default=5, ge=1, le=15)
    preset: Literal["hormozi", "neon", "classic", "boxed"] = "hormozi"
    layout: Literal["auto", "fit", "crop", "split", "pip"] = "auto"
    encoder: Literal["auto", "libx264", "h264_nvenc", "h264_qsv", "h264_videotoolbox"] = "auto"
    bgm: Optional[str] = None
    bgm_volume: float = Field(default=.20, ge=0, le=1)
    words_per_group: int = Field(default=3, ge=1, le=12)
    word_pop: bool = True
    uppercase: bool = True
    model: str = "base"
    device: str = "auto"
    skip_intro: float = Field(default=15, ge=0, le=1440)


class FacecamRequest(BaseModel):
    video: str


class ScanRequest(BaseModel):
    chat: Optional[str] = None
    video: Optional[str] = None
    top: int = Field(default=10, ge=1, le=100)


@app.get("/api/status")
def get_status():
    enc = reels.detect_hardware_encoder()
    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except Exception:
        has_cuda = False

    return {
        "status": "online",
        "encoder": enc,
        "is_gpu_accelerated": enc in ("h264_nvenc", "h264_videotoolbox", "h264_qsv"),
        "cuda_available": has_cuda,
        "ffmpeg": reels.ffmpeg(),
        "is_busy": any(j["status"] in ("running", "queued") for j in JOBS.list())
    }


@app.post("/api/detect-facecam")
def api_detect_facecam(req: FacecamRequest):
    p = Path(req.video)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    res = reels.detect_facecam(p)
    return res


@app.post("/api/scan-moments")
def api_scan_moments(req: ScanRequest):
    peaks = []
    # If chat provided
    if req.chat and Path(req.chat).exists():
        msgs = reels.parse_chat_file(req.chat)
        chat_peaks, total, duration = reels.find_chat_spikes_core(msgs, top_k=req.top)
        peaks.extend([{
            "type": "chat",
            "time": p["spike_time"],
            "start": p["start"],
            "end": p["end"],
            "ratio": p["ratio"],
            "score": p["score"],
            "label": f"Chat Spike: {', '.join(p['top_words'][:3])}",
            "sample_quotes": p.get("sample_quotes", [])
        } for p in chat_peaks])

    # If video provided, check audio spikes
    if req.video and Path(req.video).exists():
        audio_spikes = reels.detect_audio_spikes_core(req.video, top_k=req.top)
        peaks.extend([{
            "type": "audio",
            "time": s["time"],
            "start": s["start"],
            "end": s["end"],
            "ratio": s["ratio"],
            "score": s["ratio"] * 2.0,
            "label": f"Audio Scream/Volume Peak ({s['ratio']:.1f}x)",
            "rms": s["rms"]
        } for s in audio_spikes])

    peaks.sort(key=lambda x: x["score"], reverse=True)
    return {"count": len(peaks), "peaks": peaks[:req.top]}


@app.post("/api/render-auto")
def api_render_auto(req: AutoRunRequest):
    if bool(req.video) == bool(req.url):
        raise HTTPException(422, 'Provide exactly one local video or URL')
    for key in ('video', 'chat', 'bgm'):
        value = getattr(req, key)
        if value and not Path(value).is_file():
            raise HTTPException(422, f'{key} file not found')
    return JOBS.submit(req.model_dump() if hasattr(req, 'model_dump') else req.dict())


@app.get("/api/jobs")
def list_jobs():
    return {'jobs': JOBS.list()}


def require_job(job_id):
    try:
        return JOBS.get(job_id)
    except KeyError:
        raise HTTPException(404, 'Job not found')


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return require_job(job_id)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    require_job(job_id)
    return JOBS.cancel(job_id)


@app.get("/api/jobs/{job_id}/review")
def review_job(job_id: str):
    job = require_job(job_id)
    if job['status'] != 'review':
        raise HTTPException(409, 'Candidates are not ready for review')
    directory = Path(job['directory'])
    return {'manifest': reels.load(directory / 'cuts.json'),
            'transcript': reels.load(directory / 'transcript.json')}


@app.get("/api/jobs/{job_id}/source")
def job_source(job_id: str):
    job = require_job(job_id)
    manifest = Path(job['directory']) / 'cuts.json'
    if not manifest.exists():
        raise HTTPException(409, 'Source is not ready')
    return FileResponse(reels.load(manifest)['source'], media_type='video/mp4')


class ReviewRequest(BaseModel):
    manifest: dict
    transcript: dict


@app.post('/api/jobs/{job_id}/preview')
def preview_candidate(job_id: str, req: ReviewRequest, index: int = 0):
    import uuid
    from types import SimpleNamespace
    job = require_job(job_id)
    if job['status'] != 'review':
        raise HTTPException(409, 'Job is not awaiting review')
    original = reels.load(Path(job['directory']) / 'cuts.json')
    try:
        if not 0 <= index < len(req.manifest['reels']):
            raise ValueError('Invalid candidate index')
        info = reels.probe(original['source'])
        reels.validate_manifest(req.manifest, info)
        reels.validate_transcript(req.transcript, info['duration'])
        directory = Path(job['directory']) / '.previews' / uuid.uuid4().hex
        directory.mkdir(parents=True)
        reel = dict(req.manifest['reels'][index])
        start, end = reel['ranges'][0]
        reel.update(name='preview', ranges=[[start, min(end, start + 8)]])
        manifest = dict(req.manifest, width=360, height=640, fps=15,
                        transcript='transcript.json', reels=[reel])
        req.transcript['source'] = original['source']
        reels.save(directory / 'transcript.json', req.transcript)
        reels.save(directory / 'cuts.json', manifest)
        reels.render(SimpleNamespace(video=original['source'], manifest=str(directory / 'cuts.json'),
            out=str(directory / 'render'), encoder='libx264', preset='ultrafast', overwrite=False))
        return FileResponse(directory / 'render/preview.mp4', media_type='video/mp4')
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc))


@app.post("/api/jobs/{job_id}/approve")
def approve_job(job_id: str, req: ReviewRequest):
    job = require_job(job_id)
    if job['status'] != 'review':
        raise HTTPException(409, 'Job is not awaiting review')
    original = reels.load(Path(job['directory']) / 'cuts.json')
    # Source and transcript destinations are controlled by the server.
    req.manifest['source'] = original['source']
    req.manifest['transcript'] = 'reviewed-transcript.json'
    req.transcript['source'] = original['source']
    try:
        info = reels.probe(original['source'])
        reels.validate_manifest(req.manifest, info)
        segments = reels.validate_transcript(req.transcript, info['duration'])
        reels.validate_reel_subtitles(req.manifest, info, segments)
        return JOBS.approve(job_id, req.manifest, req.transcript)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/logs")
def get_logs():
    jobs = JOBS.list()
    return {'running': any(j['status'] in ('queued', 'running') for j in jobs),
            'logs': jobs[0]['logs'] if jobs else []}


@app.get("/api/exports")
def get_exports(folder: str = "reels_output"):
    p = Path(folder)
    p = (p if p.is_absolute() else ROOT / p).resolve()
    if not p.is_relative_to(JOBS.root):
        raise HTTPException(422, 'Export folder must be inside reels_output')
    if not p.exists():
        return {"count": 0, "reels": []}
        
    results = []
    # Find all mp4 files recursively
    for mp4 in p.rglob("*.mp4"):
        if '.previews' in mp4.parts or mp4.name.startswith('source_video.'):
            continue
        manifest_path = mp4.parent / "cuts.json"
        posting_path = mp4.parent / "posting.md"
        qa_path = mp4.parent / "qa.json"
        
        caption_text = ""
        hashtags = ""
        if posting_path.exists():
            content = posting_path.read_text(encoding="utf-8")
            caption_text = content[:200]
            
        results.append({
            "name": mp4.name,
            "path": str(mp4.resolve()),
            "rel_url": f"/files/{mp4.resolve().relative_to(ROOT).as_posix()}",
            "size_mb": round(mp4.stat().st_size / (1024 * 1024), 2),
            "folder": str(mp4.parent.name),
            "has_qa": qa_path.exists(),
            "preview_caption": caption_text
        })
    results.sort(key=lambda x: x["name"])
    return {"count": len(results), "reels": results}


# Mount static output files for live video playback in browser
reels_dir = ROOT / "reels_output"
reels_dir.mkdir(parents=True, exist_ok=True)
app.mount("/files/reels_output", StaticFiles(directory=str(reels_dir)), name="reels_output")


@app.get("/", response_class=HTMLResponse)
def index_html():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GTA-Clipping & Video-to-Reels Studio</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0B0E14;
      --card-bg: #151922;
      --card-border: #232936;
      --primary: #FFDF00;
      --primary-hover: #FFE633;
      --accent: #00FF66;
      --text: #F1F5F9;
      --text-muted: #94A3B8;
      --danger: #EF4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: rgba(21, 25, 34, 0.8);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      padding: 16px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 50;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand h1 {
      font-size: 20px;
      font-weight: 800;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #FFDF00 0%, #FF8800 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .badge {
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 9999px;
      background: rgba(0, 255, 102, 0.12);
      color: var(--accent);
      border: 1px solid rgba(0, 255, 102, 0.3);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .badge.cpu {
      background: rgba(148, 163, 184, 0.15);
      color: var(--text-muted);
      border-color: rgba(148, 163, 184, 0.3);
    }
    .badge::before {
      content: '';
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
    }
    .container {
      display: grid;
      grid-template-columns: 460px 1fr;
      gap: 24px;
      padding: 24px 32px;
      flex: 1;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }
    .card h2 {
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .form-group {
      margin-bottom: 16px;
    }
    label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    input[type="text"], input[type="number"], select {
      width: 100%;
      background: #0B0E14;
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 14px;
      font-family: inherit;
      transition: all 0.2s;
    }
    input:focus, select:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(255, 223, 0, 0.2);
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .checkbox-group {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
      font-size: 13px;
      color: var(--text);
      cursor: pointer;
    }
    .checkbox-group input {
      accent-color: var(--primary);
      width: 16px;
      height: 16px;
      cursor: pointer;
    }
    button.btn-primary {
      width: 100%;
      background: var(--primary);
      color: #000;
      font-weight: 700;
      font-size: 14px;
      padding: 14px;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s;
      box-shadow: 0 4px 16px rgba(255, 223, 0, 0.25);
      margin-top: 8px;
    }
    button.btn-primary:hover {
      background: var(--primary-hover);
      transform: translateY(-1px);
    }
    button.btn-secondary {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    button.btn-secondary:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: var(--text-muted);
    }
    .right-pane {
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .terminal {
      background: #06080C;
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      height: 220px;
      overflow-y: auto;
      color: #A3E635;
      line-height: 1.5;
    }
    .gallery-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 20px;
      margin-top: 16px;
    }
    .reel-card {
      background: #0E121A;
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: transform 0.2s, border-color 0.2s;
    }
    .reel-card:hover {
      transform: translateY(-2px);
      border-color: var(--primary);
    }
    .reel-card video {
      width: 100%;
      aspect-ratio: 9/16;
      background: #000;
      object-fit: cover;
    }
    .reel-card-info {
      padding: 12px 14px;
      font-size: 12px;
    }
    .reel-card-title {
      font-weight: 700;
      font-size: 13px;
      color: var(--text);
      margin-bottom: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .tag {
      font-size: 10px;
      font-weight: 700;
      color: var(--primary);
      text-transform: uppercase;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <h1>GTA-CLIPPING &bull; STUDIO</h1>
      <span class="badge" id="gpu-badge">Detecting GPU...</span>
    </div>
    <div>
      <button class="btn-secondary" onclick="fetchExports()">🔄 Refresh Gallery</button>
    </div>
  </header>

  <div class="container">
    <!-- Configuration Column -->
    <div class="card">
      <h2>⚙️ Reel Production Engine</h2>

      <div class="form-group">
        <label>Input Video File Path (Local MP4)</label>
        <input type="text" id="video-path" placeholder="e.g. D:/Videos/gameplay.mp4">
      </div>

      <div class="form-group">
        <label>Or YouTube / Twitch Stream URL</label>
        <input type="text" id="stream-url" placeholder="https://youtube.com/watch?v=... or Twitch VOD">
      </div>

      <div class="form-group">
        <label>Optional Chat JSON (Twitch / YouTube)</label>
        <input type="text" id="chat-path" placeholder="e.g. D:/git/GTA-clipping/lias_re_chat.json">
      </div>

      <div class="grid-2">
        <div class="form-group">
          <label>Layout Mode</label>
          <select id="layout-mode">
            <option value="auto">Auto (Smart Facecam)</option>
            <option value="split">Split / Stacked</option>
            <option value="fit">Fit (Blurred BG)</option>
            <option value="crop">Crop (9:16 Center)</option>
            <option value="pip">PiP (Facecam Inset)</option>
          </select>
        </div>

        <div class="form-group">
          <label>Subtitle Preset</label>
          <select id="subtitle-preset">
            <option value="hormozi">Hormozi (Yellow & Black)</option>
            <option value="neon">Neon Green</option>
            <option value="classic">Classic White</option>
            <option value="boxed">Boxed High-Contrast</option>
          </select>
        </div>
      </div>

      <div class="grid-2">
        <div class="form-group">
          <label>Number of Clips</label>
          <input type="number" id="clip-count" value="5" min="1" max="15">
        </div>

        <div class="form-group">
          <label>Hardware Encoder</label>
          <select id="encoder-choice">
            <option value="auto">Auto (GPU Preferred)</option>
            <option value="h264_nvenc">NVIDIA NVENC</option>
            <option value="libx264">CPU (libx264)</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label>Background Music (Optional MP3)</label>
        <input type="text" id="bgm-path" placeholder="e.g. D:/Music/bgm.mp3">
      </div>

      <div class="grid-2">
        <label class="checkbox-group">
          <input type="checkbox" id="word-pop" checked>
          Word-by-Word Pop Animation
        </label>
        <label class="checkbox-group">
          <input type="checkbox" id="uppercase" checked>
          ALL CAPS Subtitles
        </label>
      </div>

      <div style="margin-top: 20px;">
        <button class="btn-primary" id="render-btn" onclick="startRender()">🚀 Find Candidates to Review</button>
      </div>

      <div style="margin-top: 12px; display: flex; gap: 8px;">
        <button class="btn-secondary" style="flex:1;" onclick="detectFacecam()">🔍 Test Facecam</button>
        <button class="btn-secondary" style="flex:1;" onclick="scanMoments()">⚡ Scan Moments</button>
      </div>
    </div>

    <!-- Results & Gallery Column -->
    <div class="right-pane">
      <div class="card" style="padding: 16px 20px;">
        <h2>📟 Live Console & Progress</h2>
        <div id="job-status" role="status">Ready</div>
        <progress id="job-progress" max="100" value="0" style="width:100%"></progress>
        <button class="btn-secondary" onclick="cancelActiveJob()">Cancel job</button>
        <select id="job-history" onchange="selectJob(this.value)"><option value="">Select a job</option></select>
        <div class="terminal" id="terminal-logs">
          [System] Ready. Enter input source and click Generate.
        </div>
      </div>

      <div class="card" id="review-panel" hidden>
        <h2>Review candidates</h2>
        <p>Preview each range, adjust its timing and framing, and correct captions before rendering.
        Scores rank candidates; check the context and payoff yourself.</p>
        <video id="source-preview" controls preload="metadata" style="width:100%"></video>
        <video id="framing-preview" controls hidden style="width:100%;max-height:500px"></video>
        <div id="candidate-list"></div>
        <details><summary>Edit full manifest and transcript</summary>
          <p>Transcript corrections clear stale word alignment so phrases remain accurate.</p>
          <label>Manifest JSON</label><textarea id="manifest-editor" rows="12" style="width:100%"></textarea>
          <label>Transcript JSON</label><textarea id="transcript-editor" rows="12" style="width:100%"></textarea>
          <button class="btn-secondary" onclick="applyAdvanced()">Apply JSON edits</button>
        </details>
        <button class="btn-primary" onclick="approveReview()">Render reviewed clips</button>
      </div>
      <div class="card" style="flex: 1;">
        <h2>🎬 Exported Vertical Reels</h2>
        <div id="gallery-empty" style="color: var(--text-muted); font-size: 13px; padding: 20px 0;">
          No reels found in output folder yet. Click Generate to produce vertical reels.
        </div>
        <div class="gallery-grid" id="gallery-grid"></div>
      </div>
    </div>
  </div>

  <script>
    async function loadStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const badge = document.getElementById('gpu-badge');
        if (data.encoder === 'h264_nvenc') {
          badge.textContent = '⚡ NVIDIA NVENC (GPU Acceleration Active)';
          badge.className = 'badge';
        } else {
          badge.textContent = `💻 CPU Encoder (${data.encoder})`;
          badge.className = 'badge cpu';
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function detectFacecam() {
      const video = document.getElementById('video-path').value.trim();
      if (!video) return alert("Please enter a local video path first!");
      addTerminal("[Facecam] Scanning frames for streamer facecam...");
      try {
        const res = await fetch('/api/detect-facecam', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({video})
        });
        const data = await res.json();
        if (data.has_facecam) {
          addTerminal(`[Facecam] DETECTED at ${data.corner}! Recommended layout: ${data.recommended_layout}`);
        } else {
          addTerminal(`[Facecam] No facecam detected. Recommended: fit layout.`);
        }
      } catch (e) {
        addTerminal(`[Facecam Error] ${e.message}`);
      }
    }

    async function scanMoments() {
      const chat = document.getElementById('chat-path').value.trim();
      const video = document.getElementById('video-path').value.trim();
      if (!chat && !video) return alert("Please specify either a chat JSON or video file to scan!");
      addTerminal("[Scan] Scanning for viral chat spikes and audio volume peaks...");
      try {
        const res = await fetch('/api/scan-moments', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({chat, video, top: 10})
        });
        const data = await res.json();
        addTerminal(`[Scan] Found ${data.count} candidate viral moments:`);
        data.peaks.forEach((p, i) => {
          addTerminal(`  #${i+1} [${p.time.toFixed(1)}s] ${p.label} (Score: ${p.score.toFixed(1)})`);
        });
      } catch (e) {
        addTerminal(`[Scan Error] ${e.message}`);
      }
    }

    async function startRender() {
      const video = document.getElementById('video-path').value.trim() || null;
      const url = document.getElementById('stream-url').value.trim() || null;
      if (!video && !url) return alert("Please provide either a local video path or YouTube/Twitch URL!");

      const payload = {
        video: video,
        url: url,
        chat: document.getElementById('chat-path').value.trim() || null,
        count: parseInt(document.getElementById('clip-count').value),
        preset: document.getElementById('subtitle-preset').value,
        layout: document.getElementById('layout-mode').value,
        encoder: document.getElementById('encoder-choice').value,
        bgm: document.getElementById('bgm-path').value.trim() || null,
        word_pop: document.getElementById('word-pop').checked,
        uppercase: document.getElementById('uppercase').checked
      };

      try {
        const res = await fetch('/api/render-auto', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const err = await res.json();
          return alert(err.detail || "Error starting render");
        }
        const job = await res.json();
        document.getElementById('review-panel').hidden = true;
        refreshJobs();
        activeJob = job.id; localStorage.setItem("activeJob", activeJob);
        addTerminal("[Pipeline] Job queued. Candidates will be available for review.");
        pollLogs();
      } catch (e) {
        alert("Error starting render: " + e.message);
      }
    }

    function addTerminal(msg) {
      const term = document.getElementById('terminal-logs');
      const line = document.createElement('div'); line.textContent = msg; term.appendChild(line);
      term.scrollTop = term.scrollHeight;
    }

    let activeJob = localStorage.getItem("activeJob");
    let reviewData = null;
    let pollInterval = null;
    function pollLogs() {
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch('/api/jobs/' + activeJob);
          if (!res.ok) { clearInterval(pollInterval); return; }
          const data = await res.json();
          const term = document.getElementById('terminal-logs');
          term.textContent = data.logs.join('\n');
          document.getElementById('job-status').textContent = data.stage + ' (' + data.status + ')';
          document.getElementById('job-progress').value = data.progress;
          term.scrollTop = term.scrollHeight;
          if (!['queued', 'running'].includes(data.status)) {
            clearInterval(pollInterval);
            fetchExports();
            refreshJobs();
            if (data.status === 'review') await loadReview();
            if (data.error) addTerminal(data.error);
          }
        } catch (e) {
          console.error(e);
        }
      }, 1500);
    }

    async function fetchExports() {
      try {
        await refreshJobs();
        const res = await fetch('/api/exports?folder=reels_output');
        const data = await res.json();
        const grid = document.getElementById('gallery-grid');
        const empty = document.getElementById('gallery-empty');
        if (data.count === 0) {
          empty.style.display = 'block';
          grid.innerHTML = '';
          return;
        }
        empty.style.display = 'none';
        grid.innerHTML = data.reels.map(r => `
          <div class="reel-card">
            <video controls preload="metadata">
              <source src="${escapeHTML(r.rel_url)}" type="video/mp4">
            </video>
            <div class="reel-card-info">
              <span class="tag">${escapeHTML(r.folder)}</span>
              <div class="reel-card-title">${escapeHTML(r.name)}</div>
              <div style="color: var(--text-muted); font-size: 11px;">Size: ${r.size_mb} MB</div>
            </div>
          </div>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    function escapeHTML(value) {
      return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    async function cancelActiveJob() {
      if (activeJob) await fetch('/api/jobs/' + activeJob + '/cancel', {method:'POST'});
    }
    function selectJob(id) {
      if (!id) return;
      activeJob = id; localStorage.setItem('activeJob', id);
      document.getElementById('review-panel').hidden = true;
      pollLogs();
    }
    async function refreshJobs() {
      const data = await (await fetch('/api/jobs')).json();
      const select = document.getElementById('job-history');
      select.replaceChildren(new Option('Select a job', ''));
      data.jobs.forEach(j => select.add(new Option(j.id.slice(0,16) + ' ? ' + j.status, j.id)));
      if (activeJob) select.value = activeJob;
    }
    async function loadReview() {
      const res = await fetch('/api/jobs/' + activeJob + '/review');
      if (!res.ok) return;
      reviewData = await res.json();
      document.getElementById('review-panel').hidden = false;
      document.getElementById('source-preview').src = '/api/jobs/' + activeJob + '/source';
      drawCandidates();
    }
    function syncEditors() {
      document.getElementById('manifest-editor').value = JSON.stringify(reviewData.manifest, null, 2);
      document.getElementById('transcript-editor').value = JSON.stringify(reviewData.transcript, null, 2);
    }
    function applyAdvanced() {
      try {
        const manifest=JSON.parse(document.getElementById('manifest-editor').value);
        const transcript=JSON.parse(document.getElementById('transcript-editor').value);
        if (!Array.isArray(manifest.reels) || !Array.isArray(transcript.segments)) throw new Error('Invalid manifest or transcript');
        reviewData={manifest,transcript}; drawCandidates();
      } catch(e) { alert(e.message); }
    }
    function drawCandidates() {
      const list = document.getElementById('candidate-list'); list.replaceChildren();
      reviewData.manifest.reels.forEach((reel, i) => {
        const row = document.createElement('div'); row.style.margin = '16px 0';
        const title = document.createElement('strong'); title.textContent = reel.title || reel.name; row.append(title);
        reel.ranges.forEach((range, n) => {
          const controls = document.createElement('div');
          ['Start', 'End'].forEach((label, k) => {
            const field = document.createElement('label'); field.textContent = label + ' (seconds) ';
            const input = document.createElement('input'); input.type='number'; input.step='.01'; input.min='0'; input.value=range[k];
            input.onchange=()=>{range[k]=Number(input.value); syncEditors();}; field.append(input); controls.append(field);
          });
          const play = document.createElement('button'); play.textContent='Preview range'; play.className='btn-secondary';
          play.onclick=()=>{const v=document.getElementById('source-preview'); v.currentTime=range[0]; v.ontimeupdate=()=>{if(v.currentTime>=range[1])v.pause();}; v.play();};
          controls.append(play); row.append(controls);
        });
        const layout=document.createElement('select');
        ['fit','crop','split','pip'].forEach(x=>layout.add(new Option(x,x)));
        layout.value=reel.layout; layout.onchange=()=>{reel.layout=layout.value;syncEditors();}; row.append(layout);
        const crop=document.createElement('input'); crop.type='range'; crop.min='0'; crop.max='1'; crop.step='.01'; crop.value=reel.crop_x ?? .5;
        crop.setAttribute('aria-label','Horizontal crop position'); crop.oninput=()=>{reel.crop_x=Number(crop.value);reel.top_crop_x=Number(crop.value);syncEditors();}; row.append(crop);
        const remove=document.createElement('button'); remove.textContent='Remove candidate'; remove.className='btn-secondary';
        remove.onclick=()=>{reviewData.manifest.reels.splice(i,1);drawCandidates();}; row.append(remove);
        reviewData.transcript.segments.filter(s=>reel.ranges.some(r=>s.end>r[0] && s.start<r[1])).forEach(segment=>{
          const input=document.createElement('textarea'); input.value=segment.text; input.style.width='100%';
          input.onchange=()=>{segment.text=input.value;segment.words=[];syncEditors();};row.append(input);
        });
        const preview=document.createElement('button'); preview.textContent='Preview framing and captions (8 sec)'; preview.className='btn-secondary';
        preview.onclick=async()=>{
          preview.disabled=true;
          try {
            const res=await fetch('/api/jobs/'+activeJob+'/preview?index='+i,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(reviewData)});
            if(!res.ok)throw new Error(await res.text());
            const player=document.getElementById('framing-preview');
            if(player.src.startsWith('blob:'))URL.revokeObjectURL(player.src);
            player.src=URL.createObjectURL(await res.blob());player.hidden=false;player.play();
          } catch(e){alert(e.message);} finally{preview.disabled=false;}
        };row.append(preview);list.append(row);
      });
      syncEditors();
    }
    async function approveReview() {
      try {
        const res=await fetch('/api/jobs/'+activeJob+'/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(reviewData)});
        const data=await res.json(); if(!res.ok)throw new Error(JSON.stringify(data.detail));
        document.getElementById('review-panel').hidden=true;pollLogs();
      } catch(e) {alert(e.message);}
    }
    loadStatus();
    fetchExports();
    refreshJobs();
    if (activeJob) pollLogs();
  </script>
</body>
</html>
"""


def main():
    import argparse
    p = argparse.ArgumentParser(description="GTA-Clipping & Video-to-Reels Studio")
    p.add_argument("--host", default="127.0.0.1", help="Host address (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="Port number (default 8000)")
    args = p.parse_args()

    print(f"\n=======================================================")
    print(f"  GTA-Clipping & Video-to-Reels Studio Web Dashboard")
    print(f"  Open in browser: http://{args.host}:{args.port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
