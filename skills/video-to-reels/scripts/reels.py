"""Agent-assisted reel production. Editorial selections are supplied in a manifest.
Enhanced with OpenShorts-inspired local features:
- Smart Layouts: fit, crop (with custom crop_box), split (stacked), pip (picture-in-picture)
- Modern Subtitle Presets: hormozi, neon, classic, boxed, uppercase mode, positioning
- Local Moment Suggestion: heuristic speech-density + excitement scoring (Zero API cost)
- Silence Detection: FFmpeg-based dead-air finder
"""
import argparse
import io
import json
import math
import os
import re
import shutil
import subprocess
import warnings
from pathlib import Path


def ffmpeg():
    custom = os.environ.get('FFMPEG_BINARY') or shutil.which('ffmpeg')
    if custom:
        return custom
    # Check static_ffmpeg install locations (macOS/Linux/Windows)
    home = Path.home()
    candidates = list((home / "Library/Python").glob("*/lib/python/site-packages/static_ffmpeg/bin/*/ffmpeg"))
    if not candidates:
        candidates = list((home / ".local/lib").glob("python*/site-packages/static_ffmpeg/bin/*/ffmpeg"))
    if candidates and candidates[0].exists():
        return str(candidates[0])
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return 'ffmpeg'


def ffprobe():
    custom = os.environ.get('FFPROBE_BINARY') or shutil.which('ffprobe')
    if custom:
        return custom
    home = Path.home()
    candidates = list((home / "Library/Python").glob("*/lib/python/site-packages/static_ffmpeg/bin/*/ffprobe"))
    if not candidates:
        candidates = list((home / ".local/lib").glob("python*/site-packages/static_ffmpeg/bin/*/ffprobe"))
    if candidates and candidates[0].exists():
        return str(candidates[0])
    return 'ffprobe'


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def probe(video):
    # Try ffprobe first for robust metadata without depending on cv2
    try:
        probe_bin = ffprobe()
        cmd = [probe_bin, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(video)]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        vstream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        has_audio = any(s.get('codec_type') == 'audio' for s in data.get('streams', []))
        if vstream:
            fps_parts = str(vstream.get('r_frame_rate', '30/1')).split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) != 0 else 30.0
            duration = float(data.get('format', {}).get('duration') or vstream.get('duration') or 0)
            frames = int(vstream.get('nb_frames') or round(duration * fps))
            return dict(
                source=str(Path(video).resolve()),
                width=int(vstream['width']),
                height=int(vstream['height']),
                fps=fps,
                frames=frames,
                duration=duration,
                has_audio=has_audio,
                stream_details=json.dumps(data.get('streams', []), indent=2)
            )
    except Exception:
        pass

    # Fallback to cv2 + ffmpeg banner inspection
    try:
        import cv2
        c = cv2.VideoCapture(str(video))
        if not c.isOpened():
            raise ValueError(f'Cannot open video: {video}')
        fps, count = c.get(cv2.CAP_PROP_FPS), c.get(cv2.CAP_PROP_FRAME_COUNT)
        info = dict(source=str(Path(video).resolve()), width=int(c.get(3)), height=int(c.get(4)),
                    fps=fps, frames=int(count), duration=count / fps if fps else 0)
        c.release()
    except ImportError:
        info = dict(source=str(Path(video).resolve()), width=0, height=0, fps=30.0, frames=0, duration=0)

    p = subprocess.run([ffmpeg(), '-hide_banner', '-i', str(video)], capture_output=True, text=True, errors='replace')
    info['has_audio'] = bool(re.search(r'Stream #.*Audio:', p.stderr))
    info['stream_details'] = p.stderr
    duration = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', p.stderr)
    if duration:
        h, minutes, seconds = map(float, duration.groups())
        info['duration'] = h * 3600 + minutes * 60 + seconds
    dim = re.search(r'Video:.*,\s*(\d{2,5})x(\d{2,5})', p.stderr)
    if dim and (not info.get('width') or not info.get('height')):
        info['width'], info['height'] = int(dim.group(1)), int(dim.group(2))
    if not info.get('duration') or not info.get('width') or not info.get('height'):
        raise ValueError('Could not determine video dimensions and duration')
    return info


