# LPR KPIs Analytics

A Windows desktop application for analyzing License Plate Recognition (LPR) camera performance data. Built with Python, CustomTkinter, SQLite, and Matplotlib.

Import daily camera statistics from Excel files and visualize fleet-wide and per-camera KPIs through an interactive dark-themed dashboard with 8 analysis tabs.

---

## Features

- **Excel Import** — Drag-and-drop `.xlsx` files with 25 standardized columns; automatic validation, deduplication (by date + camera), and persistent storage in SQLite.
- **Dashboard** — 4 KPI cards paired with time-series trend charts showing green/red segment coloring based on target thresholds.
- **Accuracy Analysis** — Per-camera accuracy distribution histogram and a table of underperforming cameras (below 85%).
- **Manual Review Analysis** — MR rate distribution, high-MR camera table, per-camera stacked bar breakdown of 7 review reasons, and a fleet-wide donut chart.
- **Archive Analysis** — Archive rate distribution, high-archive camera table, grouped bar chart of archive sub-types, and Potential Manual Link Rate for IN cameras.
- **Cameras** — Sortable per-camera KPI table with search and color-coded cells.
- **Trends** — Time-series line charts with camera and lot selectors for any KPI.
- **Outliers** — Statistical outlier detection using Z-score, IQR, threshold breach, and dominant review reason methods.
- **Export** — Full Excel report (4 sheets with color-coded cells) and PNG dashboard snapshot.
- **Caching** — Computed KPIs are cached in SQLite for instant tab switching; cache invalidates automatically on data import or deletion.
- **Global Filters** — Date range, lot, and direction filters apply across all tabs.

---

## System Requirements

- **OS**: Windows 10/11 (also runs on macOS/Linux with Python 3.11+)
- **Python**: 3.11 or later
- **Disk**: ~50 MB for application + dependencies; database grows with imported data
- **RAM**: 512 MB minimum; 2 GB recommended for large datasets

---

## Installation

1. **Clone or download** the repository:
   ```
   git clone <repository-url>
   cd Performance_Review
   ```

