---
name: seismic-waveform-analysis
description: "Process seismic waveform data and perform P/S wave phase picking. Use when loading .npz seismic trace files, detecting P-wave and S-wave arrival times, applying STA/LTA (Short Term Average / Long Term Average) algorithms, filtering seismic signals, or computing pick quality metrics. Covers numpy trace loading, bandpass filtering, characteristic function computation, and F1-based evaluation."
---

# Seismic Waveform Analysis & Phase Picking

## Overview

This skill covers processing seismic waveform data (typically stored as `.npz` files) and detecting P-wave and S-wave arrival times. The standard evaluation metric is F1 score: a pick is "correct" if it's within 0.1 seconds of the human-labeled ground truth.

## Loading Trace Data

Seismic traces are typically stored as `.npz` files with these fields:

```python
import numpy as np
import os, glob

data_dir = '/root/data/'
trace_files = sorted(glob.glob(os.path.join(data_dir, '*.npz')))

for trace_path in trace_files:
    trace = np.load(trace_path, allow_pickle=True)
    
    # Required fields:
    waveform = trace['data']       # Shape: (n_samples, n_channels) e.g. (12000, 3)
    dt = float(trace['dt'])        # Sampling interval in seconds
    channels = str(trace['channels'])  # e.g. "DPE,DPN,DPZ"
    
    n_samples = waveform.shape[0]
    n_channels = waveform.shape[1]
    duration = n_samples * dt      # Total duration in seconds
```

### ⚠️ CRITICAL: Understanding the Data Format

- `data`: 2D array, shape `(n_samples × n_channels)`. Each column is one component (E, N, Z or similar).
- `dt`: Sampling interval in **seconds** (e.g., 0.01 = 100 Hz). NOT frequency.
- To convert time tolerance to index tolerance: `index_tolerance = 0.1 / dt` (for 0.1s tolerance)

## Preprocessing: Bandpass Filter

Seismic signals need bandpass filtering to remove noise before phase picking.

```python
from scipy.signal import butter, filtfilt

def bandpass_filter(data, lowcut, highcut, fs, order=4):
    """Apply Butterworth bandpass filter."""
    nyquist = fs / 2.0
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data, axis=0)

# Typical filter parameters for P-wave picking: 1-10 Hz
# For S-wave picking: 0.5-5 Hz (lower frequencies)
fs = 1.0 / dt  # Sampling frequency in Hz

filtered_p = bandpass_filter(waveform, 1.0, 10.0, fs)   # P-wave band
filtered_s = bandpass_filter(waveform, 0.5, 5.0, fs)    # S-wave band
```

### Filter Parameters

| Wave | Lowcut (Hz) | Highcut (Hz) | Rationale |
|------|-------------|-------------|-----------|
| P-wave | 1.0-2.0 | 8.0-15.0 | P-waves are higher frequency |
| S-wave | 0.5-1.0 | 3.0-7.0 | S-waves are lower frequency |

## STA/LTA Phase Picking (Standard Method)

The Short Term Average / Long Term Average (STA/LTA) ratio is the standard method for seismic phase detection.

```python
def sta_lta(signal, sta_len, lta_len):
    """
    Compute STA/LTA characteristic function.
    
    Args:
        signal: 1D array of seismic amplitude
        sta_len: Short-term average window length (in samples)
        lta_len: Long-term average window length (in samples)
    
    Returns:
        ratio: STA/LTA ratio array
    """
    n_samples = len(signal)
    sta = np.zeros(n_samples)
    lta = np.zeros(n_samples)
    
    # Compute squared amplitude (characteristic function)
    char_func = signal ** 2
    
    # Compute moving averages
    for i in range(lta_len, n_samples):
        sta[i] = np.mean(char_func[i - sta_len:i])
        lta[i] = np.mean(char_func[i - lta_len:i])
    
    # Avoid division by zero
    ratio = np.zeros(n_samples)
    mask = lta > 0
    ratio[mask] = sta[mask] / lta[mask]
    
    return ratio
```

### ⚠️ CRITICAL: Window Size Selection

| Wave | STA Window (seconds) | LTA Window (seconds) | Trigger Threshold |
|------|---------------------|---------------------|-------------------|
| P-wave | 0.5-1.0 | 5.0-10.0 | 3.0-5.0 |
| S-wave | 1.0-2.0 | 10.0-30.0 | 2.0-4.0 |

Convert to samples: `sta_samples = int(sta_seconds / dt)`, `lta_samples = int(lta_seconds / dt)`