def analyze(args):
    from PIL import Image, ImageDraw
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    info = probe(args.video)
    save(out / 'media.json', info)
    
    n = min(args.samples, max(1, math.ceil(info['duration'] / 2)))
    times = [i * max(0, info['duration'] - .2) / max(1, n - 1) for i in range(n)]
    
    # Try cv2 first, fallback to ffmpeg pipe
    has_cv2 = False
    try:
        import cv2
        c = cv2.VideoCapture(str(args.video))
        has_cv2 = c.isOpened()
    except ImportError:
        has_cv2 = False

    ff_bin = ffmpeg()

    for page in range(math.ceil(n / 24)):
        batch = times[page * 24:(page + 1) * 24]
        sheet = Image.new('RGB', (1280, math.ceil(len(batch) / 4) * 205), '#181818')
        draw = ImageDraw.Draw(sheet)
        for i, t in enumerate(batch):
            im = None
            if has_cv2:
                c.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ok, frame = c.read()
                if ok:
                    im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if im is None:
                # ffmpeg frame extraction fallback
                proc = subprocess.run(
                    [ff_bin, '-ss', str(t), '-i', str(args.video), '-vframes', '1', '-f', 'image2', '-c:v', 'mjpeg', 'pipe:1'],
                    capture_output=True
                )
                if proc.stdout:
                    try:
                        im = Image.open(io.BytesIO(proc.stdout))
                    except Exception:
                        im = None
            if im is None:
                continue
            im.thumbnail((320, 180))
            x, y = i % 4 * 320, i // 4 * 205
            sheet.paste(im, (x + (320 - im.width) // 2, y + 25))
            draw.text((x + 8, y + 5), f'{int(t // 60):02}:{t % 60:05.2f}', fill='white')
        sheet.save(out / f'contact_{page + 1:02}.jpg', quality=88)
        
    if has_cv2:
        c.release()
    print(json.dumps({k: v for k, v in info.items() if k != 'stream_details'}, indent=2))


def ensure_ffmpeg_on_path():
    ff = ffmpeg()
    ff_dir = str(Path(ff).parent)
    if ff_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = f"{ff_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def detect_hardware_encoder():
    """Detects best available FFmpeg encoder (h264_nvenc, h264_videotoolbox, h264_qsv, libx264)."""
    # Test h264_nvenc (NVIDIA) - require >=256x256 test canvas
    try:
        res = subprocess.run([
            ffmpeg(), '-v', 'quiet', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1',
            '-c:v', 'h264_nvenc', '-f', 'null', '-'
        ], capture_output=True, timeout=3)
        if res.returncode == 0:
            return 'h264_nvenc'
    except Exception:
        pass
    # Test videotoolbox (macOS)
    try:
        res = subprocess.run([
            ffmpeg(), '-v', 'quiet', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1',
            '-c:v', 'h264_videotoolbox', '-f', 'null', '-'
        ], capture_output=True, timeout=3)
        if res.returncode == 0:
            return 'h264_videotoolbox'
    except Exception:
        pass
    # Test qsv (Intel)
    try:
        res = subprocess.run([
            ffmpeg(), '-v', 'quiet', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1',
            '-c:v', 'h264_qsv', '-f', 'null', '-'
        ], capture_output=True, timeout=3)
        if res.returncode == 0:
            return 'h264_qsv'
    except Exception:
        pass
    return 'libx264'


def transcribe(args):
    if not probe(args.video)['has_audio']:
        raise ValueError('No audio stream; use visual selection without captions')
    ensure_ffmpeg_on_path()
    import ssl
    try:
        import certifi
        ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ssl._create_default_https_context = ssl._create_unverified_context

    device = getattr(args, 'device', 'auto')
    compute_type = getattr(args, 'compute_type', 'auto')
    if device == 'auto':
        try:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        except Exception:
            device = 'cpu'
    if compute_type == 'auto':
        compute_type = 'float16' if device == 'cuda' else 'int8'

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        try:
            import whisper
        except ImportError as e:
            raise RuntimeError('Install faster-whisper or openai-whisper to transcribe speech') from e
        model = whisper.load_model(args.model, device=device)
        decoded = model.transcribe(str(args.video), language=args.language, word_timestamps=True,
                                   fp16=device != 'cpu', verbose=False)
        result = {'source': str(Path(args.video).resolve()), 'language': decoded.get('language'),
                  'language_probability': None, 'model': f'openai-whisper-{args.model}', 'segments': []}
        for s in decoded['segments']:
            if s['end'] <= s['start']:
                continue
            result['segments'].append(dict(start=s['start'], end=s['end'], text=s['text'].strip(),
                words=[dict(start=w['start'], end=w['end'], word=w['word'])
                       for w in s.get('words', []) if w.get('start') is not None and w.get('end') is not None
                       and w['end'] > w['start']]))
    else:
        model = WhisperModel(args.model, device=device, compute_type=compute_type)
        segments, info = model.transcribe(str(args.video), language=args.language,
                                          word_timestamps=True, vad_filter=True, beam_size=5)
        result = {'source': str(Path(args.video).resolve()), 'language': info.language,
                  'language_probability': info.language_probability, 'model': args.model, 'segments': []}
        for s in segments:
            if s.end <= s.start:
                continue
            result['segments'].append(dict(start=s.start, end=s.end, text=s.text.strip(),
                words=[dict(start=w.start, end=w.end, word=w.word)
                       for w in (s.words or []) if w.end is not None and w.start is not None and w.end > w.start]))
    save(args.out, result)
    print(f"Saved {len(result['segments'])} segments: {args.out}")


def caption_tokens(text):
    return re.findall(r"\w+(?:['’]\w+)*", str(text).casefold(), flags=re.UNICODE)


def word_alignment_matches(text, words, start=None, end=None):
    if caption_tokens(text) != caption_tokens(' '.join(str(w.get('word', '')) for w in words)):
        return False
    previous_start = None
    for word in words:
        a, b = word.get('start'), word.get('end')
        if not isinstance(a, (int, float)) or isinstance(a, bool) or not math.isfinite(a):
            return False
        if not isinstance(b, (int, float)) or isinstance(b, bool) or not math.isfinite(b) or a >= b:
            return False
        if start is not None and a < start - .1:
            return False
        if end is not None and b > end + .1:
            return False
        if previous_start is not None and a < previous_start:
            return False
        previous_start = a
    return True


def phrases(transcript, max_words=None):
    segments = transcript.get('segments', []) if isinstance(transcript, dict) else transcript
    result = []
    limit = int(max_words) if max_words and int(max_words) > 0 else 6
    for s in segments:
        words = s.get('words', [])
        if not words:
            result.append({k: s[k] for k in ('start', 'end', 'text')})
            continue
        if not word_alignment_matches(s.get('text', ''), words, s.get('start'), s.get('end')):
            result.append({k: s[k] for k in ('start', 'end', 'text')})
            continue
        group = []
        for w in words:
            group.append(w)
            length = len(' '.join(x['word'].strip() for x in group))
            if len(group) >= limit or (max_words is None and (length >= 35 or re.search(r'[.!?।]$', w['word'].strip()))):
                result.append(dict(start=group[0]['start'], end=group[-1]['end'],
                                   text=' '.join(x['word'].strip() for x in group), words=group.copy()))
                group = []
        if group:
            result.append(dict(start=group[0]['start'], end=group[-1]['end'],
                               text=' '.join(x['word'].strip() for x in group), words=group.copy()))
    return result


def ass_time(seconds):
    cs = round(seconds * 100)
    return f'{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}'


def ass_text(text):
    return str(text).replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\r', '').replace('\n', r'\N')


def build_ass_style(preset, font, width, height, custom_opts=None):
    """Generates ASS styling based on presets: hormozi, neon, classic, boxed, or default."""
    custom_opts = custom_opts or {}
    preset = str(preset or 'default').lower()
    
    font_size = custom_opts.get('font_size') or round(width * 0.052)
    margin_l = custom_opts.get('margin_l') or round(width * 0.10)
    margin_r = custom_opts.get('margin_r') or round(width * 0.10)
    
    # Vertical position: bottom (default), center, top
    pos = str(custom_opts.get('position', 'bottom')).lower()
    if pos == 'center':
        margin_v = round(height * 0.48)
    elif pos == 'top':
        margin_v = round(height * 0.75)
    else:
        margin_v = custom_opts.get('margin_v') or round(height * 0.25)

    highlight = custom_opts.get('highlight_words', True)
    # Presets definition in ASS BGR colors (&H00BBGGRR)
    if preset in ('hormozi', 'yellow_shadow', 'yellow'):
        primary = custom_opts.get('primary_color') or '&H0000FFFF'    # Bright Vivid Yellow
        secondary = custom_opts.get('secondary_color') or ('&H00FFFFFF' if highlight else '&H0000FFFF')
        outline_col = custom_opts.get('outline_color') or '&H00000000'# Solid Pitch Black
        back_col = '&H00000000'                                      # Solid Pitch Black Shadow (100% opaque)
        bold = -1
        outline = 5                                                  # High-contrast 5px outline
        shadow = 4                                                   # Deep 4px drop shadow for ultra readability
        border_style = 1
    elif preset == 'neon':
        primary = custom_opts.get('primary_color') or '&H0000FF00'    # Neon Green
        secondary = custom_opts.get('secondary_color') or '&H00FFFFFF'# White
        outline_col = custom_opts.get('outline_color') or '&H00000000'
        back_col = '&H80000000'
        bold = -1
        outline = 4
        shadow = 1
        border_style = 1
    elif preset == 'classic':
        primary = custom_opts.get('primary_color') or '&H00FFFFFF'    # White
        secondary = custom_opts.get('secondary_color') or '&H00C0C0C0'# Light Gray
        outline_col = custom_opts.get('outline_color') or '&H00151515'
        back_col = '&H80000000'
        bold = -1
        outline = 3
        shadow = 1
        border_style = 1
    elif preset == 'boxed':
        primary = custom_opts.get('primary_color') or '&H0000FFFF'
        secondary = custom_opts.get('secondary_color') or '&H00FFFFFF'
        outline_col = '&H00000000'
        back_col = '&H99101010'  # Semi-transparent box
        bold = -1
        outline = 0
        shadow = 0
        border_style = 3  # Opaque box
    else:
        primary = custom_opts.get('primary_color') or '&H0000FFFF'
        secondary = custom_opts.get('secondary_color') or '&H00FFFFFF'
        outline_col = custom_opts.get('outline_color') or '&H00101010'
        back_col = '&H80000000'
        bold = -1
        outline = max(2, round(width * 0.004))
        shadow = 1
        border_style = 1

    caption_line = (
        f"Style: Caption,{font},{font_size},{primary},{secondary},{outline_col},{back_col},"
        f"{bold},0,0,0,100,100,0,0,{border_style},{outline},{shadow},2,"
        f"{margin_l},{margin_r},{margin_v},1"
    )
    hook_size = round(width * 0.055)
    hook_v = round(height * 0.13)
    hook_line = (
        f"Style: Hook,{font},{hook_size},&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,5,4,8,"
        f"{margin_l},{margin_r},{hook_v},1"
    )
    return caption_line, hook_line


def get_sentiment_emoji(text):
    low = text.lower()
    if any(k in low for k in ('scare', 'scream', 'jumpscare', 'spooky', 'horror', 'terrified')):
        return '😱'
    if any(k in low for k in ('dead', 'die', 'died', 'freeze', 'rip', 'kill', 'zombie', 'virus')):
        return '💀'
    if any(k in low for k in ('lmao', 'lmfao', 'lol', 'haha', 'hilarious', 'laugh', 'joke', 'reaction', 'overreaction')):
        return '😂'
    if any(k in low for k in ('omg', 'god', 'what', 'holy', 'dude', 'bro', 'wait', 'why')):
        return '👀'
    if any(k in low for k in ('run', 'running', 'fast', 'chase')):
        return '🏃'
    if any(k in low for k in ('fire', 'clutch', 'boss', 'headshot', 'sniper', 'onetap', 'bang')):
        return '🔥'
    return None


def caption_file(path, reel, transcript, width, height, font, duration):
    if any(x in font for x in ',\r\n'):
        raise ValueError('Font name must not contain commas/newlines')
    events = []
    offset = 0
    word_pop = reel.get('word_pop', False) or (str(reel.get('animation', '')).lower() == 'pop')
    words_per_group = reel.get('words_per_group')
    if words_per_group and not reel.get('captions'):
        captions = phrases(transcript, max_words=int(words_per_group))
    else:
        captions = reel.get('captions', phrases(transcript))

    highlight_words = reel.get('highlight_words', True)
    uppercase = reel.get('uppercase', False)
    use_emojis = reel.get('use_emojis', reel.get('emojis', True))
    
    preset = reel.get('subtitle_preset') or reel.get('style_preset', 'default')
    custom_opts = {
        'position': reel.get('subtitle_position', 'bottom'),
        'primary_color': reel.get('primary_color'),
        'secondary_color': reel.get('secondary_color'),
        'outline_color': reel.get('outline_color'),
        'font_size': reel.get('font_size'),
        'highlight_words': highlight_words
    }

    pop_prefix = r"{\fscx115\fscy115\t(0,80,\fscx100\fscy100)}" if word_pop else ""
    ACCENT_KEYS = {'omg', 'dead', 'clutch', 'fail', 'insane', 'win', 'what', 'bro', 'damn', 'holy', 'headshot', 'crash', 'died', 'secret', 'beast'}

    if reel.get('burn_captions', True):
        for a, b in reel['ranges']:
            for c in captions:
                start, end = max(a, float(c['start'])), min(b, float(c['end']))
                if end > start and c['text'].strip():
                    words = c.get('words', []) if isinstance(c, dict) else []
                    timed = [w for w in words if w.get('start') is not None and w.get('end') is not None]
                    if not word_alignment_matches(c.get('text', ''), timed, c.get('start'), c.get('end')):
                        timed = []
                    if highlight_words and timed:
                        phrase = []
                        for wi, w in enumerate(timed):
                            ws, we = max(start, float(w['start'])), min(end, float(w['end']))
                            if we <= ws:
                                continue
                            token = str(w.get('word', '')).strip()
                            if uppercase:
                                token = token.upper()
                            if token:
                                next_start = float(timed[wi + 1]['start']) if wi + 1 < len(timed) else we
                                span_end = min(end, max(we, next_start))
                                cs = max(1, round((span_end - ws) * 100))
                                is_accent = any(k in token.lower() for k in ACCENT_KEYS) or any(ch.isdigit() for ch in token)
                                if is_accent:
                                    phrase.append(f"{{\\k{cs}}}{{\\c&H00FFFF00&}}{ass_text(token)}{{\\r}}")
                                else:
                                    phrase.append(f"{{\\k{cs}}}{ass_text(token)}")
                        if phrase:
                            if use_emojis:
                                em = get_sentiment_emoji(c.get('text', ''))
                                if em and not any(em in p for p in phrase):
                                    phrase.append(f"{{\\k1}}{em}")
                            line_content = pop_prefix + ' '.join(phrase)
                            events.append((offset + start - a, offset + end - a, 'Caption', line_content))
                    else:
                        txt = ass_text(c['text'])
                        if uppercase:
                            txt = txt.upper()
                        if use_emojis:
                            em = get_sentiment_emoji(c.get('text', ''))
                            if em and em not in txt:
                                txt += f" {em}"
                        line_content = pop_prefix + txt
                        events.append((offset + start - a, offset + end - a, 'Caption', line_content))
            offset += b - a
    if reel.get('hook'):
        hook_txt = ass_text(reel['hook'])
        if uppercase:
            hook_txt = hook_txt.upper()
        events.append((0, min(duration, float(reel.get('hook_seconds', 3))), 'Hook', hook_txt))

    caption_style, hook_style = build_ass_style(preset, font, width, height, custom_opts)
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{caption_style}
{hook_style}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    for a, b, style, text in sorted(events):
        header += f'Dialogue: 0,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{text}\n'
    path.write_text(header, encoding='utf-8-sig')
    return len(events)


def validate_manifest(m, info):
    if not isinstance(m, dict):
        raise ValueError('Manifest must be a JSON object')
    width, height, fps = m.get('width', 1080), m.get('height', 1920), m.get('fps', 30)
    if not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 and v % 2 == 0 for v in (width, height)):
        raise ValueError('Dimensions must be positive even integers')
    if abs(width / height - 9 / 16) > .001:
        raise ValueError('Use a 9:16 canvas')
    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or not math.isfinite(fps) or not 1 <= fps <= 120:
        raise ValueError('Invalid fps')
    if not isinstance(m.get('reels'), list) or not m['reels']:
        raise ValueError('Manifest needs at least one reel')
    names = set()
    for reel in m['reels']:
        if not isinstance(reel, dict):
            raise ValueError('Each reel entry must be a JSON object')
        name = reel.get('name')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', name) or name.lower() in names:
            raise ValueError('Reel names must be unique safe file stems')
        names.add(name.lower())
        
        layout = reel.get('layout', 'fit')
        valid_layouts = ('fit', 'crop', 'split', 'stacked', 'pip')
        if not isinstance(layout, str) or layout not in valid_layouts:
            raise ValueError(f'layout must be one of: {", ".join(valid_layouts)}')
            
        crop_x = reel.get('crop_x', .5)
        if not isinstance(crop_x, (int, float)) or isinstance(crop_x, bool) or not math.isfinite(crop_x) or not 0 <= crop_x <= 1:
            raise ValueError('crop_x must be 0–1')
            
        if 'crop_box' in reel:
            box = reel['crop_box']
            if not isinstance(box, (list, tuple)) or len(box) != 4 or not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in box):
                raise ValueError(f'{name}: crop_box must be [x, y, w, h] normalized between 0 and 1')

        if not isinstance(reel.get('ranges'), list) or not reel['ranges']:
            raise ValueError('Each reel needs ranges')
        for pair in reel['ranges']:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f'{name}: each range must contain a start and end')
            a, b = pair
            if not all(isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) for t in (a, b)):
                raise ValueError('Range timestamps must be finite numbers')
            if not 0 <= a < b <= info['duration'] + .05:
                raise ValueError(f'Invalid/out-of-source range: {a}, {b}')
        if 'burn_captions' in reel and not isinstance(reel['burn_captions'], bool):
            raise ValueError(f'{name}: burn_captions must be true or false')
        if 'highlight_words' in reel and not isinstance(reel['highlight_words'], bool):
            raise ValueError(f'{name}: highlight_words must be true or false')
        if reel.get('hook') is not None and not isinstance(reel['hook'], str):
            raise ValueError(f'{name}: hook must be text')
        hook_seconds = reel.get('hook_seconds', 3)
        if not isinstance(hook_seconds, (int, float)) or isinstance(hook_seconds, bool) or not math.isfinite(hook_seconds) or hook_seconds <= 0:
            raise ValueError(f'{name}: hook_seconds must be a positive number')
        for key in ('title', 'reason', 'post_caption'):
            if key in reel and not isinstance(reel[key], str):
                raise ValueError(f'{name}: {key} must be text')
        if 'hashtags' in reel and (not isinstance(reel['hashtags'], list) or not all(isinstance(x, str) for x in reel['hashtags'])):
            raise ValueError(f'{name}: hashtags must be a list of text values')
    font = m.get('font', 'Arial')
    if not isinstance(font, str) or not font.strip() or any(x in font for x in ',\r\n'):
        raise ValueError('font must be a non-empty font name without commas/newlines')
    if 'normalize_audio' in m and not isinstance(m['normalize_audio'], bool):
        raise ValueError('normalize_audio must be true or false')
    if 'transcript' in m and not isinstance(m['transcript'], (str, Path)):
        raise ValueError('transcript must be a file path')
    return width, height, fps


