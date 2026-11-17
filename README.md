# GTA Clipping & Video-to-Reels Pipeline

A high-performance, **100% local, zero-API-cost** pipeline designed to convert long-form Twitch live streams, YouTube VODs, and offline gaming footage into viral vertical 9:16 Shorts, Reels, and TikToks.

Built with Python, FFmpeg, and local OpenAI Whisper. No paid cloud APIs, no external subscriptions.

---

## Key Features

* **Rolling Chat Burst Spike Detection**: Identifies viral moments in live chat logs (Twitch `.json` and YouTube `.live_chat.json`) using rolling baseline window multipliers.
* **Sentiment & Emoji Weighting**: Ranks moments by emotional viewer reactions (`SCREAM`, `JUMPSCARE`, `LMFAO`, `DEAD`, `CLUTCH`, `CLIP`, `💀`, `😂`, `😭`, `😱`, `🔥`).
* **Stream Intro Skip**: Automatically ignores the first 15–30 minutes of "stream starting soon" or pre-game audio setup screens so only real gameplay moments are clipped.
* **5-Parameter Virality Scoring (0–100)**:
  * **Chat Spike Velocity (25%)**: Multiplier over rolling 5-minute baseline.
  * **Emotional Reaction Density (25%)**: Density of sentiment words and reaction emojis.
  * **2-Second Hook Strength (20%)**: Immediate dialogue onset ($\le 0.8\text{s}$) vs. dead silence.
  * **Speech Pacing (15%)**: Optimal words-per-second rate without dead pauses.
  * **Climax & Payoff Impact (15%)**: Clear punchline, scream, or resolution in the final third.
* **Ultra-Readable Subtitle Presets**:
  * `yellow_shadow` / `hormozi`: Vivid high-contrast Yellow (`#FFFF00`) with solid 5px pitch-black outline and 4px solid drop shadow for maximum readability on any video background.
  * `neon`: Electric Green with solid black outline.
  * `classic`: Minimalist white with clean borders.
  * `boxed`: Opaque background box style.
* **Reaction Emojis in Subtitles & Hooks**: Context-aware sentiment emojis dynamically inserted into karaoke subtitle phrases and hook headlines (`😂`, `💀`, `😱`, `👀`, `🏃`, `🔥`).
* **Multi-Layout Vertical Canvas (1080x1920)**:
  * `fit`: Original video scaled with letterboxing.
  * `crop`: Centered or offset vertical crop on the action.
  * `split` / `stacked`: Dual-camera vertical layout (e.g. facecam on top, gameplay on bottom).
  * `pip`: Inset facecam in the corner with full-bleed background.
* **Bandwidth & Storage Efficient**: Downloads only the exact 30–45s video slices around detected chat spikes using `TwitchDownloaderCLI`'s timestamp bounds instead of downloading massive 25GB stream files.

---

## Architecture & Workflow

```mermaid
flowchart LR
    A[Twitch VOD / YouTube / Offline Video] --> B[Chat Log / Audio Energy]
    B --> C[Rolling Spike Detector]
    C --> D[5-Factor Virality Scoring]
    D --> E[Selective 30s-45s Slice Download]
    E --> F[Local Whisper Transcription]
    F --> G[ASS Karaoke Subtitles & Emojis]
    G --> H[FFmpeg 9:16 Render & QA]
```

---

## Quick Start

### 1. Prerequisites
* Python 3.9+
* FFmpeg (or `static-ffmpeg`)
* OpenAI Whisper (`pip install openai-whisper`)
* (Optional for Twitch VODs) [TwitchDownloaderCLI](https://github.com/lay295/TwitchDownloader)

### 2. Find Viral Chat Spikes & Candidate Clips
Analyze a 5-hour stream chat in 3 seconds:
```bash
python skills/video-to-reels/scripts/reels.py find-chat-spikes \
  --chat stream_chat.json \
  --skip-intro 20 \
  --top 10 \
  --out cuts.json
```

### 3. Download Isolated Clip Slices (Zero Wasted Bandwidth)
```bash
./TwitchDownloaderCLI videodownload --id <VOD_ID> -b <START_SEC>s -e <END_SEC>s -o clip_source.mp4
```

### 4. Transcribe with Local Whisper
```bash
python skills/video-to-reels/scripts/reels.py transcribe \
  --video clip_source.mp4 \
  --out transcript.json \
  --model base
```

### 5. Render Vertical Reel with Captions & Audio Mastering
```bash
python skills/video-to-reels/scripts/reels.py render \
  --video clip_source.mp4 \
  --manifest cuts.json \
  --out reels_output/export
```

### 6. Verify Technical Compliance
```bash
python skills/video-to-reels/scripts/reels.py verify --folder reels_output/export
```

---

## Output Structure

When a reel is rendered, the pipeline produces a self-contained folder:
```
reels_output/export/
├── 01_Viral_Clip.mp4        # Rendered 1080x1920 vertical video
├── 01_Viral_Clip.ass        # High-readability styled karaoke subtitles
├── cuts.json                # Execution manifest
├── transcript.json          # Word-level Whisper timestamps
├── qa.json                  # Automated FFprobe verification report
├── render_report.json       # Encoding stats & timings
└── posting.md               # Social title, caption, and hashtags ready to copy
```

---

## License

MIT License. Free to use and customize.
