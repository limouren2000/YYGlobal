---
name: usgs-flood-analysis
description: "End-to-end workflow for detecting flood events from USGS stream gage data. Use when analyzing USGS water level or streamflow data to identify flood events, comparing gage heights to NWS flood stage thresholds, or processing instantaneous (15-min) gage data into daily summaries. Covers dataretrieval API usage, NWS threshold download, daily-max aggregation, flood-day counting, and CSV output formatting."
---

# USGS Flood Analysis — End-to-End Workflow

## Overview

This skill walks through the complete pipeline for detecting floods from USGS gage data:
download instantaneous water levels → aggregate to daily maximum → compare against NWS flood stage thresholds → count flood days → output CSV.

The agent must perform **all three data steps**: (1) download gage heights from USGS, (2) download flood stage thresholds from NWS, (3) merge and compare. Missing any one of these will produce wrong results.

## Required Packages

The Docker environment has these pre-installed:
```
pandas==2.2.3
dataretrieval==1.0.10
```

Standard library modules available: `csv`, `json`, `os`, `urllib`, `io`, `datetime`.

## Step 1: Read Station IDs

```python
with open('/root/data/michigan_stations.txt', 'r') as f:
    station_ids = [line.strip() for line in f if line.strip()]
```

**Station IDs are 8-digit strings with leading zeros** (e.g., `'04124000'`). Never convert them to integers — you will lose the leading zero and fail to match thresholds.

## Step 2: Download Gage Height Data from USGS

Use the `dataretrieval` package to download **instantaneous values** (parameter `00065` = gage height in feet).

```python
from dataretrieval import nwis

all_data = {}
for site_id in station_ids:
    try:
        df, meta = nwis.get_iv(
            sites=site_id,
            start='2025-04-01',
            end='2025-04-07',
            parameterCd='00065'   # Gage height, feet — NOT 00060 (discharge)
        )
        if len(df) > 0:
            # Extract gage height column (exclude quality code columns ending in _cd)
            gage_col = [c for c in df.columns if '00065' in str(c) and '_cd' not in str(c)]
            if gage_col:
                all_data[site_id] = df[gage_col[0]]
    except Exception as e:
        print(f"Failed to download {site_id}: {e}")
```

### Critical: Use `get_iv()`, NOT `get_dv()`

| Function | Data Frequency | Availability |
|----------|---------------|--------------|
| `nwis.get_iv()` | ~15-minute intervals | **Widely available** — use this |
| `nwis.get_dv()` | Daily values | Often empty for gage height — do NOT rely on it |

Most USGS stations record gage height as instantaneous values. `get_dv()` frequently returns empty DataFrames for parameter `00065`. Always use `get_iv()` and aggregate yourself.

### Critical: Filter Quality Code Columns

The returned DataFrame has both value and quality code columns:
```
Columns: ['00065', '00065_cd', 'site_no']
                    ↑ value    ↑ quality code — IGNORE THIS
```

Always filter with: `[c for c in df.columns if '00065' in str(c) and '_cd' not in str(c)]`

## Step 3: Aggregate to Daily Maximum

**You MUST use daily maximum, NOT daily mean.** Flood stage is compared against the peak water level each day, not the average. A station might have a brief spike above flood stage that gets diluted in the mean.

```python
import pandas as pd

# df has datetime index and gage height values
daily_max = df.resample('D').max()
```

| Aggregation | Correct for Flood Detection? | Why |
|-------------|------------------------------|-----|
| `resample('D').max()` | ✅ **YES** | Captures peak water level |
| `resample('D').mean()` | ❌ NO | Dilutes short flood peaks below threshold |
| `resample('D').min()` | ❌ NO | Only shows lowest point |

## Step 4: Download Flood Stage Thresholds from NWS

The National Weather Service publishes flood stage thresholds for all USGS gages in a bulk CSV.

```python
import pandas as pd
import csv
import urllib.request
import io

nws_url = "https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv"
response = urllib.request.urlopen(nws_url)
content = response.read().decode('utf-8')
reader = csv.reader(io.StringIO(content))
headers = next(reader)
data = [row[:43] for row in reader]   # ⚠️ CRITICAL: truncate to 43 columns
nws_df = pd.DataFrame(data, columns=headers)
```

### ⚠️ CRITICAL: NWS CSV Column Mismatch Bug

The NWS CSV has a known data quality issue: **the header row has 43 columns but data rows have 44 columns**. If you don't truncate, `pd.DataFrame()` will raise a ValueError or silently misalign columns.

**Always truncate**: `data = [row[:43] for row in reader]`