def validate_transcript(transcript, duration):
    if isinstance(transcript, dict):
        segments = transcript.get('segments')
    else:
        segments = transcript
    if not isinstance(segments, list):
        raise ValueError('Transcript must contain a list of segments')
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError(f'Transcript segment {i} must be an object')
        start, end, text = segment.get('start'), segment.get('end'), segment.get('text')
        if (not isinstance(start, (int, float)) or isinstance(start, bool) or not math.isfinite(start)
                or not isinstance(end, (int, float)) or isinstance(end, bool) or not math.isfinite(end)
                or not 0 <= start < end <= duration + .05):
            raise ValueError(f'Transcript segment {i} has invalid/out-of-source times')
        if not isinstance(text, str):
            raise ValueError(f'Transcript segment {i} text must be a string')
        words = segment.get('words', [])
        if not isinstance(words, list):
            raise ValueError(f'Transcript segment {i} words must be a list')
        for j, word in enumerate(words):
            if not isinstance(word, dict):
                raise ValueError(f'Transcript word {i}.{j} must be an object')
            a, b, token = word.get('start'), word.get('end'), word.get('word')
            if (not isinstance(a, (int, float)) or isinstance(a, bool) or not math.isfinite(a)
                    or not isinstance(b, (int, float)) or isinstance(b, bool) or not math.isfinite(b)
                    or not 0 <= a < b <= duration + .05):
                raise ValueError(f'Transcript word {i}.{j} has invalid/out-of-source times')
            if not isinstance(token, str) or not token.strip():
                raise ValueError(f'Transcript word {i}.{j} needs a word string')
    return segments


def validate_reel_subtitles(manifest, info, transcript_segments):
    for reel in manifest['reels']:
        name = reel['name']
        captions = reel.get('captions')
        if 'captions' in reel and not isinstance(captions, list):
            raise ValueError(f'{name}: captions must be a list')
        for i, caption in enumerate(captions or []):
            if not isinstance(caption, dict):
                raise ValueError(f'{name}: caption {i} must be an object')
            start, end, text = caption.get('start'), caption.get('end'), caption.get('text')
            if (not isinstance(start, (int, float)) or isinstance(start, bool) or not math.isfinite(start)
                    or not isinstance(end, (int, float)) or isinstance(end, bool) or not math.isfinite(end)
                    or not 0 <= start < end <= info['duration'] + .05):
                raise ValueError(f'{name}: caption {i} has invalid/out-of-source times')
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f'{name}: caption {i} text must be a non-empty string')
            words = caption.get('words', [])
            if not isinstance(words, list):
                raise ValueError(f'{name}: caption {i} words must be a list')
            if words:
                for j, word in enumerate(words):
                    if not isinstance(word, dict):
                        raise ValueError(f'{name}: caption {i} word {j} must be an object')
                    a, b = word.get('start'), word.get('end')
                    if (not isinstance(a, (int, float)) or isinstance(a, bool) or not math.isfinite(a)
                            or not isinstance(b, (int, float)) or isinstance(b, bool) or not math.isfinite(b)
                            or not start <= a < b <= end):
                        raise ValueError(f'{name}: caption {i} word {j} must fall within its caption time')
                    if not isinstance(word.get('word'), str) or not word['word'].strip():
                        raise ValueError(f'{name}: caption {i} word {j} needs text')
                if not word_alignment_matches(text, words):
                    warnings.warn(f'{name}: caption {i} word alignment differs from its text; showing the complete phrase without karaoke highlighting')
            if not any(max(start, a) < min(end, b) for a, b in reel['ranges']):
                warnings.warn(f'{name}: caption {i} does not overlap any selected source range')
        if reel.get('burn_captions', True) and not (captions or transcript_segments):
            raise ValueError(f'{name}: subtitles are enabled but no transcript/captions are supplied')
        if reel.get('burn_captions', True) and captions is None and transcript_segments:
            if not any(seg.get('text', '').strip() and any(
                    max(seg['start'], a) < min(seg['end'], b) for a, b in reel['ranges'])
                    for seg in transcript_segments):
                warnings.warn(f'{name}: no transcript speech overlaps this reel; confirm it is intentionally silent or add source-aligned subtitles')


