import json
import sys
from pathlib import Path
import pytest
import numpy as np

# Ensure skills script is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "video-to-reels" / "scripts"))
import reels


def test_ffmpeg_and_hardware_encoder():
    ff = reels.ffmpeg()
    assert ff, "FFmpeg binary must be found"
    enc = reels.detect_hardware_encoder()
    assert enc in ("h264_nvenc", "h264_videotoolbox", "h264_qsv", "libx264")
    print(f"Detected hardware encoder: {enc}")


def test_phrases_word_grouping():
    transcript = {
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "one two three four five six seven eight",
                "words": [
                    {"start": 0.0, "end": 0.2, "word": "one"},
                    {"start": 0.2, "end": 0.4, "word": "two"},
                    {"start": 0.4, "end": 0.6, "word": "three"},
                    {"start": 0.6, "end": 0.8, "word": "four"},
                    {"start": 0.8, "end": 1.0, "word": "five"},
                    {"start": 1.0, "end": 1.2, "word": "six"},
                    {"start": 1.2, "end": 1.4, "word": "seven"},
                    {"start": 1.4, "end": 1.6, "word": "eight"},
                ]
            }
        ]
    }
    # Test grouping with max_words=3 (short-retention style)
    grouped = reels.phrases(transcript, max_words=3)
    assert len(grouped) == 3
    assert len(grouped[0]["words"]) == 3
    assert grouped[0]["text"] == "one two three"
    assert len(grouped[1]["words"]) == 3
    assert grouped[1]["text"] == "four five six"
    assert len(grouped[2]["words"]) == 2
    assert grouped[2]["text"] == "seven eight"


def test_caption_file_generation_with_pop(tmp_path):
    sub_path = tmp_path / "test_pop.ass"
    reel = {
        "name": "test_pop",
        "ranges": [[0.0, 3.0]],
        "subtitle_preset": "hormozi",
        "word_pop": True,
        "uppercase": True,
        "burn_captions": True,
        "highlight_words": True,
        "hook": "TEST HOOK! 🔥",
        "captions": [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "INSANE CLUTCH MOMENT",
                "words": [
                    {"start": 0.0, "end": 0.6, "word": "INSANE"},
                    {"start": 0.6, "end": 1.2, "word": "CLUTCH"},
                    {"start": 1.2, "end": 2.0, "word": "MOMENT"},
                ]
            }
        ]
    }
    event_count = reels.caption_file(sub_path, reel, {}, 1080, 1920, "Arial", 3.0)
    assert event_count >= 1
    content = sub_path.read_text(encoding="utf-8-sig")
    assert "Style: Caption,Arial" in content
    assert "Style: Hook,Arial" in content
    assert r"\fscx115\fscy115\t(0,80,\fscx100\fscy100)" in content
    assert r"\k" in content


def test_audio_spike_detection():
    # Generate 10 seconds of synthetic audio with a spike at 5 seconds
    sr = 16000
    audio = np.random.normal(0, 100, sr * 10).astype(np.float32)
    # Spike at 5.0s
    audio[5*sr : int(5.5*sr)] += np.random.normal(0, 1500, int(0.5*sr))

    # Test helper
    samples_per_bucket = sr
    num_buckets = len(audio) // samples_per_bucket
    rms_arr = np.array([float(np.sqrt(np.mean(audio[i*sr:(i+1)*sr]**2))) for i in range(num_buckets)])
    baseline = np.median(rms_arr)
    spike_idx = int(np.argmax(rms_arr))
    assert spike_idx == 5
    assert rms_arr[spike_idx] / baseline > 2.0
