# Video to Instagram Reels ? Project Brain

## Purpose

Give Codex a video and invoke `$video-to-reels` to receive edited vertical MP4 reels, suggested post captions and hashtags, and a record of the selected source moments. The skill works across gaming, interviews, tutorials, podcasts, vlogs, events and other footage through content-aware editorial decisions. The helper does not independently understand or rank all video content: Codex reviews the source and selects moments, then uses deterministic scripts to produce the exports.

## Use the skill

Installed skill: `C:/Users/rajat/.codex/skills/video-to-reels/SKILL.md`.

Editable project copy: [skills/video-to-reels/SKILL.md](skills/video-to-reels/SKILL.md).

Example request:

> $video-to-reels ? Is video se Instagram ke liye best reels banao: "D:/Videos/my-video.mp4". Clean cuts aur readable captions rakho.

Optional preferences can specify count, language, duration, framing or style. Without them, the skill chooses sensible defaults and carries the work through to exports. If the newly installed skill is not visible in the current session, start a fresh session or provide the SKILL.md path directly. It is not a standalone service or uploader.

## Default output

- A new source-specific folder with completed MP4 reels; original source and existing exports stay intact.
- 1080?1920, 30 fps, H.264/AAC and fast-start metadata. Lower resolution is possible when justified and disclosed.
- Up to 3?6 worthwhile, distinct moments for a long source, fewer for short/limited footage. Roughly 15?60 seconds where suitable, with variable durations based on the actual story.
- On-screen subtitles in the spoken language by default; translations only when requested. Reliable word timings get synchronized word highlighting; incomplete timings keep the full phrase static. Hindi/Hinglish uses multilingual transcription and an appropriate installed font.
- Optional accurate opening hooks, plus `posting.md` containing titles, post captions and relevant hashtags.
- `cuts.json`, caption ASS files, `render_report.json` and `qa.json` for reproducibility and technical validation. Visual/playback observations can be recorded in `review.md`.

## Editorial rules

1. Inspect the source and surrounding context before selecting moments. A loud section is not automatically a good reel.
2. Every reel needs enough context, meaningful development and an actual payoff. Do not end an action reel before the outcome or cut speech mid-word.
3. Keep qualifications and factual meaning. Correct important transcript names and numbers against the source; never invent inaudible content.
4. Preserve essential screen information. Fit gameplay, HUD, slides, screen recordings and groups unless a verified crop is better. Fixed cropping is not subject tracking.
5. Captions must be readable, accurate and clear of important source/UI regions. Use word timestamps for phrase grouping, not guessed word timing.
6. Prefer distinct reels. Reusing a reaction can be justified, but avoid producing multiple nearly identical clips just to fill a quota.
7. Check actual exports, not only source timestamps. Technical decode checks and editorial/audio review are different evidence.
8. Deliver files without unnecessary approval rounds. Publishing to Instagram requires a separate explicit request.

## Implementation

- [Skill instructions](skills/video-to-reels/SKILL.md)
- [Editing guide and manifest schema](skills/video-to-reels/references/editing-guide.md)
- [Reusable helper](skills/video-to-reels/scripts/reels.py)
- [UI metadata](skills/video-to-reels/agents/openai.yaml)

Helper commands:

```powershell
python skills/video-to-reels/scripts/reels.py analyze --video "INPUT.mp4" --out "OUTPUT/analysis"
python skills/video-to-reels/scripts/reels.py transcribe --video "INPUT.mp4" --out "OUTPUT/transcript.json"
# Moment detection (Zero API cost):
# Chat-driven: Twitch VODs, YouTube live streams, or offline chat JSON
python skills/video-to-reels/scripts/reels.py find-chat-spikes --chat "OUTPUT/chat.json" --out "OUTPUT/cuts.json" --subtitle-preset hormozi
# Audio/Transcript-driven: Heuristic speech density + excitement scoring
python skills/video-to-reels/scripts/reels.py suggest-moments --transcript "OUTPUT/transcript.json" --out "OUTPUT/cuts.json" --subtitle-preset hormozi
python skills/video-to-reels/scripts/reels.py detect-silence --video "INPUT.mp4" --noise-db -30 --min-duration 0.5
python skills/video-to-reels/scripts/reels.py render --video "INPUT.mp4" --manifest "OUTPUT/cuts.json" --out "OUTPUT/exports"
python skills/video-to-reels/scripts/reels.py verify --folder "OUTPUT/exports"
```

Dependencies: Python, imageio-ffmpeg / static-ffmpeg / system FFmpeg, Pillow, and either faster-whisper or openai-whisper for speech transcription. No paid account or external API is required by the helper.

