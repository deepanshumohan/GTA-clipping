# Project Brain: GTA & Automated Video Reel Engine

## 1. Executive Summary & Project Context
This project workspace (`d:\git\gta`) is focused on automated short-form video generation, analysis of viral clipping workflows (specifically reverse-engineering tools like **Vice Cuts**), and executing end-to-end automated clip extraction from raw gaming footage.

---

## 2. Benchmark Case Study: Vice Cuts (`vicecuts.com`)

### 2.1 Product Philosophy
Vice Cuts is a specialized AI video clipping and automated editing SaaS tailored for *Grand Theft Auto VI* (and GTA V) content creators, designed around the core loop: **Paste. Pick. Post.**

Unlike generic AI clipping platforms (such as Opus Clip, Klap, or Submagic) that focus primarily on talking-head podcasts, Vice Cuts focuses entirely on **in-game events, visual HUD cues, and cultural game aesthetics**.

### 2.2 Core Workflow Pipeline
1. **Input (Paste):** Stream URL (YouTube, Twitch, Kick) or direct video file upload.
2. **AI Moment Detection (The Tape):** Multi-modal frame analysis and speech transcription detect critical game events (chases, shootouts, wanted star climbs, fails, mission wins).
3. **The Map & Route UI:** The full video timeline is rendered as a GTA GPS route where each highlighted moment is an interactive "blip" (checkpoint).
4. **The Weapon Wheel (Jobs):** Video styling presets formatted in GTA's iconic weapon-selection wheel:
   - **Mission Passed (`mission`):** Outro sequence featuring mission passed screen, 5 stars, and 'Respect +' audio.
   - **Wanted Hook (`wanted`):** Intro hook showing wanted stars climbing alongside action highlights.
   - **Trailer Cut (`trailer`):** Freeze-frame character cards with custom typography ("Starring You").
   - **Radio (`radio`):** In-game radio wheel HUD animation and track name overlay.
   - **News Ticker (`news`):** *Weazel News* lower-third breaking news ticker.
   - **Cutscene Subs (`subs`):** Voice commentary turned into authentic in-game dialogue subtitles.
   - **Cash Counter (`cash`):** Real-time heist cash counter and payout split.
   - **Wasted (`wasted`):** Classic slow-motion desaturated "Wasted" screen for fails.
   - **Waypoint (`waypoint`):** Integrated GPS minimap route tracking.
5. **Polishing & Export:** 9:16 vertical smart crop, custom GTA color grading (Vice, Dusk, Teal, Night), authentic SFX, and export.

### 2.3 Technical Architecture & Stack
- **Frontend:** Vanilla JS, WebGL / HTML5 Canvas route engine, responsive web UI.
- **Backend Infrastructure:** Railway / Netlify hosting headless rendering jobs (`render.mjs`, FFmpeg, WebCodecs).
- **AI Layer:** Anthropic Claude Vision + Whisper for visual frame recognition, HUD parsing, and captioning.
- **Database & Auth:** Supabase (PostgreSQL, Auth, Storage).
- **Billing & Subscriptions:** Stripe Checkout with credit "run" model ($20 for 60 runs, $49 for 200 runs, $99 for 500 runs) + Rewardful affiliate system.

---

## 3. Source Footage Analysis: Bloons TD Battles 2

### 3.1 Media Specification
- **File Name:** `this spike factory got 10,000,000 pops... (Bloons TD Battles 2).mp4`
- **File Location:** `d:\git\gta\this spike factory got 10,000,000 pops... (Bloons TD Battles 2).mp4`
- **Duration:** 24 minutes, 18.19 seconds (1458.19 seconds)
- **Container / Video Codec:** MP4 / H.264 (Main) @ 2,121 kb/s
- **Resolution & Frame Rate:** 1280×720 (16:9), 30 fps progressive
- **Audio Codec:** AAC LC stereo @ 128 kb/s, 44.1 kHz

### 3.2 Signal & Content Extraction Metrics
- **Mean Volume:** -19.1 dB | **Peak Volume:** 0.0 dB
- **Transcription Model:** Faster-Whisper (`tiny.en`, int8 CPU execution)
- **Total Transcribed Dialogue Segments:** 561
- **Key Peaks Detected:**
  - `00:04 - 00:34`: Update meta explanation & strategy setup.
  - `11:04 - 11:34`: Round 26 fast DDT bloons arrival & defense calculation.
  - `14:03 - 14:33`: Ultra Boost stacking on Spike Factory for Round 30 B.A.D.
  - `20:36 - 21:06`: 5 B.A.D. Bloons all-out offensive rush by opponent.
  - `21:35 - 22:05`: Screen-wide ZOMG wave shredding & panic defense.
  - `22:32 - 23:02`: **10 Million Pops milestone** and opponent rage-quit.

