---
name: video-to-reels
description: Turn a supplied video or stream into edited Instagram-ready vertical reels with complete highlights, clean cuts, reviewed on-screen subtitles, and checked MP4 exports. Supports automated end-to-end production with NVIDIA NVENC hardware acceleration, facecam detection, and multi-modal moment finding.
---

# Video to Reels

Deliver edited MP4s, not just timestamps or advice. Read [the editing guide](references/editing-guide.md) for selection, framing, and manifest details. Use `scripts/reels.py` for analysis, transcription, moment suggestion, silence detection, hardware-accelerated rendering, and technical checks. The agent makes editorial choices; the script provides deterministic rendering and zero-cost local automation.

## Defaults

- Use the supplied video or stream URL. Ask for it only if missing/inaccessible.
- With no other direction, choose up to 3–6 distinct strong moments from a long video, fewer when material supports fewer. Aim roughly 15–60 seconds when appropriate.
- Supply short titles, suggested post captions, and relevant hashtags.
- Default to 1080×1920, 30 fps, H.264/AAC MP4 with fast-start.
- **Hardware Acceleration**: Automatically selects GPU encoding (`h264_nvenc` on NVIDIA, `h264_videotoolbox` on macOS, `h264_qsv` on Intel) with graceful CPU fallback.
- **Subtitles**: Presets (`hormozi`, `neon`, `classic`, `boxed`) with synchronized karaoke highlighting, high-retention word-by-word pop bounce animations, and customizable word grouping (1–3 words per card).
- **Layout Options**: `auto` (smart facecam ROI detection), `fit` (centered with blurred background), `crop` (fixed offset or exact `crop_box`), `split`/`stacked` (vertical split for facecam + gameplay), and `pip` (picture-in-picture inset).
- **Background Music**: Supports royalty-free BGM with automated sidechain audio ducking during speech.

## Completion standard

The task is complete only when each selected reel has a playable MP4, reviewed burned-in subtitles when speech is present, a short title, paste-ready post caption and relevant hashtags, plus technical QA. Provide direct links to every MP4 and `posting.md`, `qa.json`, and `render_report.json`.

## Quick Start: One-Command Auto Pipeline

Run end-to-end moment finding, facecam detection, transcription, and GPU rendering with a single command:

```powershell
# From local video file:
python scripts/reels.py auto --video "INPUT.mp4" --count 5 --preset hormozi --out "reels_output/auto_run"

# From YouTube / Twitch URL directly:
python scripts/reels.py auto --url "https://youtube.com/watch?v=..." --count 5 --preset hormozi --out "reels_output/auto_run"

# With chat logs and background music auto-ducking:
python scripts/reels.py auto --video "INPUT.mp4" --chat "chat.json" --bgm "music.mp3" --out "reels_output/auto_run"
```

## Interactive Web Studio

Launch the local web dashboard to visually scrub timelines, inspect facecam detection, preview subtitle presets, and render with one click:

```powershell
python web_ui.py --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

## Modular CLI Commands

Paths below are relative to this skill directory:

```powershell
# 1. Detect Streamer Facecam ROI:
python scripts/reels.py detect-facecam --video "INPUT.mp4"

# 2. Detect Audio Screams / Volume Spikes (Zero API Cost):
python scripts/reels.py detect-audio-spikes --video "INPUT.mp4" --out "OUTPUT/audio_spikes.json"

# 3. Detect Chat Burst Spikes (Twitch / YouTube):
python scripts/reels.py find-chat-spikes --chat "chat.json" --out "OUTPUT/cuts.json" --subtitle-preset hormozi

# 4. Multi-Modal Moment Suggestion (Audio + Transcript):
python scripts/reels.py suggest-moments --transcript "OUTPUT/transcript.json" --video "INPUT.mp4" --out "OUTPUT/cuts.json"

# 5. Local Whisper Speech-to-Text:
python scripts/reels.py transcribe --video "INPUT.mp4" --out "OUTPUT/transcript.json" --device auto

# 6. Render with GPU NVENC & Subtitles:
python scripts/reels.py render --video "INPUT.mp4" --manifest "OUTPUT/cuts.json" --out "OUTPUT/exports" --encoder auto

# 7. Verify Technical Compliance:
python scripts/reels.py verify --folder "OUTPUT/exports"
```
