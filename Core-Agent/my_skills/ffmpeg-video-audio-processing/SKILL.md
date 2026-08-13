---
name: ffmpeg-video-audio-processing
description: "Process video and audio files using ffmpeg and Python audio libraries. Use when detecting or removing silence from videos, converting media formats, extracting audio tracks, analyzing audio levels, compressing video, or performing time-based video editing. Covers ffmpeg command construction, pydub silence detection, dBFS thresholds, and codec selection."
---

# FFmpeg Video & Audio Processing

## Overview

This skill covers processing video and audio files using `ffmpeg` (command-line) and Python libraries (`pydub`, `scipy`). Common tasks: silence detection/removal, format conversion, audio analysis, video compression.

## Checking Available Tools

```python
import subprocess

# Check ffmpeg
result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
if result.returncode != 0:
    # Install if missing
    subprocess.run(['apt-get', 'update', '-qq'], check=True)
    subprocess.run(['apt-get', 'install', '-y', '-qq', 'ffmpeg'], check=True)

# Check Python audio libraries
try:
    from pydub import AudioSegment
except ImportError:
    subprocess.run(['pip', 'install', 'pydub'], check=True)
    from pydub import AudioSegment
```

## Extracting Audio from Video

```python
# Extract audio as WAV (lossless, best for analysis)
subprocess.run([
    'ffmpeg', '-i', 'input_video.mp4',
    '-vn',                    # No video
    '-acodec', 'pcm_s16le',   # 16-bit PCM
    '-ar', '16000',           # 16kHz sample rate
    '-ac', '1',               # Mono
    '-y',                     # Overwrite
    'audio_track.wav'
], check=True)
```

## Silence Detection with pydub

```python
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

audio = AudioSegment.from_file('audio_track.wav', format='wav')

# Detect non-silent segments
# min_silence_len: minimum silence duration (ms) to split on
# silence_thresh: dBFS threshold below which is considered silence
nonsilent_ranges = detect_nonsilent(
    audio,
    min_silence_len=500,      # 500ms minimum silence
    silence_thresh=-40        # -40 dBFS threshold
)
```

### ⚠️ CRITICAL: Understanding dBFS Thresholds

| dBFS Value | Sound Level       | Use For |
|-----------|-------------------|---------|
| -20 dBFS  | Loud              | Only detect very quiet silence |
| -30 dBFS  | Normal speech     | Moderate silence detection |
| **-40 dBFS** | **Quiet room**  | **Default — good starting point** |
| -50 dBFS  | Very quiet        | Aggressive silence removal |
| -60 dBFS  | Near absolute zero | Almost everything is "non-silent" |

**Lower (more negative) = less silence detected.** Start with -40 dBFS and adjust if needed.

### ⚠️ CRITICAL: Silence Detection Parameters

| Parameter | Meaning | Typical Value |
|-----------|---------|--------------|
| `min_silence_len` | Minimum silence duration to trigger a split (ms) | 300-1000ms |
| `silence_thresh` | dBFS level below which is "silent" | -40 to -50 |
| `seek_step` | Search granularity (ms) — lower = more precise but slower | 1-10ms |

## Removing Silence and Concatenating

```python
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

audio = AudioSegment.from_file('input_video.mp4')
nonsilent = detect_nonsilent(audio, min_silence_len=500, silence_thresh=-40)

# Build output from non-silent segments
output = AudioSegment.empty()
for start, end in nonsilent:
    output += audio[start:end]

# Export
output.export('audio_no_silence.wav', format='wav')
```

## Video Silence Removal (ffmpeg + pydub)

The typical workflow for removing silence from video:

```python
import subprocess, json
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

# Step 1: Get original video duration
probe = subprocess.run(
    ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', 'input_video.mp4'],
    capture_output=True, text=True, check=True
)
original_duration = float(json.loads(probe.stdout)['format']['duration'])

# Step 2: Extract audio and detect non-silent ranges
audio = AudioSegment.from_file('input_video.mp4')
nonsilent = detect_nonsilent(audio, min_silence_len=500, silence_thresh=-40)

# Step 3: Build ffmpeg filter to concatenate non-silent video segments
# Each nonsilent range becomes a segment to keep
filters = []
for i, (start_ms, end_ms) in enumerate(nonsilent):
    start_sec = start_ms / 1000.0
    end_sec = end_ms / 1000.0
    duration = end_sec - start_sec
    filters.append(f"trim=start={start_sec}:end={end_sec},setpts=PTS-STARTPTS")

# Join all segments
filter_complex = "[0:v]" + "[v]".join(f"[{i}]{f}[{i}v];" for i, f in enumerate(filters))
# Simplified approach: use concat demuxer
```