---

## 4. Extracted Reels Catalog (9:16 Vertical Cuts)

All clips are rendered to `d:\git\gta\reels_output\` using high-quality H.264 encoding with a dual-layer vertical filter (centered sharp 16:9 gameplay with matching blurred-atmosphere background):

| Reel File | Timestamp | Duration | Core Highlight |
|---|---|---|---|
| `Reel_01_Engineer_Nerf_Strategy_Hook.mp4` | `00:04 - 00:34` | 30.0s | Overclock nerf explanation & match kickoff hook |
| `Reel_02_Round26_DDT_Defense.mp4` | `11:04 - 11:34` | 30.0s | Fast DDT bloon threat & $13.5k overclock dilemma |
| `Reel_03_UltraBoost_Round30_BAD.mp4` | `14:03 - 14:33` | 30.0s | Ultra Boost + Overclock stacking on Spike Factory |
| `Reel_04_Mega_5_BADs_Rush.mp4` | `20:36 - 21:06` | 30.0s | Opponent sells farms for a terrifying 5-B.A.D. rush |
| `Reel_05_ZOMG_Shredding_Chaos.mp4` | `21:35 - 22:05` | 30.0s | Massive ZOMG swarm defense ("We are shredding!") |
| `Reel_06_10Million_Pops_Climax.mp4` | `22:32 - 23:02` | 30.0s | **The Title Climax:** 10M Pops + Opponent Rage Quit |

---

## 5. Reel Improvement Roadmap: How to Make These Go Viral

To elevate raw 30-second clips into high-retention, viral short-form assets, follow this 5-stage enhancement blueprint:

### 1. Dynamic Animated Subtitles (The "Hook & Caption" Effect)
- **Problem:** Over 60% of short-form viewers watch without sound or decide whether to stay within the first 1.5 seconds.
- **Solution:** Add word-by-word highlighted captions (Alex Hormozi / MrBeast style).
- **Implementation:**
  - Generate precise word-level timestamps using Whisper (`word_timestamps=True`).
  - Render with high-contrast fonts (e.g., *Komika Axis*, *Montserrat ExtraBold*, or *The Bold Font*).
  - Highlight current words in bright yellow (`#FFE600`) or lime green (`#00FF66`) with black text borders.

### 2. Top Banner Hook (Title Card)
- **Problem:** Viewers need immediate context on what they are watching.
- **Solution:** Add a bold, punchy headline in the top blurred third:
  - *Reel 1:* "THEY NERFED OVERCLOCK?! 😳"
  - *Reel 4:* "HE SENT 5 B.A.D. BLOONS AT ONCE!! 😱"
  - *Reel 6:* "10,000,000 POPS ON ONE TOWER?! 🤯"

### 3. Dynamic Camera Moves (Punch-Ins & Zoom Cuts)
- **Problem:** Static gameplay video can cause retention drop-offs after 4–5 seconds.
- **Solution:**
  - **Punch-in (1.25x zoom)** whenever the commentator yells or reacts ("Holy crap!", "Wait guys!").
  - **Pan/Focus zoom** towards the pop counter or the bottom-track spike pile when bloons approach the exit.
  - Quick shake / impact effect when B.A.D. bloons pop into ZOMGs.

### 4. Audio Sweetening & SFX Layering
- **Game Sound / Voice Balance:** Compress speech audio with slight ducking on the game soundtrack so commentary is crystal clear.
- **Micro-SFX:**
  - *Whoosh / Swish* on text pop-ups.
  - *Vine Boom / Bass Drop* when the 5 B.A.D. rush appears on screen.
  - *Bell ding / Cash register sound* when pop milestones cross 1M, 5M, 10M.

### 5. Call-To-Action & Loop Outro
- Trim the final 0.5 seconds to seamlessly loop back to the opening word for maximum repeat views (boosting algorithm watch-time metrics).

---

## 6. Automated Pipeline Architecture for Scale