def warn_duplicate_ranges(manifest):
    reels = manifest['reels']
    for i, reel in enumerate(reels):
        for j in range(i + 1, len(reels)):
            other = reels[j]
            overlap = sum(max(0.0, min(b, d) - max(a, c))
                          for a, b in reel['ranges'] for c, d in other['ranges'])
            if overlap > .25:
                warnings.warn(f"{reel['name']} and {other['name']} reuse {overlap:.2f}s of source footage; keep only if the repetition is editorially intentional")
        ranges = sorted(reel['ranges'])
        for (_, end), (next_start, _) in zip(ranges, ranges[1:]):
            if next_start < end:
                warnings.warn(f"{reel['name']} has overlapping ranges that will repeat source footage")


def build_layout_filter(layout, width, height, reel):
    """Constructs FFmpeg filtergraph for fit, crop, split (stacked), and pip layouts."""
    if layout in ('split', 'stacked'):
        split_ratio = float(reel.get('split_ratio', 0.5))
        top_h = max(2, round((height * split_ratio) / 2) * 2)
        bot_h = height - top_h
        
        top_crop_x = reel.get('top_crop_x', 0.5)
        bot_crop_x = reel.get('bottom_crop_x', 0.5)
        bot_layout = reel.get('bottom_layout', 'fit')
        
        lines = [
            '[joined]split=2[top_in][bot_in]',
            f'[top_in]scale=-1:{top_h}:force_original_aspect_ratio=increase,crop={width}:{top_h}:(iw-ow)*{top_crop_x}:(ih-oh)/2,setsar=1[top_pane]'
        ]
        if bot_layout == 'fit':
            lines += [
                f'[bot_in]split=2[bot_bg][bot_fg]',
                f'[bot_bg]scale={width//2}:{bot_h//2}:force_original_aspect_ratio=increase,crop={width//2}:{bot_h//2},boxblur=15:2,scale={width}:{bot_h},setsar=1[bot_back]',
                f'[bot_fg]scale={width}:{bot_h}:force_original_aspect_ratio=decrease,setsar=1[bot_front]',
                f'[bot_back][bot_front]overlay=(W-w)/2:(H-h)/2[bot_pane]'
            ]
        else:
            lines += [
                f'[bot_in]scale=-1:{bot_h}:force_original_aspect_ratio=increase,crop={width}:{bot_h}:(iw-ow)*{bot_crop_x}:(ih-oh)/2,setsar=1[bot_pane]'
            ]
        lines.append('[top_pane][bot_pane]vstack=inputs=2[canvas]')
        return lines
        
    elif layout == 'pip':
        pos = reel.get('pip_position', 'top-right')
        pip_w = round(width * float(reel.get('pip_scale', 0.35)))
        pip_h = round(pip_w * 9 / 16)
        margin = 30
        
        pos_map = {
            'top-left': f'{margin}:{margin + 150}',
            'top-right': f'W-w-{margin}:{margin + 150}',
            'bottom-left': f'{margin}:H-h-{margin + 350}',
            'bottom-right': f'W-w-{margin}:H-h-{margin + 350}'
        }
        overlay_coords = pos_map.get(pos, pos_map['top-right'])
        
        return [
            '[joined]split=2[main_in][pip_in]',
            f'[main_in]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1[main_canvas]',
            f'[pip_in]scale={pip_w}:{pip_h}:force_original_aspect_ratio=increase,crop={pip_w}:{pip_h},setsar=1[pip_pane]',
            f'[main_canvas][pip_pane]overlay={overlay_coords}[canvas]'
        ]
        
    elif layout == 'crop':
        if 'crop_box' in reel:
            bx, by, bw, bh = reel['crop_box']
            return [
                f'[joined]crop=iw*{bw}:ih*{bh}:iw*{bx}:ih*{by},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1[canvas]'
            ]
        else:
            crop_x = reel.get('crop_x', 0.5)
            return [
                f'[joined]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:(iw-ow)*{crop_x}:(ih-oh)/2,setsar=1[canvas]'
            ]
            
    else:  # default 'fit'
        return [
            '[joined]split=2[bg][fg]',
            f'[bg]scale={width//2}:{height//2}:force_original_aspect_ratio=increase,crop={width//2}:{height//2},boxblur=20:2,scale={width}:{height},setsar=1[back]',
            f'[fg]scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1[front]',
            '[back][front]overlay=(W-w)/2:(H-h)/2[canvas]'
        ]