### ⚠️ CRITICAL: -9999 Sentinel Values

Stations without a defined flood stage use `-9999` as a sentinel value. You **must** filter these out:

```python
nws_df['flood stage'] = pd.to_numeric(nws_df['flood stage'], errors='coerce')
nws_df = nws_df[nws_df['flood stage'] != -9999]
nws_df = nws_df[nws_df['flood stage'].notna()]
```

### NWS Flood Stage Categories

| Category | CSV Column | Use for Flood Detection? |
|----------|------------|--------------------------|
| Action Stage | `action stage` | ❌ No — monitoring level, not flooding |
| **Flood Stage** | **`flood stage`** | **✅ YES — this is the minor flood threshold** |
| Moderate Flood Stage | `moderate flood stage` | ❌ No — higher threshold |
| Major Flood Stage | `major flood stage` | ❌ No — highest threshold |

Use the `flood stage` column (minor flood stage). This is the standard definition of "flooding occurred."

### Match Thresholds to Station IDs

```python
thresholds = {}
for _, row in nws_df.iterrows():
    usgs_id = str(row['usgs id']).strip()
    flood = row['flood stage']
    if pd.notna(flood) and flood != -9999:
        thresholds[usgs_id] = float(flood)
```

## Step 5: Detect Flood Days and Output

```python
import csv, os

flood_results = []

for site_id, gage_series in all_data.items():
    # Get threshold for this station
    threshold = thresholds.get(site_id)
    if threshold is None:
        continue   # Station not in NWS database — skip

    # Aggregate to daily maximum
    daily_max = gage_series.resample('D').max()

    # Count days where daily max >= flood stage
    flood_days = int((daily_max >= threshold).sum())

    if flood_days > 0:
        flood_results.append({
            'station_id': site_id,
            'flood_days': flood_days
        })

# Sort by flood_days descending
flood_results.sort(key=lambda x: x['flood_days'], reverse=True)

# Write output
os.makedirs('/root/output', exist_ok=True)
with open('/root/output/flood_results.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['station_id', 'flood_days'])
    writer.writeheader()
    writer.writerows(flood_results)
```

## Common Mistakes

- **Using `get_dv()` instead of `get_iv()`.** Daily values for gage height (00065) are often unavailable. `get_dv()` returns empty DataFrame; you get zero stations. Always use `get_iv()` and aggregate.

- **Using daily mean instead of daily max.** `resample('D').mean()` dilutes short flood spikes. A station that floods for 3 hours then drops back below threshold will show no flooding in the mean but will show flooding in the max.

- **Forgetting to truncate NWS CSV rows to 43 columns.** Header has 43 columns, data rows have 44. Without `row[:43]`, pandas crashes or misaligns data.

- **Not filtering -9999 sentinel values.** Stations without a flood stage have `-9999` in the CSV. Comparing gage height >= -9999 makes every station appear to flood.

- **Using `action stage` instead of `flood stage`.** Action stage is for monitoring/preparation, not actual flooding. The correct column is `flood stage` (minor flood threshold).

- **Converting station IDs to integers.** Station IDs like `04124000` lose the leading zero when cast to int (`4124000`). Keep them as strings.

- **Not filtering `_cd` columns from USGS data.** The DataFrame has `00065` (value) and `00065_cd` (quality code). Using the wrong column gives garbage values.

- **Using parameter code `00060` instead of `00065`.** `00060` = discharge (cfs), `00065` = gage height (feet). Flood stage is in feet — you need gage height.

- **Including stations with 0 flood days in output.** The task says "I only want to keep stations that had at least one flood day." Filter with `if flood_days > 0`.

- **Hardcoding date range wrong.** The task specifies April 1-7, 2025. Use `start='2025-04-01', end='2025-04-07'` — this is inclusive on both ends.

- **Not wrapping API calls in try/except.** Some stations may be offline or have no data. Without error handling, one failure crashes the entire script.

- **Forgetting `os.makedirs` for output directory.** If `/root/output/` doesn't exist, the file write fails silently or throws. Always create it first.

## Sanity Checks

After producing output, verify:

- `flood_days` for every station is between **1 and 7** (the date range is 7 days).
- `station_id` values are **8-digit strings** (e.g., `'04124000'`, not `4124000`).
- CSV has exactly **two columns**: `station_id` and `flood_days`.
- **No station appears with flood_days = 0.**
- If a station's daily max gage heights are all well below its flood stage threshold, it correctly should NOT appear in the output.
- The total number of stations with flooding should be **much less than 79** (most stations don't flood in a given week).
