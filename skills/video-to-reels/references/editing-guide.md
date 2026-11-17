# Selection, layout and manifest

## Content decisions

Gaming: keep threat, response and actual outcome together; preserve relevant HUD/minimap/facecam. A future threat is not an actual defense. Commentary alone does not confirm a rage quit.

Interviews/podcasts: a clear claim plus explanation/example. Preserve qualifications; avoid deceptive quote splicing. Supply enough context for answers that depend on a question.

Tutorials/screen recordings: problem, essential steps, result. Controls/text must be readable; fitting everything is not sufficient if it is too small. Use a custom panel layout in an editor when necessary.

Vlogs/events/sport: setup, action, reaction. Preserve decisive actions, including meaningful quiet footage. Music clips should respect musical phrases.

The original Bloons example used fixed 30-second cuts that lost context/payoff. Learn the editorial lesson; do not reuse its timestamps, six-clip quota or gaming hooks for arbitrary videos.

## Framing and layouts

1. **`fit` (Default)**: Preserves the entire video aspect ratio centered over a blurred background. Best for wide gameplay, HUD, slides, or group shots.
2. **`crop`**:
   - Fixed center offset with `crop_x: 0.5` (0 = left edge, 1 = right edge).
   - Custom region with `crop_box: [x, y, w, h]` (normalized 0–1) to focus on a specific area of the screen.
3. **`split` / `stacked`**: Stacks two views vertically in a 9:16 frame.
   - `split_ratio`: Ratio for the top pane (default `0.5`).
   - `top_crop_x`: Horizontal crop offset for the top pane.
   - `bottom_layout`: `"fit"` (default) or `"crop"`.
   - Perfect for gaming videos with facecams (facecam on top, gameplay on bottom) or two-person interviews!
4. **`pip`**: Picture-in-picture facecam inset box overlay.
   - `pip_position`: `"top-right"` (default), `"top-left"`, `"bottom-right"`, or `"bottom-left"`.
   - `pip_scale`: Inset scale relative to canvas width (default `0.35`).

## Subtitle styles and presets

The renderer supports modern short-form subtitle styles inspired by high-retention formats:
- **`subtitle_preset: "hormozi"`**: Bold, punchy yellow highlight (`&H0000FFFF`), white inactive text, thick black border, and drop shadow. Best for high-energy shorts.
- **`subtitle_preset: "neon"`**: Electric neon-green highlight (`&H0000FF00`), white inactive text, clean dark outline.
- **`subtitle_preset: "classic"`**: Clean white text with subtle shadow.
- **`subtitle_preset: "boxed"`**: Translucent dark background box (`&H99101010`) behind text for maximum legibility over fast-moving backgrounds.
- **`uppercase: true`**: Automatically capitalizes all subtitle and hook words.
- **`subtitle_position`**: `"bottom"` (default near y=1440), `"center"` (y=960 for TikTok center-screen style), or `"top"`.

On-screen subtitles should use short phrase groups, usually 3–7 words and no more than two lines. Preserve the spoken language by default. When reliable word timestamps match the recognized phrase, the helper highlights spoken words in karaoke style. Set `highlight_words: false` on a reel to disable highlighting.

## Manifest schema

```json
{
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "transcript": "transcript.json",
  "font": "Arial",
  "normalize_audio": true,
  "reels": [{
    "name": "01_viral_moment",
    "title": "An accurate short title",
    "reason": "Why the moment is complete and worth sharing",
    "ranges": [[440.0, 475.6]],
    "layout": "fit",
    "crop_x": 0.5,
    "subtitle_preset": "hormozi",
    "uppercase": true,
    "subtitle_position": "bottom",
    "hook": "WAIT FOR THE END!",
    "hook_seconds": 3,
    "burn_captions": true,
    "highlight_words": true,
    "post_caption": "A concise post description grounded in this clip.",
    "hashtags": ["#Shorts", "#Reels", "#Gaming"],
    "captions": [{"start": 440.0, "end": 444.0, "text": "Reviewed caption text"}]
  }]
}
```

## Zero-cost automation commands

### 1. Chat-Driven Moment Finding (Twitch, YouTube, & Offline)
When chat explodes with "LMAO", "KEKW", or "CLIP IT", that burst marks a viral moment. The tool compares message volume against a 5-minute rolling baseline to find spikes louder than normal, starting each clip 20s before the spike and ending 10s after.

```bash
# Analyze chat spikes from Twitch, YouTube, or generic chat JSON:
python scripts/reels.py find-chat-spikes --chat "chat.json" --out "cuts.json" --subtitle-preset hormozi --top 5

# How to download chat logs (Zero API costs):
# Twitch VOD:
./TwitchDownloaderCLI chatdownload --id <VOD_URL_OR_ID> -o chat.json

# YouTube Stream / VOD:
yt-dlp --skip-download --write-subs --sub-langs live_chat "<YOUTUBE_URL>"
# Produces <filename>.live_chat.json, which can be passed directly to --chat!
```

### 2. Speech Density & Audio Energy Moment Finding
When no chat log is available (e.g. offline video or edited gameplay), scan the Whisper transcript and audio energy for peak engagement:

```bash
python scripts/reels.py suggest-moments --transcript "transcript.json" --out "cuts.json" --subtitle-preset hormozi
```

### 3. Silence Detection
Detect dead-air pauses and silences to tighten clip pacing:

```bash
python scripts/reels.py detect-silence --video "INPUT.mp4" --noise-db -30 --min-duration 0.5
```

## Quality evidence

`verify` fully decodes audio/video and measures dimensions, duration and frame rate; it records audio presence. This does not prove subtitle accuracy, editorial quality, audio/video sync, perceived loudness or platform acceptance. Record the evidence separately in `review.md`.