### Alternative: Simpler ffmpeg approach using concat file

```python
# Write segment list for ffmpeg concat demuxer
with open('segments.txt', 'w') as f:
    for start_ms, end_ms in nonsilent:
        start_sec = start_ms / 1000.0
        duration = (end_ms - start_ms) / 1000.0
        f.write(f"file 'segment_{start_ms}.ts'\n")

# Extract each segment
for start_ms, end_ms in nonsilent:
    start_sec = start_ms / 1000.0
    duration = (end_ms - start_ms) / 1000.0
    out_file = f'segment_{start_ms}.ts'
    subprocess.run([
        'ffmpeg', '-ss', str(start_sec), '-t', str(duration),
        '-i', 'input_video.mp4',
        '-c', 'copy', '-y', out_file
    ], check=True, capture_output=True)

# Concatenate
subprocess.run([
    'ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'segments.txt',
    '-c', 'copy', '-y', 'compressed_video.mp4'
], check=True)
```

## Computing Compression Report

```python
import json

# Get compressed duration
probe = subprocess.run(
    ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', 'compressed_video.mp4'],
    capture_output=True, text=True, check=True
)
compressed_duration = float(json.loads(probe.stdout)['format']['duration'])

removed_duration = original_duration - compressed_duration
compression_pct = (removed_duration / original_duration) * 100

# Build segments_removed list
segments_removed = []
for start_ms, end_ms in silent_ranges:
    segments_removed.append({
        "start": round(start_ms / 1000.0, 2),
        "end": round(end_ms / 1000.0, 2),
        "duration": round((end_ms - start_ms) / 1000.0, 2)
    })

report = {
    "original_duration_seconds": round(original_duration, 2),
    "compressed_duration_seconds": round(compressed_duration, 2),
    "removed_duration_seconds": round(removed_duration, 2),
    "compression_percentage": round(compression_pct, 2),
    "segments_removed": segments_removed
}

with open('compression_report.json', 'w') as f:
    json.dump(report, f, indent=2)
```

## Audio Level Analysis

```python
from pydub import AudioSegment
import math

audio = AudioSegment.from_file('audio.wav')

# Basic level metrics
loudness_dbfs = audio.dBFS                    # Overall loudness in dBFS
max_amplitude = audio.max_dBFS                # Peak amplitude
# RMS (Root Mean Square) — perceived loudness
rms = audio.rms
rms_dbfs = 20 * math.log10(rms / 32767) if rms > 0 else -float('inf')

# Per-chunk analysis (e.g., 1-second chunks)
chunk_length_ms = 1000
chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
chunk_levels = [chunk.dBFS for chunk in chunks if len(chunk) == chunk_length_ms]
```

## Common Mistakes

- **Using wrong `silence_thresh`.** -20 dBFS is too loud (treats normal speech as silence). -60 dBFS is too quiet (detects nothing). Start with -40 dBFS.
- **Forgetting `setpts=PTS-STARTPTS` in ffmpeg trim filter.** Without resetting timestamps, segments won't concatenate correctly — you get black gaps between segments.
- **Using `-c copy` with incompatible segment formats.** If segments have different codecs/parameters, concat demuxer fails. Use matching parameters or re-encode.
- **Not handling audio with no silence.** If the entire audio is non-silent, `detect_nonsilent` returns one range covering the whole file. Handle this edge case.
- **Confusing `min_silence_len` with `seek_step`.** `min_silence_len` is the minimum silence duration to detect; `seek_step` is the search granularity. They serve different purposes.
- **Using `AudioSegment.silent()` instead of `AudioSegment.empty()`.** `silent()` creates actual silence audio; `empty()` creates a zero-length segment for concatenation.
- **Not installing ffmpeg before use.** Docker environments may not have ffmpeg pre-installed. Always check and install if missing.
- **Wrong segment time units.** `pydub` uses milliseconds; `ffmpeg -ss` uses seconds. Always convert: `start_sec = start_ms / 1000.0`.

## Sanity Checks

- `compressed_duration <= original_duration` (can't be longer after removing silence)
- `removed_duration = original_duration - compressed_duration` (math must add up)
- `compression_percentage` is between 0 and 100
- Each segment in `segments_removed` has `start < end`
- Sum of all removed durations ≈ `removed_duration`
- The output video should still be playable (not corrupted)