def render(args):
    video = Path(args.video).resolve()
    manifest_path = Path(args.manifest).resolve()
    out = Path(args.out).resolve()
    if out == video.parent or out in video.parents:
        raise ValueError('Output must be a separate folder outside the source video folder')
    m, info = load(manifest_path), probe(video)
    width, height, fps = validate_manifest(m, info)
    transcript = []
    transcript_segments = []
    if m.get('transcript'):
        t = Path(m['transcript'])
        transcript_path = t if t.is_absolute() else manifest_path.parent / t
        transcript_path = transcript_path.resolve()
        transcript = load(transcript_path)
        if isinstance(transcript, dict) and transcript.get('source'):
            if not isinstance(transcript['source'], str):
                raise ValueError('Transcript source metadata must be a path string')
            raw_source = transcript['source']
            source_basename = raw_source.replace('\\', '/').split('/')[-1]
            if source_basename.lower() != video.name.lower():
                transcript_source = Path(raw_source)
                if not transcript_source.is_absolute():
                    transcript_source = transcript_path.parent / transcript_source
                if transcript_source.resolve() != video:
                    raise ValueError('Transcript source differs from the rendering source')
            else:
                transcript_source = video
        elif isinstance(transcript, dict):
            warnings.warn('Transcript has no source metadata; confirm manually that it matches the input video')
        transcript_segments = validate_transcript(transcript, info['duration'])
    validate_reel_subtitles(m, info, transcript_segments)
    warn_duplicate_ranges(m)
    
    if not args.overwrite:
        for r in m['reels']:
            if (out / (r['name'] + '.mp4')).exists():
                raise FileExistsError('Output exists; choose a new folder or explicitly --overwrite')
    out.mkdir(parents=True, exist_ok=True)
    posting, report = [], []
    
    for reel in m['reels']:
        name, ranges = reel['name'], reel['ranges']
        duration = sum(b - a for a, b in ranges)
        sub = out / (name + '.ass')
        event_count = caption_file(sub, reel, transcript, width, height, m.get('font', 'Arial'), duration)
        if reel.get('burn_captions', True) and not (reel.get('captions') or transcript):
            raise ValueError(f'{name}: captions requested but none supplied; transcribe or disable captions')
            
        cmd = [ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y' if args.overwrite else '-n']
        for a, b in ranges:
            cmd += ['-ss', str(a), '-t', str(b - a), '-i', str(video)]
            
        graph = []
        for i, (a, b) in enumerate(ranges):
            graph.append(f'[{i}:v:0]trim=duration={b-a},setpts=PTS-STARTPTS,fps={fps},setsar=1[v{i}]')
            if info['has_audio']:
                graph.append(f'[{i}:a:0]atrim=duration={b-a},asetpts=PTS-STARTPTS,aresample=48000[a{i}]')
        ins = ''.join(f'[v{i}]' + (f'[a{i}]' if info['has_audio'] else '') for i in range(len(ranges)))
        graph.append(f'{ins}concat=n={len(ranges)}:v=1:a={int(info["has_audio"])}[joined]' + ('[sound]' if info['has_audio'] else ''))
        
        # Build layout filter (fit, crop, split, pip)
        graph += build_layout_filter(reel.get('layout', 'fit'), width, height, reel)
        
        if event_count:
            graph.append(f'[canvas]ass=filename={sub.name},format=yuv420p[final]')
        else:
            graph.append('[canvas]format=yuv420p[final]')
            
        # Check for BGM mixing with auto-ducking
        bgm_file = getattr(args, 'bgm', None) or m.get('bgm')
        bgm_volume = float(getattr(args, 'bgm_volume', 0.2) or m.get('bgm_volume', 0.2))
        bgm_idx = len(ranges)
        has_bgm = bool(bgm_file and Path(bgm_file).exists())
        if has_bgm:
            cmd += ['-stream_loop', '-1', '-i', str(Path(bgm_file).resolve())]
            if info['has_audio']:
                graph.append(f'[{bgm_idx}:a]volume={bgm_volume}[bgm_raw]')
                graph.append(f'[bgm_raw][sound]sidechaincompress=threshold=0.03:ratio=4:attack=50:release=300[ducked_bgm]')
                graph.append(f'[sound][ducked_bgm]amix=inputs=2:duration=first[mixed_sound]')
                sound_label = '[mixed_sound]'
            else:
                graph.append(f'[{bgm_idx}:a]volume={bgm_volume}[mixed_sound]')
                sound_label = '[mixed_sound]'
        else:
            sound_label = '[sound]'

        if (info['has_audio'] or has_bgm) and m.get('normalize_audio', True):
            graph.append(f'{sound_label}loudnorm=I=-16:TP=-1.5:LRA=11[normalized]')
            final_audio = '[normalized]'
        elif info['has_audio'] or has_bgm:
            final_audio = sound_label
        else:
            final_audio = None
            
        cmd += ['-filter_complex', ';'.join(graph), '-map', '[final]']
        if final_audio:
            cmd += ['-map', final_audio, '-c:a', 'aac', '-b:a', '192k', '-ar', '48000']
                    
        target = out / (name + '.mp4')
        encoder = getattr(args, 'encoder', 'auto')
        if encoder == 'auto':
            encoder = detect_hardware_encoder()
            
        if encoder == 'h264_nvenc':
            cmd += ['-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '19', '-b:v', '8M',
                    '-maxrate', '12M', '-bufsize', '16M', '-pix_fmt', 'yuv420p',
                    '-t', str(duration), '-movflags', '+faststart', str(target)]
        elif encoder == 'h264_videotoolbox':
            cmd += ['-c:v', 'h264_videotoolbox', '-b:v', '8M', '-pix_fmt', 'yuv420p',
                    '-t', str(duration), '-movflags', '+faststart', str(target)]
        elif encoder == 'h264_qsv':
            cmd += ['-c:v', 'h264_qsv', '-global_quality', '20', '-pix_fmt', 'nv12',
                    '-t', str(duration), '-movflags', '+faststart', str(target)]
        else:
            cmd += ['-c:v', 'libx264', '-preset', getattr(args, 'preset', 'fast'), '-crf', '18', '-pix_fmt', 'yuv420p',
                    '-t', str(duration), '-movflags', '+faststart', str(target)]
                
        try:
            run(cmd, cwd=out)
        except Exception:
            if target.exists():
                target.unlink()
            raise
            
        report.append(dict(name=name, ranges=ranges, target_duration=duration, caption_events=event_count,
                           layout=reel.get('layout', 'fit'), reason=reel.get('reason', '')))
        posting += [f'## {reel.get("title", name)}', '', f'File: `{target.name}`', '',
                    reel.get('post_caption', ''), '', ' '.join(reel.get('hashtags', [])), '']
        print(f'Exported {target.name} ({duration:.2f}s)', flush=True)
        
    if m.get('transcript'):
        save(out / 'transcript.json', transcript)
        m['transcript'] = 'transcript.json'
    save(out / 'cuts.json', m)
    save(out / 'render_report.json', report)
    (out / 'posting.md').write_text('\n'.join(posting), encoding='utf-8')


def verify(args):
    results = []
    report_path = Path(args.folder) / 'render_report.json'
    expected = {r['name']: r['target_duration'] for r in load(report_path)} if report_path.exists() else {}
    for p in sorted(Path(args.folder).glob('*.mp4')):
        info = probe(p)
        decoded = subprocess.run([ffmpeg(), '-v', 'error', '-xerror', '-i', str(p), '-f', 'null', '-'],
                                 capture_output=True, text=True, errors='replace')
        result = {k: v for k, v in info.items() if k != 'stream_details'}
        result.update(decode_ok=decoded.returncode == 0 and not decoded.stderr.strip(),
                      decode_errors=decoded.stderr.strip(), vertical_9_16=abs(info['width']/info['height']-9/16)<.001)
        if p.stem in expected:
            result['target_duration'] = expected[p.stem]
            result['duration_ok'] = abs(info['duration'] - expected[p.stem]) <= max(.15, 2/info['fps'])
        results.append(result)
        print(f'{p.name}: decode={result["decode_ok"]}, {info["width"]}x{info["height"]}, {info["duration"]:.2f}s')
    if not results:
        raise ValueError('No MP4 files found')
    save(Path(args.folder) / 'qa.json', {'checks': results, 'scope': 'Technical decode/metadata only; visual, caption and listening review are separate.'})
    if not all(x['decode_ok'] and x['vertical_9_16'] and x.get('duration_ok', True) for x in results):
        raise SystemExit(1)


def detect_silence(args):
    """Detects audio silence in a video using FFmpeg silencedetect without external APIs."""
    video = Path(args.video).resolve()
    ff_bin = ffmpeg()
    cmd = [
        ff_bin, '-i', str(video),
        '-af', f'silencedetect=noise={args.noise_db}dB:d={args.min_duration}',
        '-f', 'null', '-'
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    silences = []
    for line in p.stderr.splitlines():
        if 'silence_start:' in line:
            m = re.search(r'silence_start:\s*([\d\.]+)', line)
            if m:
                silences.append({'start': float(m.group(1))})
        elif 'silence_end:' in line:
            m = re.search(r'silence_end:\s*([\d\.]+)\s*\|\s*silence_duration:\s*([\d\.]+)', line)
            if m and silences and 'end' not in silences[-1]:
                silences[-1]['end'] = float(m.group(1))
                silences[-1]['duration'] = float(m.group(2))
                
    if args.out:
        save(args.out, {'video': str(video), 'silence_count': len(silences), 'silences': silences})
    print(f'Detected {len(silences)} silent pauses (noise<={args.noise_db}dB, duration>={args.min_duration}s)')
    return silences


def detect_audio_spikes_core(video_path, bucket_seconds=1.0, rolling_minutes=3.0, min_ratio=2.0, top_k=10, before=15.0, after=15.0, min_gap=60.0):
    """Detect sudden audio volume spikes (screams, laughter, explosions) using raw audio RMS."""
    try:
        import numpy as np
    except ImportError:
        return []
        
    cmd = [ffmpeg(), '-v', 'quiet', '-i', str(video_path), '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-']
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return []
        
    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32)
    sr = 16000
    samples_per_bucket = int(sr * bucket_seconds)
    num_buckets = len(audio) // samples_per_bucket
    if num_buckets < 5:
        return []
        
    rms_buckets = []
    times = []
    for i in range(num_buckets):
        chunk = audio[i * samples_per_bucket : (i + 1) * samples_per_bucket]
        rms = float(np.sqrt(np.mean(chunk**2)))
        rms_buckets.append(rms)
        times.append(i * bucket_seconds)
        
    rms_arr = np.array(rms_buckets)
    window_buckets = max(5, int((rolling_minutes * 60) / bucket_seconds))
    half_w = window_buckets // 2
    
    candidates = []
    for i in range(num_buckets):
        w_start = max(0, i - half_w)
        w_end = min(num_buckets, i + half_w + 1)
        baseline = float(np.median(rms_arr[w_start:w_end]))
        if baseline < 50.0:
            baseline = 50.0
        ratio = rms_arr[i] / baseline
        if ratio >= min_ratio and rms_arr[i] > 250.0:
            candidates.append({
                'time': times[i],
                'rms': rms_arr[i],
                'baseline': baseline,
                'ratio': ratio,
                'start': max(0.0, times[i] - before),
                'end': times[i] + after
            })
            
    candidates.sort(key=lambda x: x['ratio'], reverse=True)
    selected = []
    for c in candidates:
        if not any(abs(c['time'] - s['time']) < min_gap for s in selected):
            selected.append(c)
            if len(selected) >= top_k:
                break
                
    selected.sort(key=lambda x: x['time'])
    return selected


def detect_audio_spikes(args):
    """CLI handler for audio energy spike detection."""
    spikes = detect_audio_spikes_core(args.video, bucket_seconds=getattr(args, 'bucket', 1.0),
                                      rolling_minutes=getattr(args, 'window', 3.0),
                                      min_ratio=getattr(args, 'min_ratio', 2.0),
                                      top_k=getattr(args, 'top', 10),
                                      min_gap=getattr(args, 'gap', 60.0))
    out_data = {'video': str(args.video), 'spike_count': len(spikes), 'spikes': spikes}
    if getattr(args, 'out', None):
        save(args.out, out_data)
    print(f'Detected {len(spikes)} audio energy spikes (ratio>={getattr(args, "min_ratio", 2.0)}x):')
    for idx, s in enumerate(spikes, 1):
        m, sec = divmod(int(s['time']), 60)
        h, m = divmod(m, 60)
        ts_str = f"{h:02}:{m:02}:{sec:02}" if h > 0 else f"{m:02}:{sec:02}"
        print(f"  #{idx:02d} [{ts_str}] {s['ratio']:.1f}x volume spike (RMS {s['rms']:.0f} vs baseline {s['baseline']:.0f})")
    return spikes


def detect_facecam(video_path, num_samples=12):
    """Detects streamer facecam corner and coordinates using frame sampling and motion/skin analysis."""
    info = probe(video_path)
    dur = info['duration']
    if dur <= 2.0:
        return {'has_facecam': False, 'layout': 'fit'}
        
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {'has_facecam': False, 'layout': 'fit'}
        
    c = cv2.VideoCapture(str(video_path))
    if not c.isOpened():
        return {'has_facecam': False, 'layout': 'fit'}
        
    sample_times = np.linspace(dur * 0.1, dur * 0.9, num_samples)
    frames = []
    for t in sample_times:
        c.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame = c.read()
        if ret:
            frames.append(frame)
    c.release()
    
    if len(frames) < 4:
        return {'has_facecam': False, 'layout': 'fit'}
        
    H, W, _ = frames[0].shape
    corners = {
        'top-left': (0, int(H * 0.35), 0, int(W * 0.30), [0.0, 0.0, 0.30, 0.35]),
        'top-right': (0, int(H * 0.35), int(W * 0.70), W, [0.70, 0.0, 0.30, 0.35]),
        'bottom-left': (int(H * 0.65), H, 0, int(W * 0.30), [0.0, 0.65, 0.30, 0.35]),
        'bottom-right': (int(H * 0.65), H, int(W * 0.70), W, [0.70, 0.65, 0.30, 0.35]),
    }
    
    scores = {}
    for name, (y1, y2, x1, x2, box) in corners.items():
        diffs = []
        skin_ratios = []
        for i in range(1, len(frames)):
            c_curr = frames[i][y1:y2, x1:x2]
            c_prev = frames[i-1][y1:y2, x1:x2]
            diff = float(np.mean(np.abs(c_curr.astype(float) - c_prev.astype(float))))
            diffs.append(diff)
            
            ycrcb = cv2.cvtColor(c_curr, cv2.COLOR_BGR2YCrCb)
            mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
            skin_ratios.append(float(np.mean(mask > 0)))
            
        mean_diff = float(np.mean(diffs))
        mean_skin = float(np.mean(skin_ratios))
        scores[name] = {
            'score': mean_diff * (1.0 + 4.0 * mean_skin),
            'motion': mean_diff,
            'skin': mean_skin,
            'box': box
        }
        
    best_corner = max(scores, key=lambda k: scores[k]['score'])
    best_data = scores[best_corner]
    has_cam = best_data['skin'] >= 0.03 and best_data['motion'] >= 2.0
    return {
        'has_facecam': has_cam,
        'corner': best_corner,
        'crop_box': best_data['box'],
        'scores': {k: v['score'] for k, v in scores.items()},
        'recommended_layout': 'split' if has_cam else 'fit',
        'top_crop_x': 0.15 if 'left' in best_corner else 0.85
    }


def detect_facecam_cmd(args):
    """CLI handler for facecam detection."""
    res = detect_facecam(args.video)
    if getattr(args, 'out', None):
        save(args.out, res)
    if res['has_facecam']:
        print(f"Facecam DETECTED at corner '{res['corner']}'! Recommended layout: '{res['recommended_layout']}' (top_crop_x={res['top_crop_x']})")
    else:
        print("No streamer facecam detected (pure gameplay/full screen). Recommended layout: 'fit'")
    return res


def suggest_moments(args):
    """Scans transcript and optional audio energy for high-energy candidate clips."""
    transcript_path = Path(args.transcript).resolve()
    data = load(transcript_path)
    segments = data.get('segments', []) if isinstance(data, dict) else data
    if not segments:
        raise ValueError('No segments found in transcript')
        
    KEYWORDS = {
        "jump": 3.0, "crash": 3.5, "bro": 1.5, "omg": 3.0, "insane": 3.0, "crazy": 2.5,
        "wait": 2.0, "look": 2.0, "no way": 3.5, "impossible": 3.0, "chance": 2.0,
        "ready": 1.5, "win": 2.5, "fail": 2.5, "oh": 1.5, "yes": 1.5, "nice": 2.0,
        "easy": 1.5, "clutch": 3.0, "last": 2.0, "help": 2.5, "what": 1.5, "lets go": 3.0,
        "died": 2.5, "first try": 3.0, "challenge": 2.0, "secret": 2.5, "trick": 2.0
    }
    
    # Check for audio energy spikes if video supplied
    audio_spikes = []
    if getattr(args, 'video', None):
        try:
            audio_spikes = detect_audio_spikes_core(args.video, top_k=25, min_gap=20.0)
            if audio_spikes:
                print(f"Fusing {len(audio_spikes)} audio volume spikes into moment virality score...")
        except Exception as e:
            warnings.warn(f"Audio spike analysis skipped: {e}")
            
    scored_segs = []
    for seg in segments:
        text = seg.get('text', '')
        start_t = float(seg.get('start', 0))
        end_t = float(seg.get('end', 0))
        duration = max(0.4, end_t - start_t)
        words = text.split()
        wps = len(words) / duration
        
        kw_score = sum(weight for kw, weight in KEYWORDS.items() if kw in text.lower())
        punct_score = text.count('!') * 2.0 + text.count('?') * 1.5
        
        # Audio spike boost
        audio_boost = 1.0
        for aspike in audio_spikes:
            if start_t - 5.0 <= aspike['time'] <= end_t + 5.0:
                audio_boost = max(audio_boost, 1.0 + 0.4 * min(4.0, aspike['ratio']))
                
        score = ((wps * 1.0) + kw_score + punct_score) * audio_boost
        scored_segs.append({
            'start': start_t,
            'end': end_t,
            'text': text,
            'score': score
        })
        
    candidates = []
    min_dur, max_dur = float(args.min_duration), float(args.max_duration)
    
    for i in range(len(scored_segs)):
        start_time = scored_segs[i]['start']
        accum_text = []
        total_score = 0
        for j in range(i, len(scored_segs)):
            end_time = scored_segs[j]['end']
            dur = end_time - start_time
            if dur > max_dur:
                break
            accum_text.append(scored_segs[j]['text'])
            total_score += scored_segs[j]['score']
            if dur >= min_dur:
                density_score = total_score / (dur ** 0.5)
                candidates.append({
                    'start': round(start_time, 2),
                    'end': round(end_time, 2),
                    'duration': round(dur, 2),
                    'score': round(density_score, 2),
                    'preview': ' '.join(accum_text)[:140]
                })
                
    candidates.sort(key=lambda x: x['score'], reverse=True)
    selected = []
    for c in candidates:
        overlap = False
        for s in selected:
            ov = max(0.0, min(c['end'], s['end']) - max(c['start'], s['start']))
            if ov > 5.0:
                overlap = True
                break
        if not overlap:
            selected.append(c)
        if len(selected) >= args.max_reels:
            break
            
    manifest = {
        'width': 1080,
        'height': 1920,
        'fps': 30,
        'transcript': str(transcript_path.name),
        'font': getattr(args, 'font', 'Arial'),
        'normalize_audio': True,
        'reels': []
    }
    
    for idx, s in enumerate(selected, 1):
        clean_title = f"Highlight {idx:02d}"
        em = get_sentiment_emoji(s['preview']) or '🔥'
        manifest['reels'].append({
            'name': f"{idx:02d}_moment",
            'title': clean_title,
            'reason': f"High-energy moment with virality density score {s['score']:.1f}",
            'ranges': [[s['start'], s['end']]],
            'layout': args.default_layout,
            'crop_x': 0.5,
            'subtitle_preset': args.subtitle_preset,
            'uppercase': args.uppercase,
            'hook': f"WAIT FOR IT! {em}",
            'burn_captions': True,
            'highlight_words': True,
            'post_caption': f"{clean_title}: {s['preview']}...",
            'hashtags': ['#Shorts', '#Reels', '#Gaming', '#Highlights']
        })
        
    save(args.out, manifest)
    print(f"Generated {len(selected)} moment suggestions -> {args.out}")


def parse_chat_file(chat_path):
    """Parses Twitch JSON, YouTube .live_chat.json, or generic list format."""
    path = Path(chat_path)
    if not path.exists():
        raise FileNotFoundError(f"Chat file not found: {chat_path}")
    messages = []
    # Try reading as single JSON (TwitchDownloader or generic list)
    try:
        content = path.read_text(encoding='utf-8-sig')
        data = json.loads(content)
        if isinstance(data, dict) and "comments" in data:
            for c in data["comments"]:
                t = c.get("content_offset_seconds")
                if t is not None:
                    body = c.get("message", {}).get("body", "")
                    messages.append((float(t), str(body)))
            return messages
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    t = item.get("time") or item.get("timestamp") or item.get("content_offset_seconds")
                    if t is not None:
                        txt = item.get("message") or item.get("text") or ""
                        messages.append((float(t), str(txt)))
            return messages
    except Exception:
        pass

    # Try reading line-by-line (YouTube .live_chat.json or JSONL)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                action = obj.get("replayChatItemAction", {})
                for a in action.get("actions", []):
                    item = a.get("addChatItemAction", {}).get("item", {})
                    msg_renderer = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer")
                    if msg_renderer:
                        offset_ms = msg_renderer.get("videoOffsetTimeMsec")
                        if offset_ms is not None:
                            t = float(offset_ms) / 1000.0
                            runs = msg_renderer.get("message", {}).get("runs", [])
                            txt = "".join(r.get("text", "") for r in runs)
                            messages.append((t, txt))
            except Exception:
                continue
    return messages


def find_chat_spikes_core(messages, bucket_size=20, window_minutes=5, before=20, after=10, min_gap=120, top_k=10, min_ratio=2.0, skip_intro_minutes=15.0):
    from collections import Counter
    if not messages:
        return [], 0, 0
    max_time = max(t for t, _ in messages)
    skip_intro_sec = max(0.0, float(skip_intro_minutes) * 60.0)
    
    step_sec = 5.0
    win_sec = max(10.0, float(bucket_size))
    num_steps = int(math.ceil(max_time / step_sec)) + 1
    
    REACTION_WORDS = {
        'LMAO', 'LOL', 'KEKW', 'LUL', 'HAHA', 'WTF', 'OMG', 'BRO', 'NOOO',
        'SCREAM', 'SCARED', 'DEAD', 'DIE', 'DIED', 'JUMP', 'JUMPSCARE', 'RUN',
        'ASHLEY', 'LEON', 'BOSS', 'CLUTCH', 'CRAZY', 'HELP', 'RIP', 'CLIP', 'LMFAO'
    }
    EMOJIS = ['😂', '💀', '😭', '😱', '🤣', '👀', '🙏']

    windows = []
    for s in range(num_steps):
        t_start = s * step_sec
        t_end = t_start + win_sec
        center_t = t_start + win_sec / 2.0
        if max_time > skip_intro_sec * 2 and center_t < skip_intro_sec:
            continue
        msgs_in = [m for m in messages if t_start <= m[0] < t_end]
        cnt = len(msgs_in)
        if cnt == 0:
            continue
        reaction_hits = 0
        words = []
        for _, msg in msgs_in:
            upper = msg.upper()
            for w in upper.split():
                w_clean = w.strip(".,!?\"'")
                if w_clean in REACTION_WORDS:
                    reaction_hits += 1
                if len(w_clean) >= 3 and w_clean not in ("THE", "AND", "YOU", "FOR", "THAT", "THIS", "SHE", "ALL", "WITH"):
                    words.append(w_clean)
            reaction_hits += sum(msg.count(e) for e in EMOJIS)
        windows.append((center_t, cnt, reaction_hits, words, msgs_in))

    half_window_steps = max(1, int((window_minutes * 60) / (2 * step_sec)))
    scored = []
    for i, (center_t, cnt, reaction_hits, words, msgs_in) in enumerate(windows):
        w_start = max(0, i - half_window_steps)
        w_end = min(len(windows), i + half_window_steps + 1)
        sub_counts = [windows[j][1] for j in range(w_start, w_end)]
        baseline = sum(sub_counts) / len(sub_counts) if sub_counts else 1.0
        ratio = cnt / max(0.5, baseline)
        score = ratio * (1.0 + min(4.0, reaction_hits * 0.6))
        top_words = [w for w, _ in Counter(words).most_common(3)]
        scored.append({
            "center_time": center_t,
            "count": cnt,
            "baseline": round(baseline, 1),
            "ratio": round(ratio, 2),
            "score": round(score, 2),
            "reaction_hits": reaction_hits,
            "top_words": top_words,
            "sample_quotes": [m[1] for m in msgs_in[:4]]
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    peaks = []
    for item in scored:
        if item["ratio"] < min_ratio and len(peaks) >= top_k:
            break
        t = item["center_time"]
        if any(abs(t - p["center_time"]) < min_gap for p in peaks):
            continue
        peaks.append(item)
        if len(peaks) >= top_k:
            break

    peaks.sort(key=lambda x: x["center_time"])
    results = []
    for p in peaks:
        start = max(0.0, p["center_time"] - before)
        end = min(max_time, p["center_time"] + after)
        results.append({
            "spike_time": p["center_time"],
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(end - start, 2),
            "count": p["count"],
            "ratio": p["ratio"],
            "score": p["score"],
            "top_words": p["top_words"],
            "sample_quotes": p.get("sample_quotes", [])
        })
    return results, len(messages), max_time


def find_chat_spikes(args):
    """Detects viral moment spikes in chat logs (Twitch, YouTube, or generic JSON) and outputs cuts.json."""
    messages = parse_chat_file(args.chat)
    if not messages:
        raise ValueError(f"No valid chat messages found in {args.chat}")
        
    peaks, total_msgs, max_time = find_chat_spikes_core(
        messages,
        bucket_size=args.bucket,
        window_minutes=args.window,
        before=args.before,
        after=args.after,
        min_gap=args.gap,
        top_k=args.top,
        min_ratio=args.min_ratio,
        skip_intro_minutes=getattr(args, 'skip_intro', 15.0)
    )
    
    h, m, s = int(max_time // 3600), int((max_time % 3600) // 60), int(max_time % 60)
    print(f"\n{total_msgs} chat messages, {h:02d}:{m:02d}:{s:02d} of stream")
    print("-" * 55)
    for idx, p in enumerate(peaks, 1):
        st = p['spike_time']
        sh, sm, ss = int(st // 3600), int((st % 3600) // 60), int(st % 60)
        words_str = ", ".join(p['top_words']) if p['top_words'] else "N/A"
        print(f"#{idx}  {sh:02d}:{sm:02d}:{ss:02d}  {p['count']} msgs in {args.bucket}s ({p['ratio']:.1f}x normal) | Words: {words_str}")
    print("-" * 55)
    
    manifest = {
        'width': 1080,
        'height': 1920,
        'fps': 30,
        'font': 'Arial',
        'normalize_audio': True,
        'reels': []
    }
    
    for idx, p in enumerate(peaks, 1):
        st = p['spike_time']
        sh, sm, ss = int(st // 3600), int((st % 3600) // 60), int(st % 60)
        words_str = " ".join(p['top_words']) if p['top_words'] else "CHAT EXPLOSION"
        name = f"{idx:02d}_chat_spike_{sh:02d}_{sm:02d}_{ss:02d}"
        
        hook_emoji = " 💀" if any(w in words_str for w in ("DEAD", "DIE", "JUMP", "SCREAM", "SCARE")) else (" 😂" if any(w in words_str for w in ("LMAO", "LOL", "KEKW", "HAHA", "LMFAO")) else " 🔥")
        manifest['reels'].append({
            'name': name,
            'title': f"Chat Explosion #{idx}: {words_str}",
            'reason': f"Chat spike at {sh:02d}:{sm:02d}:{ss:02d}: {p['count']} msgs in {args.bucket}s ({p['ratio']:.1f}x normal). Key reaction: {words_str}",
            'ranges': [[p['start'], p['end']]],
            'layout': args.default_layout,
            'crop_x': 0.5,
            'subtitle_preset': args.subtitle_preset,
            'uppercase': args.uppercase,
            'use_emojis': True,
            'hook': f"CHAT LOST IT HERE!{hook_emoji}" if idx == 1 else f"CHAT: {words_str}!{hook_emoji}",
            'burn_captions': True,
            'highlight_words': True,
            'post_caption': f"Chat went crazy during this moment! ({p['ratio']:.1f}x normal volume) {words_str}",
            'hashtags': ['#Twitch', '#Gaming', '#ChatClips', '#Shorts', '#Reels']
        })
        
    save(args.out, manifest)
    print(f"\nSaved {len(peaks)} candidate clips to {args.out}")
    print(f"Next step: python skills/video-to-reels/scripts/reels.py render --video \"<video_file>\" --manifest \"{args.out}\" --out \"reels_output/exports\"\n")


def auto_pipeline(args):
    """End-to-end autonomous pipeline: Ingest/Download -> Audio+Chat+Speech Detection -> Transcribe -> Manifest -> NVENC Render -> QA."""
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Resolve video source
    if getattr(args, 'url', None):
        print(f"\n[1/5] Ingesting video from URL via yt-dlp: {args.url}...", flush=True)
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp is required for URL downloads. Run: pip install yt-dlp")
            
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(out_dir / 'source_video.%(ext)s'),
            'quiet': False
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([args.url])
        matched = list(out_dir.glob('source_video.*'))
        if not matched:
            raise RuntimeError("Failed to download video from URL")
        video_path = matched[0].resolve()
    elif getattr(args, 'video', None):
        video_path = Path(args.video).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"Source video not found: {video_path}")
        print(f"\n[1/5] Using source video: {video_path.name}...", flush=True)
    else:
        raise ValueError("Must provide either --video or --url")
        
    v_info = probe(video_path)
    print(f"      Duration: {v_info['duration']:.1f}s | Resolution: {v_info['width']}x{v_info['height']} | FPS: {v_info['fps']:.1f}")
    
    chosen_layout = args.layout
    top_crop_x = 0.5
    if chosen_layout == 'auto':
        print("[2/5] Detecting streamer facecam for smart layout...", flush=True)
        cam_res = detect_facecam(video_path)
        chosen_layout = cam_res['recommended_layout']
        top_crop_x = cam_res.get('top_crop_x', 0.5)
        print(f"      Layout auto-selected: '{chosen_layout}' (facecam={'yes' if cam_res['has_facecam'] else 'no'})", flush=True)
    else:
        print(f"[2/5] Using requested layout: '{chosen_layout}'", flush=True)
        
    # 2. Local Whisper Transcription
    transcript_file = out_dir / 'transcript.json'
    if not transcript_file.exists():
        print(f"[3/5] Transcribing speech with local Whisper (device={args.device})...", flush=True)
        class TransArgs:
            pass
        t_args = TransArgs()
        t_args.video = str(video_path)
        t_args.out = str(transcript_file)
        t_args.model = args.model
        t_args.language = args.language
        t_args.device = args.device
        t_args.compute_type = args.compute_type
        transcribe(t_args)
    else:
        print(f"[3/5] Reusing existing transcript: {transcript_file.name}", flush=True)
        
    # 3. Moment Detection (Multimodal)
    print(f"[4/5] Running multi-modal moment analysis (Chat + Audio Screams + Speech)...", flush=True)
    cuts_file = out_dir / 'cuts.json'
    if getattr(args, 'chat', None) and Path(args.chat).exists():
        print(f"      Parsing chat spikes from: {args.chat}")
        msgs = parse_chat_file(args.chat)
        peaks, _, _ = find_chat_spikes_core(msgs, top_k=args.count, min_ratio=1.8, skip_intro_minutes=args.skip_intro)
        manifest = {
            'width': 1080, 'height': 1920, 'fps': 30,
            'transcript': 'transcript.json', 'font': args.font, 'normalize_audio': True,
            'reels': []
        }
        for idx, p in enumerate(peaks, 1):
            top_words = p.get('top_words', [])
            words_str = ' '.join(top_words[:3]) if top_words else "LMAO"
            em = get_sentiment_emoji(words_str) or '🔥'
            manifest['reels'].append({
                'name': f"{idx:02d}_chat_spike",
                'title': f"Chat Burst #{idx}: {words_str}",
                'reason': f"Chat spike at {p.get('spike_time', 0):.1f}s: {p['ratio']:.1f}x baseline",
                'ranges': [[p['start'], p['end']]],
                'layout': chosen_layout,
                'top_crop_x': top_crop_x,
                'subtitle_preset': args.preset,
                'words_per_group': args.words_per_group,
                'word_pop': args.word_pop,
                'uppercase': args.uppercase,
                'hook': f"CHAT LOST IT! ({p['ratio']:.1f}x) {em}",
                'burn_captions': True,
                'highlight_words': True,
                'post_caption': f"Chat went crazy during this moment! ({p['ratio']:.1f}x normal volume) {words_str}",
                'hashtags': ['#Gaming', '#Twitch', '#Shorts', '#Reels', '#Viral']
            })
        save(cuts_file, manifest)
    else:
        class SugArgs:
            pass
        s_args = SugArgs()
        s_args.transcript = str(transcript_file)
        s_args.video = str(video_path)
        s_args.out = str(cuts_file)
        s_args.min_duration = 15.0
        s_args.max_duration = 45.0
        s_args.max_reels = args.count
        s_args.default_layout = chosen_layout
        s_args.subtitle_preset = args.preset
        s_args.uppercase = args.uppercase
        s_args.font = args.font
        suggest_moments(s_args)
        
        m_data = load(cuts_file)
        for r in m_data.get('reels', []):
            r['words_per_group'] = args.words_per_group
            r['word_pop'] = args.word_pop
            r['top_crop_x'] = top_crop_x
        save(cuts_file, m_data)
        
    # 4. Render vertical 9:16 reels
    print(f"\n[5/5] Rendering {args.count} vertical 9:16 reels with hardware acceleration...", flush=True)
    class RendArgs:
        pass
    r_args = RendArgs()
    r_args.video = str(video_path)
    r_args.manifest = str(cuts_file)
    r_args.out = str(out_dir / 'exports')
    r_args.preset = 'fast'
    r_args.encoder = args.encoder
    r_args.bgm = args.bgm
    r_args.bgm_volume = args.bgm_volume
    r_args.overwrite = True
    render(r_args)
    
    # Verify & QA
    class VerArgs:
        pass
    v_args = VerArgs()
    v_args.folder = str(out_dir / 'exports')
    verify(v_args)
    
    print(f"\nSUCCESS! All reels generated and verified in: {out_dir / 'exports'}")
    print(f"Paste-ready social captions & hashtags: {out_dir / 'exports' / 'posting.md'}\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    
    auto_cmd = sub.add_parser('auto', help="End-to-end automatic video/stream to viral vertical reels")
    auto_cmd.add_argument('--video', default=None, help="Path to local input video MP4")
    auto_cmd.add_argument('--url', default=None, help="YouTube/Twitch stream URL (downloaded via yt-dlp)")
    auto_cmd.add_argument('--chat', default=None, help="Path to Twitch JSON or YouTube live_chat.json")
    auto_cmd.add_argument('--out', default='reels_output/auto_run', help="Output directory")
    auto_cmd.add_argument('--count', type=int, default=5, help="Number of reels to extract (default 5)")
    auto_cmd.add_argument('--preset', default='hormozi', choices=['hormozi', 'yellow_shadow', 'yellow', 'neon', 'classic', 'boxed', 'default'])
    auto_cmd.add_argument('--layout', default='auto', choices=['auto', 'fit', 'crop', 'split', 'pip'])
    auto_cmd.add_argument('--encoder', default='auto', choices=['auto', 'h264_nvenc', 'h264_videotoolbox', 'h264_qsv', 'libx264'])
    auto_cmd.add_argument('--bgm', default=None, help="Optional background music MP3 for auto-ducking")
    auto_cmd.add_argument('--bgm-volume', type=float, default=0.20, help="Background music volume relative to voice")
    auto_cmd.add_argument('--words-per-group', type=int, default=3, help="Words per subtitle card (e.g. 2-3 for fast retention)")
    auto_cmd.add_argument('--word-pop', action='store_true', default=True, help="Enable dynamic pop-bounce subtitle animation")
    auto_cmd.add_argument('--uppercase', action='store_true', default=True, help="Uppercase all subtitle words")
    auto_cmd.add_argument('--font', default='Arial', help="Subtitle font family")
    auto_cmd.add_argument('--model', default='base', help="Whisper model size (tiny, base, small, medium, large-v3)")
    auto_cmd.add_argument('--language', default=None, help="Spoken language code (e.g. en, hi)")
    auto_cmd.add_argument('--device', default='auto', help="Whisper device: auto (prefers cuda if available), cpu, cuda")
    auto_cmd.add_argument('--compute-type', default='auto', help="Compute type: auto (float16 for cuda, int8 for cpu)")
    auto_cmd.add_argument('--skip-intro', type=float, default=15.0, help="Stream intro minutes to ignore")
    auto_cmd.set_defaults(func=auto_pipeline)

    a = sub.add_parser('analyze')
    a.add_argument('--video', required=True)
    a.add_argument('--out', required=True)
    a.add_argument('--samples', type=int, default=48)
    a.set_defaults(func=analyze)
    
    t = sub.add_parser('transcribe')
    t.add_argument('--video', required=True)
    t.add_argument('--out', required=True)
    t.add_argument('--model', default='base')
    t.add_argument('--language', default=None)
    t.add_argument('--device', default='auto')
    t.add_argument('--compute-type', default='auto')
    t.set_defaults(func=transcribe)
    
    r = sub.add_parser('render')
    r.add_argument('--video', required=True)
    r.add_argument('--manifest', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--preset', default='fast')
    r.add_argument('--encoder', default='auto', choices=['auto', 'h264_nvenc', 'h264_videotoolbox', 'h264_qsv', 'libx264'])
    r.add_argument('--bgm', default=None, help="Background music audio file for auto-ducking")
    r.add_argument('--bgm-volume', type=float, default=0.20, help="Background music volume")
    r.add_argument('--overwrite', action='store_true')
    r.set_defaults(func=render)
    
    v = sub.add_parser('verify')
    v.add_argument('--folder', required=True)
    v.set_defaults(func=verify)
    
    sm = sub.add_parser('suggest-moments')
    sm.add_argument('--transcript', required=True)
    sm.add_argument('--video', default=None, help="Optional video MP4 to fuse audio volume/scream spikes")
    sm.add_argument('--out', required=True)
    sm.add_argument('--min-duration', type=float, default=20.0)
    sm.add_argument('--max-duration', type=float, default=50.0)
    sm.add_argument('--max-reels', type=int, default=5)
    sm.add_argument('--default-layout', default='fit', choices=['fit', 'crop', 'split', 'pip'])
    sm.add_argument('--subtitle-preset', default='hormozi', choices=['hormozi', 'neon', 'classic', 'boxed', 'default'])
    sm.add_argument('--uppercase', action='store_true', default=True)
    sm.set_defaults(func=suggest_moments)
    
    ds = sub.add_parser('detect-silence')
    ds.add_argument('--video', required=True)
    ds.add_argument('--noise-db', type=float, default=-30.0)
    ds.add_argument('--min-duration', type=float, default=0.5)
    ds.add_argument('--out', default=None)
    ds.set_defaults(func=detect_silence)

    das = sub.add_parser('detect-audio-spikes')
    das.add_argument('--video', required=True, help="Video MP4 to analyze for screams and loudness peaks")
    das.add_argument('--out', default=None, help="Output JSON path")
    das.add_argument('--top', type=int, default=10, help="Number of peaks to report")
    das.add_argument('--bucket', type=float, default=1.0, help="RMS bucket size in seconds")
    das.add_argument('--window', type=float, default=3.0, help="Rolling baseline window in minutes")
    das.add_argument('--min-ratio', type=float, default=2.0, help="Multiplier over baseline")
    das.add_argument('--gap', type=float, default=60.0, help="Minimum gap between distinct audio peaks in seconds")
    das.set_defaults(func=detect_audio_spikes)

    dfc = sub.add_parser('detect-facecam')
    dfc.add_argument('--video', required=True, help="Video MP4 to inspect for facecam ROI")
    dfc.add_argument('--out', default=None, help="Optional JSON output path")
    dfc.set_defaults(func=detect_facecam_cmd)

    cs = sub.add_parser('find-chat-spikes')
    cs.add_argument('--chat', required=True, help="Path to Twitch chat.json or YouTube .live_chat.json")
    cs.add_argument('--out', default='cuts.json', help="Output cuts.json manifest path")
    cs.add_argument('--top', type=int, default=10, help="Number of top spike clips to generate (default 10)")
    cs.add_argument('--before', type=float, default=20.0, help="Seconds before the spike to start clip")
    cs.add_argument('--after', type=float, default=10.0, help="Seconds after the spike to end clip")
    cs.add_argument('--gap', type=float, default=120.0, help="Minimum gap between distinct clips in seconds")
    cs.add_argument('--bucket', type=float, default=20.0, help="Sliding window size in seconds (default 20)")
    cs.add_argument('--window', type=float, default=5.0, help="Rolling baseline window in minutes")
    cs.add_argument('--min-ratio', type=float, default=2.0, help="Minimum spike multiplier over baseline (e.g. 2.0x)")
    cs.add_argument('--skip-intro', type=float, default=15.0, help="Minutes to skip at the start of stream (default 15)")
    cs.add_argument('--default-layout', default='fit', choices=['fit', 'crop', 'split', 'pip'])
    cs.add_argument('--subtitle-preset', default='yellow_shadow', choices=['yellow_shadow', 'hormozi', 'yellow', 'neon', 'classic', 'boxed', 'default'])
    cs.add_argument('--uppercase', action='store_true', default=True)
    cs.set_defaults(func=find_chat_spikes)
    
    args = p.parse_args()
    if hasattr(args, 'samples') and args.samples < 1:
        p.error('--samples must be positive')
    args.func(args)
    if hasattr(args, 'samples') and args.samples < 1:
        p.error('--samples must be positive')
    args.func(args)


if __name__ == '__main__':
    main()