```
[Raw Stream / Video]
        │
        ▼
[Audio Demux & Faster-Whisper] ──► [Energy & Keyword Analyzer]
                                            │
                                            ▼
                               [Top 30s Moments Selected]
                                            │
                                            ▼
                       [FFmpeg Engine: 9:16 Composite Filter]
                       ├── Background: Scaled, Cropped & Blurred
                       ├── Foreground: Crisp 16:9 Gameplay
                       ├── Overlay: Top Hook Card
                       └── Subtitles: Dynamic ASS/SRT Burn
                                            │
                                            ▼
                                 [Viral Ready Reels]
```

This pipeline allows converting any hours-long gaming VOD or stream into 5–10 platform-ready vertical clips fully automatically within 1–2 minutes.



## 7. Improved Reel Cuts ? 16 November 2026

User direction: improve the existing reel cuts, with complete dialogue and better moment boundaries. The revised exports below supersede the fixed 30-second cuts in Section 4 for review. Original exports remain unchanged in `reels_output/`.

**Current outputs:** `reels_output/improved/`  
**Exact cut manifest:** `reels_output/improved/cuts.json`  
**Preview contact sheet:** `reels_output/improved/preview.jpg`

| Improved export | Source in ? out | Target duration | Cut decision |
|---|---|---|---|
| `Reel_01_Engineer_Nerf_Hook.mp4` | 00:00.00 ? 00:22.30 | 22.30s | Complete opening explanation and lets-find-out ending; excludes repeated introduction. |
| `Reel_02_DDT_Threat_Overclock_Decision.mp4` | 11:08.32 ? 11:45.16 | 36.84s | Starts at Round 26 DDT context and includes the complete overclock cost explanation. |
| `Reel_03_Ultraboost_Overclock_Explained.mp4` | 14:00.48 ? 14:18.08 | 17.60s | Complete buff demonstration; ends before unrelated Round 30 discussion. |
| `Reel_04_Five_BADs_Panic_Defense.mp4` | 20:37.02 ? 21:13.12 | 36.10s | Begins with preparation, includes five BAD reveal and panic response; ends after defensive placement instruction. |
| `Reel_05_ZOMG_Defense_Payoff.mp4` | 21:40.06 ? 22:37.46 | 57.40s | Keeps the continuous defense through its first surprised survival reaction. |
| `Reel_06_Almost_10Million_Pops.mp4` | 22:20.56 ? 23:00.78 | 40.22s | Includes predicted defeat, survival reaction and almost-ten-million pop count; avoids unsupported rage-quit claim. |

### Export and verification

- All six revised MP4s were rendered from the original source at 720?1280, 30 fps, H.264 with AAC audio and fast-start metadata.
- The full landscape composition, including gameplay and facecam, is retained over a blurred vertical background.
- All six completed exports passed a full FFmpeg video/audio decode check without reported errors. Encoded duration can differ from target by approximately one frame.
- Source frames and a partial export contact sheet were inspected visually. Complete real-time playback/audio listening and user approval have not been recorded.
- These are revised cuts, without newly added captions, hook banners, sound effects, or camera animation. The enhancement ideas in Section 5 remain proposals.
- Reels 5 and 6 intentionally share part of the survival sequence: Reel 5 follows the defense, while Reel 6 focuses on predicted defeat, the reaction and pop-count commentary.
- Reel 4 covers the rush reveal and immediate defensive response; the full survival outcome is in Reels 5 and 6.

### Corrections and project limitations

- Reel 2 covers a potential DDT threat and an overclock decision; an actual DDT defense is not established by the selected dialogue.
- Reel 3 demonstrates Ultra Boost/Overclock behavior; it does not establish a Round 30 BAD defense.
- Reel 6 says **almost 10 million pops**. The revised cut makes no confirmed rage-quit claim.
- `transcript.json` has 561 segment-level entries and visible recognition errors. It has not been corrected and does not contain word-level timestamps.
- `audio_energy.json` declares 1,458 seconds but contains 1,429 smoothed samples. The smoothing window and time alignment are undocumented; the revised cuts were selected using transcript boundaries rather than assuming sample indices are exact source seconds.
- No reusable rendering pipeline script or application code is present in the workspace. `cuts.json` records the revised selection, but is not itself a complete rendering pipeline.
- Competitor architecture, pricing, processing-speed and retention claims in earlier sections are historical planning notes, not verified findings from this revision.
