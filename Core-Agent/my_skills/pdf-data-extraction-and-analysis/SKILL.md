---
name: pdf-data-extraction-and-analysis
description: "Extract data from PDF documents and process it in Excel/CSV. Use when reading tables, text, or structured data from PDF files, creating pivot tables in Excel, performing data analysis with pandas, or generating Excel reports with formulas and formatting. Covers pdfplumber, pypdf, openpyxl, pandas pivot tables, and Excel formula construction."
---

# PDF Data Extraction & Excel Analysis

## Overview

This skill covers the common workflow of extracting data from PDF documents and processing/analyzing it in Excel or CSV format. Many tasks require: (1) reading data from PDF → (2) transforming/analyzing → (3) writing structured output to Excel/CSV.

## PDF Text Extraction

```python
import pdfplumber

with pdfplumber.open('/root/data/document.pdf') as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

### pdfplumber vs pypdf

| Library | Best For | Limitation |
|---------|----------|-----------|
| **pdfplumber** | Tables, structured data, layout-aware | Slower |
| **pypdf** | Plain text, simple extraction | Can't extract tables well |

**Use pdfplumber for tables. Use pypdf for plain text.**

## PDF Table Extraction

```python
import pdfplumber
import pandas as pd

with pdfplumber.open('/root/data/document.pdf') as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# Combine all tables
combined_df = pd.concat(all_tables, ignore_index=True)
```

### ⚠️ CRITICAL: pdfplumber Table Extraction Quirks

- Tables may span multiple pages — always iterate over ALL pages
- Header row may not be on the first page — check if first row looks like data
- Some tables have merged cells — pdfplumber returns `None` for merged cells
- Numbers may be extracted as strings — always convert: `pd.to_numeric(col, errors='coerce')`
- Table boundaries may not be detected — try `extract_tables(table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"})` if default fails

## PDF to Excel Pipeline

The most common pattern: read PDF → process → write Excel.

```python
import pdfplumber
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, numbers

# Step 1: Extract from PDF
with pdfplumber.open('/root/data/report.pdf') as pdf:
    tables = []
    for page in pdf.pages:
        t = page.extract_tables()
        for table in t:
            if table and len(table) > 1:
                df = pd.DataFrame(table[1:], columns=table[0])
                tables.append(df)

data = pd.concat(tables, ignore_index=True)

# Step 2: Clean data
for col in data.columns:
    data[col] = pd.to_numeric(data[col], errors='coerce')
data = data.dropna()

# Step 3: Write to Excel with formatting
wb = Workbook()
ws = wb.active
ws.title = "Analysis"

# Write headers
for j, col_name in enumerate(data.columns, 1):
    cell = ws.cell(row=1, column=j, value=col_name)
    cell.font = Font(bold=True)

# Write data
for i, row in enumerate(data.itertuples(index=False), 2):
    for j, value in enumerate(row, 1):
        ws.cell(row=i, column=j, value=value)

wb.save('/root/output/analysis.xlsx')
```

## Excel Pivot Tables

### With pandas (simpler, data-focused)

```python
import pandas as pd

# Read source data
df = pd.read_excel('/root/data.xlsx')

# Create pivot table
pivot = pd.pivot_table(
    df,
    index='STATE',           # Row labels
    values='POPULATION_2023', # Values to aggregate
    aggfunc='sum'            # Aggregation function
)

# Write to Excel
pivot.to_excel('/root/output/report.xlsx', sheet_name='Population by State')
```

### With openpyxl (formatted, multi-sheet)

```python
from openpyxl import load_workbook, Workbook

# Multi-sheet workbook with multiple pivot tables
wb = Workbook()

# Sheet 1: Population by State
ws1 = wb.active
ws1.title = "Population by State"
pivot1 = pd.pivot_table(df, index='STATE', values='POPULATION_2023', aggfunc='sum')
ws1.append(['STATE', 'Sum of POPULATION_2023'])
for state, value in pivot1.itertuples():
    ws1.append([state, int(value)])

# Sheet 2: Earners by State
ws2 = wb.create_sheet("Earners by State")
pivot2 = pd.pivot_table(df, index='STATE', values='EARNERS', aggfunc='sum')
ws2.append(['STATE', 'Sum of EARNERS'])
for state, value in pivot2.itertuples():
    ws2.append([state, int(value)])

# Sheet 3: Regions by State (COUNT)
ws3 = wb.create_sheet("Regions by State")
pivot3 = pd.pivot_table(df, index='STATE', values='SA2', aggfunc='count')
ws3.append(['STATE', 'Count of SA2 regions'])
for state, value in pivot3.itertuples():
    ws3.append([state, int(value)])

# Sheet 4: State Income Quartile
ws4 = wb.create_sheet("State Income Quartile")
# Create quartile labels
df['Quarter'] = pd.qcut(df['MEDIAN_INCOME'], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
pivot4 = pd.pivot_table(df, index='STATE', columns='Quarter', values='EARNERS', aggfunc='sum')
ws4.append(['STATE', 'Q1', 'Q2', 'Q3', 'Q4'])
for state, row in pivot4.iterrows():
    ws4.append([state] + [int(v) if pd.notna(v) else 0 for v in row])

wb.save('/root/output/demographic_analysis.xlsx')
```

### ⚠️ CRITICAL: Quartile Labeling

- `pd.qcut()` divides data into **equal-frequency** bins (same number of rows per quartile)
- Labels: Q1 = lowest 25%, Q2 = 25-50%, Q3 = 50-75%, Q4 = highest 25%
- If the task says "based on MEDIAN_INCOME ranges", use `pd.qcut(df['MEDIAN_INCOME'], q=4, labels=['Q1','Q2','Q3','Q4'])`

### ⚠️ CRITICAL: Aggregation Functions

| Task Says | Use |
|-----------|-----|
| "Sum of X" | `aggfunc='sum'` |
| "Count of X" | `aggfunc='count'` |
| "Average/Mean of X" | `aggfunc='mean'` |
| "Number of X" | `aggfunc='count'` (NOT sum!) |

## Excel Formula Construction

**Always use Excel formulas, NOT hardcoded Python-computed values**, unless the task explicitly says otherwise.

```python
from openpyxl import load_workbook

wb = load_workbook('/root/output/report.xlsx')
ws = wb.active

# ✅ CORRECT: Use formulas
ws.cell(row=2, column=3, value='=SUM(A2:A100)')
ws.cell(row=2, column=4, value='=B2/C2')

# ❌ WRONG: Hardcode computed values
ws.cell(row=2, column=3, value=1234.56)  # Loses dynamic behavior

# Recalculate formulas (requires LibreOffice)
import subprocess
subprocess.run(['libreoffice', '--headless', '--calc', '--convert-to', 'xlsx',
                '/root/output/report.xlsx'], check=True, capture_output=True)
```

## Common Mistakes

- **Using pypdf for table extraction.** pypdf can't extract tables well. Use pdfplumber for any tabular data.
- **Not converting PDF-extracted strings to numbers.** pdfplumber returns everything as strings. Always use `pd.to_numeric(col, errors='coerce')`.
- **Using `aggfunc='sum'` when the task says "count".** Read the task carefully: "Sum of X" vs "Count of X" vs "Number of X".
- **Hardcoding Excel values instead of using formulas.** The task may require dynamic Excel formulas. Check the task requirements.
- **Not iterating over ALL PDF pages.** Tables often span multiple pages. Always loop: `for page in pdf.pages`.
- **Wrong quartile definition.** `pd.qcut` = equal-frequency (default). `pd.cut` = equal-width bins. They produce very different results.
- **Forgetting to handle `None` from merged PDF cells.** pdfplumber returns `None` for merged cells. Filter: `data = data.dropna()` or fill with appropriate defaults.
- **Sheet name errors.** Excel sheet names are case-sensitive and must match exactly what the task specifies (e.g., "Population by State" not "population_by_state").

## Sanity Checks

- Number of rows in each pivot table should match the number of unique values in the index column
- Sum of all pivot values should equal the total in the source data
- Quartile labels (Q1-Q4) should all be present in the output
- Output Excel file should have the correct number of sheets
- Each sheet name should exactly match the task specification
- Numeric columns should be actual numbers, not strings
