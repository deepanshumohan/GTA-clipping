# GTA Clipping & Video-to-Reels Studio

A local Python and FFmpeg studio for turning videos and stream recordings into vertical clips. Whisper runs locally; URL ingestion uses yt-dlp. Model and video downloads require a network connection. No paid inference API is required.

## Setup

Use Python 3.10 or newer and install FFmpeg plus ffprobe on PATH. The imageio-ffmpeg dependency provides a fallback FFmpeg executable, but does not provide ffprobe. NVIDIA acceleration also requires a compatible GPU and driver; CPU rendering is supported.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python web_ui.py
```

Open http://127.0.0.1:8000. Keep this local studio bound to loopback; it is not an authenticated multi-user service. Use one server process, without Uvicorn reload or multiple workers.

## Studio workflow

1. Enter a local video path or a YouTube/Twitch URL, optional chat JSON, and style settings.
2. Submit a job. A single worker prepares queued jobs and streams stage logs. Progress values indicate stages rather than a time-to-completion estimate.
3. Review candidates: play source ranges, adjust start/end times, choose framing and horizontal crop, remove weak candidates, and correct transcript text. Corrections remove old word alignment so corrected phrases stay static instead of highlighting incorrect words.
4. Use **Preview framing and captions** for a low-resolution preview of the first eight seconds of a candidate's first range. Advanced JSON editors expose multi-range cuts, crop boxes, layout options, captions, and transcript timing. Click **Apply JSON edits** before rendering.
5. Click **Render reviewed clips**. The worker renders full-resolution exports and runs technical QA. Inspect playback, captions, framing, and the actual payoff before publishing.

Jobs have separate folders under `reels_output/job-<id>/`. The job selector restores earlier work. Cancel stops the active process tree or cancels a queued/review job. After restart, review jobs remain available; previously queued/running jobs are marked interrupted and can be resubmitted. The queue does not automatically resume partial renders.

## CLI

```powershell
# Complete automatic run in a new, unique subfolder
python skills/video-to-reels/scripts/reels.py auto --video "gameplay.mp4" --count 5 --out "reels_output/gameplay"

# Prepare candidates without rendering
python skills/video-to-reels/scripts/reels.py auto --video "gameplay.mp4" --prepare-only --out "reels_output/review"

# Optional URL, chat, music, and shared cache
python skills/video-to-reels/scripts/reels.py auto --url "https://youtube.com/watch?v=..." --chat "chat.json" --bgm "music.mp3" --cache-dir "reels_output/.cache"

# Render an edited manifest; existing files are protected unless --overwrite is explicit
python skills/video-to-reels/scripts/reels.py render --video "gameplay.mp4" --manifest "cuts.json" --out "reels_output/export"
python skills/video-to-reels/scripts/reels.py verify --folder "reels_output/export"
```

Automatic runs preserve previous results. Transcripts are cached by source content plus model, language, device, and compute settings. Audio RMS analysis is cached for repeat preparation. Decoding retains one audio bucket in memory and stores per-bucket summaries. Encoder capability detection is cached per process. With `--encoder auto`, a failed hardware encode retries on CPU; explicitly selected encoders fail visibly.

Use `--no-word-pop` or `--no-uppercase` to disable those styles. Other commands include `analyze`, `transcribe`, `suggest-moments`, `detect-facecam`, `detect-audio-spikes`, `find-chat-spikes`, and `detect-silence`; each supports `--help`.

## Selection and QA

Candidate ranking combines transcript density, whole-word excitement keywords, punctuation, audio peaks, and optional chat bursts. Sentence endings and pauses receive preference, and selected candidates do not overlap. Scores are heuristics, not calibrated probabilities of virality. The facecam detector is also heuristic; inspect its framing. Neither selection nor facecam detection performs semantic action tracking.

Exports include MP4s, ASS captions, `cuts.json`, `transcript.json`, `posting.md`, `render_report.json`, and `qa.json`. Hard QA checks cover full decode, vertical aspect ratio, expected duration, and missing expected audio. Advisory diagnostics report black intervals, frozen/static frames, measured integrated loudness/true peak, and possible caption overflow. Static gameplay, fades, or silent footage can be intentional. Caption width estimates depend on available fonts and do not replace visual inspection. Full diagnostic scanning adds processing time.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/
```

Tests generate synthetic audio/video and cover content-aware caching, concurrent submissions, restart recovery, candidate review validation, CPU retry, preservation of exports, and preparation-through-render QA. A Node-based JavaScript smoke test runs when Node is available. Tests use cached synthetic transcripts; live Whisper downloads/inference, live stream downloads, and visual editorial quality require separate validation.

Core implementation: `skills/video-to-reels/scripts/reels.py`. Web API and dashboard: `web_ui.py`. Persistent worker: `studio_jobs.py`. Editorial guidance and manifest details live in `skills/video-to-reels/`.