```python
# P-wave picking
sta_len_p = int(0.5 / dt)    # 0.5 second STA
lta_len_p = int(8.0 / dt)    # 8 second LTA
ratio_p = sta_lta(filtered_p[:, 2], sta_len_p, lta_len_p)  # Use Z component for P

# Find first trigger above threshold
threshold_p = 3.5
p_picks = np.where(ratio_p[lta_len_p:] > threshold_p)[0] + lta_len_p
first_p_pick = p_picks[0] if len(p_picks) > 0 else None

# S-wave picking (use horizontal components)
# Combine E and N components
en_amplitude = np.sqrt(filtered_s[:, 0]**2 + filtered_s[:, 1]**2)
sta_len_s = int(1.0 / dt)    # 1 second STA
lta_len_s = int(15.0 / dt)   # 15 second LTA
ratio_s = sta_lta(en_amplitude, sta_len_s, lta_len_s)

threshold_s = 3.0
s_picks = np.where(ratio_s[lta_len_s:] > threshold_s)[0] + lta_len_s
# S-wave should come AFTER P-wave
if first_p_pick is not None:
    s_picks = s_picks[s_picks > first_p_pick]
first_s_pick = s_picks[0] if len(s_picks) > 0 else None
```

## Optimizing for F1 Score

The evaluation uses F1 score. A pick is correct if within 0.1 seconds of ground truth.

```python
def evaluate_picks(predictions, ground_truth, dt, tolerance_sec=0.1):
    """
    Compute F1 score for phase picks.
    
    Args:
        predictions: list of predicted pick indices
        ground_truth: list of true pick indices
        dt: sampling interval in seconds
        tolerance_sec: tolerance in seconds (default 0.1s)
    """
    tolerance_idx = int(tolerance_sec / dt)
    
    tp = 0  # True positives
    matched_gt = set()
    
    for pred in predictions:
        for gt_idx, gt in enumerate(ground_truth):
            if gt_idx not in matched_gt and abs(pred - gt) <= tolerance_idx:
                tp += 1
                matched_gt.add(gt_idx)
                break
    
    fp = len(predictions) - tp   # False positives (extra picks)
    fn = len(ground_truth) - tp   # False negatives (missed picks)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return f1, precision, recall
```

### Strategy for Maximizing F1

- **P-wave target: F1 >= 0.7**. Be moderately aggressive — better to have a few extra picks than miss real arrivals.
- **S-wave target: F1 >= 0.6**. S-waves are harder to detect — lower threshold helps recall.
- **Don't output too many picks.** Each false positive reduces precision. Quality over quantity.
- **Use the correct component.** P-waves are best seen on the vertical (Z) component. S-waves are best seen on horizontal (E, N) components.

## Output Format

```python
import csv

with open('/root/results.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['file_name', 'phase', 'pick_idx'])
    
    for trace_file in trace_files:
        fname = os.path.basename(trace_file)
        # ... pick P and S waves ...
        if p_pick is not None:
            writer.writerow([fname, 'P', int(p_pick)])
        if s_pick is not None:
            writer.writerow([fname, 'S', int(s_pick)])
```

**Note**: It's acceptable to output 0, 1, or multiple picks per file per phase. Each row is one pick.

## Common Mistakes

- **Using `dt` as frequency instead of sampling interval.** `dt` is the time between samples in seconds. Frequency = `1/dt`. Confusing these gives window sizes off by orders of magnitude.
- **Not bandpass filtering before STA/LTA.** Raw seismic data has lots of noise. Without filtering, STA/LTA triggers on noise, not signal.
- **Using the wrong component for P/S picking.** P-waves → vertical (Z) component. S-waves → horizontal (E, N) components. Using the wrong component reduces detection quality.
- **Setting STA/LTA threshold too high.** Threshold 10+ means only the strongest arrivals trigger. For F1 optimization, threshold 3-5 is better.
- **Forgetting that S-wave must come AFTER P-wave.** If your S-wave pick is before the P-wave pick, it's wrong.
- **Outputting pick indices from filtered data without accounting for filter delay.** `filtfilt` is zero-phase (no delay), but `lfilter` introduces delay. Use `filtfilt` or compensate.
- **Tolerance mismatch.** Evaluation uses 0.1 seconds tolerance. Convert to index: `tolerance_idx = int(0.1 / dt)`. At dt=0.01s, that's 10 samples.
- **Outputting duplicate picks.** STA/LTA ratio stays above threshold for many samples. Take only the FIRST trigger point above threshold, not all of them.

## Sanity Checks

- P-wave pick index should be > 0 and < n_samples
- S-wave pick index should be > P-wave pick index (S arrives after P)
- Pick indices should be integers
- Each row in results.csv has exactly 3 columns: file_name, phase, pick_idx
- phase column contains only "P" or "S"
- For 100 traces, you should output roughly 100-200 picks total (not 0, not 1000+)
