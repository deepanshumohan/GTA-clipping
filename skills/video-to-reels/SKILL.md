---
name: video-to-reels
description: Turn a supplied video into edited Instagram-ready vertical reels with complete highlights, clean cuts, reviewed on-screen subtitles, and checked MP4 exports. Use for gaming, interviews, tutorials, podcasts, vlogs, events and other footage. Does not publish to social accounts.
---

# Video to Reels

Deliver edited MP4s, not just timestamps or advice. Read [the editing guide](references/editing-guide.md) for selection, framing and manifest details. Use `scripts/reels.py` for analysis, transcription, moment suggestion, silence detection, rendering and technical checks. The agent makes editorial choices; the script provides deterministic rendering and zero-cost local automation.

## Defaults

- Use the supplied video. Ask for it only if missing/inaccessible; resolve the source if several files are equally plausible.
- With no other direction, choose up to 3–6 distinct strong moments from a long video, fewer when material supports fewer. A short source may yield one reel. Aim roughly 15–60 seconds when appropriate; complete stories determine boundaries. Never pad to a quota or enforce 30 seconds.
- Supply short titles, suggested post captions and a few relevant hashtags.
- Default to 1080×1920, 30 fps, H.264/AAC MP4 with fast-start. Use 720×1280 when requested or justified by source quality/resources, and disclose it.
- Subtitle speech in every reel by default after reviewing the transcript. Choose from modern presets (`hormozi`, `neon`, `classic`, `boxed`) and support uppercase styling. Preserve the spoken language, including Hindi/Hinglish. Use synchronized word highlighting (karaoke style) when reliable word timestamps exist.
- Multiple layout options: `fit` (centered with blurred background), `crop` (fixed offset or exact `crop_box`), `split`/`stacked` (vertical split for facecam + gameplay or dual speakers), and `pip` (picture-in-picture facecam inset).
- Save under `reels_output/<video_name>/` (or the supplied destination); for multiple inputs, make one folder per source. Sanitize names, preserve sources and previous exports, and never overwrite an existing export without checking it. Exporting is authorized; publishing requires explicit instruction.

## Completion standard

The task is complete only when each selected reel has a playable MP4, reviewed burned-in subtitles when speech is present, a short title, paste-ready post caption and relevant hashtags, plus technical QA. Include source time ranges and an editorial/audio/visual review in `review.md`. Provide direct links to every MP4 and `posting.md`, `qa.json`, and `review.md`.

## Workflow

1. **Analyze**: Run `analyze` to inspect source duration, dimensions, frame rate, audio, contact sheets, and screen regions.
2. **Transcribe**: Run `transcribe` unless an accurate transcript exists (uses local Whisper with word timestamps and VAD).
3. **Auto-Suggest Moments (Optional & Zero-Cost)**: Run `suggest-moments` to generate an initial draft of high-energy candidate cuts based on speech density and excitement keywords.
4. **Detect Silences (Optional)**: Run `detect-silence` to find dead-air pauses and tighten reel pacing.
5. **Curate & Refine (`cuts.json`)**: Refine cuts into complete mini-stories (hook → development → payoff). Select layout (`fit`, `crop`, `split`, `pip`) and subtitle preset (`hormozi`, `neon`, `classic`, `boxed`).
6. **Render & Verify**: Run `render`, then inspect exports and run `verify` for technical decode checks.
7. **Post Captions**: Prepare `posting.md` with paste-ready captions, titles, and hashtags.

## Commands

Paths below are relative to this skill directory. Quote paths containing spaces.

```powershell
python scripts/reels.py analyze --video "INPUT.mp4" --out "OUTPUT/analysis"
python scripts/reels.py transcribe --video "INPUT.mp4" --out "OUTPUT/transcript.json"
# Moment detection options (both zero-cost):
# Option A: Chat-driven (Twitch / YouTube / offline chat logs)
python scripts/reels.py find-chat-spikes --chat "chat.json" --out "OUTPUT/cuts.json" --subtitle-preset hormozi
# Option B: Heuristic audio energy + transcript density
python scripts/reels.py suggest-moments --transcript "OUTPUT/transcript.json" --out "OUTPUT/cuts.json" --subtitle-preset hormozi
python scripts/reels.py detect-silence --video "INPUT.mp4" --noise-db -30 --min-duration 0.5
python scripts/reels.py render --video "INPUT.mp4" --manifest "OUTPUT/cuts.json" --out "OUTPUT/exports"
python scripts/reels.py verify --folder "OUTPUT/exports"
```

Use subcommand `--help` for options. Dependencies: Python, `imageio-ffmpeg` or system FFmpeg, `Pillow`; transcription needs either `faster-whisper` or `openai-whisper`. A system FFmpeg or `FFMPEG_BINARY` overrides bundled FFmpeg. No external paid service or cloud API is required.