The manifest supplies source-second ranges, framing, subtitles and optional hooks. Multiple ranges are concatenated with correctly remapped subtitle times. Safe output names, source bounds, dimensions, subtitle timing/types and output placement are validated; reused source ranges are warned about. Existing reel filenames are protected unless `--overwrite` is explicitly passed.

OpenShorts improvements integrated (Zero API Cost):
- Layout modes: `fit` (blurred background), `crop` (fixed offset or exact `crop_box: [x,y,w,h]`), `split`/`stacked` (vertical split for facecam + gameplay), and `pip` (picture-in-picture inset).
- Viral subtitle styling: Presets for `hormozi` (bold yellow highlight), `neon` (electric green), `classic` (clean white), and `boxed` (high-contrast translucent box). Supports `uppercase: true` and `subtitle_position` (`bottom`, `center`, `top`).
- Local moment scoring: Speech-density, excitement keyword matching and punctuation spike heuristics automatically draft candidate cuts from `transcript.json`.
- Silence detection: Native FFmpeg pause finder to tighten clip pacing.
- Cross-platform path handling: Seamless portability between Windows and macOS/Linux.

Audio normalization targets -16 LUFS and -1.5 dBTP; these are processing targets, not measured output claims. The helper supports phrase subtitles, synchronized word highlighting when transcript text matches word alignment, fit/blur layout, fixed crop, hooks and audio normalization. It does not implement automatic subject tracking, zoom choreography, external posting or automatic highlight ranking. Codex can use an available editor when a video needs those capabilities.

## Validation performed ? 16 November 2026

- Skill frontmatter/scaffold validator passed.
- Source analysis produced metadata and a timestamped contact sheet.
- Cached-model transcription produced segment and word timestamps from a speech sample.
- Captioned landscape footage rendered into a vertical fit composition; multiple source ranges joined into a 3.30-second export.
- Automatic phrase captions from a generated transcript rendered into a 4.80-second crop export.
- Silent portrait footage rendered at 1080?1920 for 2 seconds without inventing audio.
- Those three exports passed full FFmpeg decode checks; the automatic-caption export also passed target-duration validation.
- Sample fit captions, hook placement and silent portrait framing were visually inspected. Complete listening review, Hindi font rendering, the default multilingual model and a diverse collection of full-length genres were not tested.

Test artifacts: `skill_validation/`. Technical checks do not guarantee editorial quality, platform acceptance or viral performance. Conventional vertical export settings are used; no unverified current Instagram duration/upload-limit claim is made.

## Existing Bloons project

Source: `this spike factory got 10,000,000 pops... (Bloons TD Battles 2).mp4`, approximately 24m18s, 1280?720, 30 fps.

Existing analysis: `transcript.json` (561 segments) and `audio_energy.json`. The legacy transcript has recognition errors and no word timestamps. The audio energy file has 1,429 smoothed samples for a declared 1,458 seconds, with undocumented alignment; do not treat indices as precise timestamps.

Original fixed-duration exports: `reels_output/`.

Revised exports: [reels_output/improved/](reels_output/improved/), with exact source selections in [cuts.json](reels_output/improved/cuts.json):

| Reel | Source range | Duration | Focus |
|---|---|---|---|
| 01 Engineer Nerf Hook | 00:00?00:22.30 | 22.30s | Complete opening explanation |
| 02 DDT Threat / Overclock Decision | 11:08.32?11:45.16 | 36.84s | Threat and upgrade cost; not an actual DDT defense |
| 03 Ultraboost / Overclock Explained | 14:00.48?14:18.08 | 17.60s | Complete buff demonstration |
| 04 Five BADs / Panic Defense | 20:37.02?21:13.12 | 36.10s | Rush reveal and immediate response |
| 05 ZOMG Defense Payoff | 21:40.06?22:37.46 | 57.40s | Defense through first survival reaction |
| 06 Almost 10 Million Pops | 22:20.56?23:00.78 | 40.22s | Predicted defeat, survival and pop count |

These earlier revised reels are 720?1280 with no newly added captions/hooks. All six passed full decode checks. Reels 5 and 6 share some survival footage. Reel 6 says **almost** 10 million; a confirmed rage quit is not established. Full listening review and user approval were not recorded.

Historical notes, including the earlier competitor study and speculative roadmap, are archived in [docs/brain_legacy_2026-11-16.md](docs/brain_legacy_2026-11-16.md). They are not verified product/architecture facts or requirements for this generalized skill.