2. **Create a virtual environment** (recommended):
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # macOS/Linux
   ```

3. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

   Required packages:
   | Package | Version | Purpose |
   |---------|---------|---------|
   | customtkinter | >= 5.2.0 | Modern dark-themed UI framework |
   | pandas | >= 2.0.0 | Data manipulation and aggregation |
   | openpyxl | >= 3.1.0 | Excel file reading and writing |
   | matplotlib | >= 3.7.0 | Charts and visualizations |
   | Pillow | >= 10.0.0 | Image support for exports |

---

## How to Run

**Windows (double-click)**:
```
run.bat
```

**Command line**:
```
python main.py
```

The application will create `parking_analytics.db` in the project directory on first launch and open the main window at 1400x900 pixels.

---

## How to Import Data

1. Click the **Import Data** tab.
2. Click **Browse** and select an `.xlsx` file exported from the parking reporting system.
3. The file must contain exactly these 25 columns:

   | Column | Type | Description |
   |--------|------|-------------|
   | Date | Date | Report date (YYYY-MM-DD) |
   | Camera Name | Text | Unique camera identifier |
   | Camera Direction | Text | `IN` or `OUT` |
   | Lot Name | Text | Parking lot name |
   | TotalTransactions | Integer | Transactions processed |
   | TotalAccurated | Integer | Accurate transactions |
   | TotalInaccurated | Integer | Inaccurate transactions |
   | TotalArchived | Integer | Archived transactions |
   | TotalArchivedAccurated | Integer | Archived accurate |
   | TotalArchivedInaccurated | Integer | Archived inaccurate |
   | TotalManualReview | Integer | Sent to manual review |
   | TotalPrimaryLowConfidence | Integer | Primary low confidence |
   | TotalSecondaryLowConfidence | Integer | Secondary low confidence |
   | TotalSecondaryNotWorking | Integer | Secondary not working |
   | TotalDifferentReading | Integer | Different reading |
   | TotalMissingIdentifiers | Integer | Missing identifiers |
   | TotalNoInForOut | Integer | No IN for OUT |
   | TotalNoInFromMain | Integer | No IN from main |
   | TotalArchivedOCR | Integer | Archived by OCR reviewer |
   | TotalArchivedOPS | Integer | Archived by operations |
   | TotalArchivedAutoArchive | Integer | Archived automatically |
   | TotalPending | Integer | Pending transactions |
   | TotalManualLink | Integer | Manually linked |
   | TotalOCRReview | Integer | OCR review queue |
   | TotalLinked | Integer | Successfully linked |

4. Click **Import**. The tool validates the file, deduplicates by (date, camera_name), and reports inserted/skipped counts.
5. **Upload history** is shown below with the option to delete any import and its associated data.

**Deduplication**: Rows with the same (Date, Camera Name) combination as existing data are automatically skipped during import.

---

## Dashboard Guide

### 1. Dashboard

The main overview screen displays 4 panels in a 2x2 grid. Each panel has:
- A **KPI card** showing the current fleet-wide value with a color indicator (green/yellow/red).
- A **trend line chart** plotting that KPI over time with segment-by-segment green/red coloring based on whether each data point meets the target threshold.
- A **dashed yellow reference line** at the target threshold.

The 4 KPIs shown are: Overall Accuracy %, Overall Manual Review Rate, Overall Archive Rate, and Overall Linking Rate.

### 2. Import Data

File upload interface with drag-and-drop, validation feedback, import progress, and upload history with delete capability.

### 3. Accuracy Analysis

- **Histogram**: Distribution of per-camera accuracy values in 10% buckets (0-10%, 10-20%, ..., 90-100%). Bars below 85% are red; bars at/above 85% are green.
- **Underperforming Table**: Lists all cameras with accuracy below 85%, sorted ascending. Shows Camera Name, Lot, Direction, Accuracy %, Total Detected, Total Accurated, and Total Archived Accurated.

### 4. Manual Review Analysis

- **Histogram**: Distribution of per-camera manual review rate in 10% buckets. Bars above 35% are red.
- **High-MR Table**: Cameras exceeding 35% manual review rate, sorted descending.
- **Stacked Bar Chart**: Per-camera breakdown of the 7 manual review reasons as percentages of each camera's total manual reviews.
- **Fleet Donut Chart**: Fleet-wide breakdown of manual review reasons with dual-percentage legend (% of review and % of total detected).

### 5. Archive Analysis

- **Histogram**: Distribution of per-camera archive rate. Bars above 1% are red.
- **High-Archive Table**: Cameras exceeding 1% archive rate with archive sub-type percentages.
- **Grouped Bar Chart**: Three bars per camera showing Archive by Reviewer %, Archive by Ops %, and Archive by Auto %.
- **Potential Manual Link Rate (IN cameras)**: Horizontal bar chart showing the estimated proportion of archived OPS transactions that may have had a linkable IN transaction missed. Formula: `(TotalManualLink / TotalArchivedOPS) x 2 x 100`. Bars above 50% are flagged red.

### 6. Cameras

Sortable table of all cameras with per-camera KPI values. Color-coded cells for target KPIs (accuracy, manual review rate, linking rate, archive rate). Search bar for filtering by camera name.

### 7. Trends

Interactive time-series charts. Select a KPI from the dropdown, optionally filter by camera or lot, and view the daily trend with data point markers.

### 8. Outliers

Statistical outlier report combining four detection methods (see Understanding Outlier Detection below). Results are displayed in a filterable table with color-coded rows by flag type.

---

## KPI Definitions & Formulas

### Base Value

```
Total Detected = TotalTransactions + TotalArchived
```

All percentage KPIs use Total Detected as the denominator unless noted otherwise.

### Core KPIs

| KPI | Formula |
|-----|---------|
| **Accuracy %** | `(TotalAccurated + TotalArchivedAccurated) / TotalDetected x 100` |
| **Manual Review Rate %** | `TotalManualReview / TotalDetected x 100` |
| **Linking Rate %** | `TotalLinked / TotalDetected x 100` |
| **Archive Rate %** | `TotalArchived / TotalDetected x 100` |
| **Pending Rate %** | `TotalPending / TotalDetected x 100` |
| **OCR Review Rate %** | `TotalOCRReview / TotalDetected x 100` |
| **Manual Link Rate %** | `TotalManualLink / TotalDetected x 100` |

### Archive Sub-Rates

These use Total Archived as the denominator:

| KPI | Formula |
|-----|---------|
| **Archive by Reviewer %** | `TotalArchivedOCR / TotalArchived x 100` |
| **Archive by Ops %** | `TotalArchivedOPS / TotalArchived x 100` |
| **Archive by Auto %** | `TotalArchivedAutoArchive / TotalArchived x 100` |

### Manual Review Reason Breakdown

For each of the 7 reasons, two percentages are computed:

| Metric | Formula |
|--------|---------|
| **% of Manual Review** | `ReasonCount / TotalManualReview x 100` |
| **% of Total Detected** | `ReasonCount / TotalDetected x 100` |

The 7 reasons: Primary Low Confidence, Secondary Low Confidence, Secondary Not Working, Different Reading, Missing Identifiers, No IN for OUT, No IN from Main.

### Potential Manual Link Rate (Archive Tab)

Applies only to IN-direction cameras:

```
PMLR = (TotalManualLink / TotalArchivedOPS) x 2 x 100
```

Estimates the proportion of archived OPS transactions that may have had a linkable IN transaction missed.

### Division by Zero

All division operations use a safe-divide function that returns `0.0` when the denominator is zero.

---

## KPI Thresholds & Color Coding

### Higher-is-Better KPIs

| KPI | Green (Good) | Yellow (Warning) | Red (Critical) |
|-----|-------------|-----------------|----------------|
| Accuracy % | >= 95% | 85% - 94.9% | < 85% |
| Linking Rate % | >= 95% | 85% - 94.9% | < 85% |

### Lower-is-Better KPIs

| KPI | Green (Good) | Yellow (Warning) | Red (Critical) |
|-----|-------------|-----------------|----------------|
| Manual Review Rate % | <= 20% | 20.1% - 35% | > 35% |
| Archive Rate % | <= 10% | 10.1% - 20% | > 20% |

### Analysis Tab Thresholds

The analysis tabs use additional thresholds for flagging cameras:

| Tab | Flag Threshold | Meaning |
|-----|---------------|---------|
| Accuracy Analysis | < 85% | Camera accuracy below warning level |
| Manual Review Analysis | > 35% | Camera MR rate above critical level |
| Archive Analysis | > 1% | Camera archive rate above operational target |
| Potential Manual Link Rate | > 50% | High proportion of potentially missed links |

### Color Application

- **Dashboard trend charts**: Line segments colored green when meeting the "good" threshold, red when not.
- **KPI cards**: Color indicator bar below the value (green/yellow/red).
- **Camera table cells**: Background fill matching KPI status.
- **Excel export**: Cell backgrounds use matching green/yellow/red fills.

---

## Understanding Outlier Detection

The Outliers tab runs four independent detection methods and combines results:

### 1. Z-Score Analysis

Computes the Z-score for each camera's KPI value relative to the fleet mean. Cameras more than **2.0 standard deviations** from the mean are flagged.

- Requires at least 3 cameras for meaningful results.
- Reports whether the value is above or below the fleet mean.

### 2. IQR (Interquartile Range) Analysis

Uses the standard IQR fence method:
- Lower fence: `Q1 - 1.5 x IQR`
- Upper fence: `Q3 + 1.5 x IQR`

Cameras outside either fence are flagged.

### 3. Threshold Breach

Flags any camera in the **critical (red)** zone for any KPI with defined targets. This uses the same thresholds as the color coding system.

### 4. Dominant Review Reason

Flags cameras where any single manual review reason accounts for more than **50%** of that camera's total manual reviews. This helps identify cameras with systematic issues.

### Analyzed KPIs

Outlier detection runs on: Accuracy %, Manual Review Rate %, Linking Rate %, and Archive Rate %.

---

## Exporting Reports

### Excel Report (Export Full Report)

Creates a multi-sheet `.xlsx` workbook:

| Sheet | Content |
|-------|---------|
| **Fleet Summary** | Fleet-wide KPI values with color-coded status cells |
| **Per-Camera KPIs** | One row per camera, KPI cells colored by threshold |
| **Manual Reasons Detail** | Breakdown of 7 review reasons with counts and percentages |
| **Outlier Report** | Flagged cameras with flag type, Z-score, and reason descriptions |

Cells are color-coded with the same green/yellow/red scheme as the application UI.

### Dashboard PNG (Export Dashboard PNG)

Saves the 4 dashboard trend charts as a single 2x2 PNG image at 150 DPI.

### How to Export

1. Apply any desired filters (date range, lot, direction).
2. Click **Export Full Report** or **Export Dashboard PNG** in the bottom bar.
3. Choose a save location in the file dialog.

Exports respect the currently applied filters — only filtered data is included.

---

## Database & Data Persistence

### Storage

All data is stored in `parking_analytics.db` (SQLite) in the application directory. The database is created automatically on first launch.

### Tables

| Table | Purpose |
|-------|---------|
| `transactions` | All imported camera statistics (one row per date + camera) |
| `uploads` | Import history tracking (file name, timestamp, record counts) |
| `kpi_cache` | Computed KPI results cache for performance |

### Key Properties

- **WAL mode**: Enables concurrent reads during writes for better performance.
- **Foreign keys**: Cascade deletes — removing an upload automatically removes its transactions.
- **Deduplication**: UNIQUE constraint on (date, camera_name) prevents duplicate imports.
- **Indexes**: Composite and single-column indexes on date, camera_name, lot_name, camera_direction for fast filtered queries.

### Data Management

- **Import**: Use the Import Data tab to add new Excel files.
- **Delete**: Click the delete button next to any upload in the history to remove it and all associated data.
- **Cache**: KPI computations are cached automatically. The cache is invalidated whenever data is imported or deleted.
- **Backup**: Copy `parking_analytics.db` to back up all data.

---

## Project Structure

```
Performance_Review/
├── main.py                  # Application entry point and main window
├── database.py              # SQLite schema, queries, and cache functions
├── ingestion.py             # Excel parser, validator, and database loader
├── analytics.py             # All KPI computations and caching wrapper
├── outliers.py              # Statistical outlier detection
├── exporter.py              # Excel and PNG export
├── requirements.txt         # Python dependencies
├── run.bat                  # Windows launcher
├── parking_analytics.db     # SQLite database (created on first run)
├── parking_analytics.log    # Application log file
├── ui/
│   ├── __init__.py          # Shared colors, fonts, and chart constants
│   ├── dashboard_tab.py     # KPI cards + trend charts
│   ├── import_tab.py        # File upload and history
│   ├── accuracy_tab.py      # Accuracy distribution and underperformers
│   ├── manual_review_tab.py # MR analysis with stacked bar and donut
│   ├── archive_tab.py       # Archive analysis and potential manual link rate
│   ├── cameras_tab.py       # Per-camera KPI table
│   ├── trends_tab.py        # Time-series trend viewer
│   └── outliers_tab.py      # Outlier detection report
└── assets/                  # Static assets directory
```

---

## Troubleshooting

### Application won't start

- Verify Python 3.11+ is installed: `python --version`
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check `parking_analytics.log` for error details.

### Import fails or shows missing columns

- Ensure the Excel file is `.xlsx` format (not `.xls` or `.csv`).
- Verify all 25 column headers are present with exact spelling (see How to Import Data).
- Check that Camera Direction values are exactly `IN` or `OUT` (rows with other values are dropped with a warning).

### Charts appear empty or show "No data"

- Confirm data has been imported via the Import Data tab.
- Check that the global filters (date range, lot, direction) are not excluding all data.
- Click **Reset** in the filter bar to clear all filters.

### Duplicate data after re-importing

- The tool deduplicates by (Date, Camera Name). Rows with the same date and camera name as existing data are automatically skipped.
- If you need to replace data, delete the previous upload first from the Import Data tab, then re-import.

### Slow performance with large datasets

- The caching layer stores computed KPIs after the first load. Subsequent tab switches should be instant.
- Use date range filters to limit the data window.
- The application uses background threads for data loading — the UI remains responsive during computation.

### Export produces empty file

- Verify the current filters have matching data (check Dashboard for non-zero KPI values).
- The export includes only data matching the active filters.

### Database corruption

- Delete `parking_analytics.db` and restart the application. The database will be recreated empty.
- Re-import your Excel files to restore data.

### Log file location

All application events and errors are written to `parking_analytics.log` in the project directory. Check this file for detailed error messages and stack traces.
