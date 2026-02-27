"""
analytics.py — All KPI computations using the exact formulas specified.

Pure computation module. Takes pandas DataFrames and returns computed KPIs
at various aggregation levels (fleet, per-camera, per-lot, per-direction, daily).
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KPI Threshold Constants — easy to update
# ---------------------------------------------------------------------------

# "higher is better" KPIs: >= good threshold = green
ACCURACY_THRESHOLDS = {"good": 95, "warning": 85}
LINKING_THRESHOLDS = {"good": 95, "warning": 85}

# "lower is better" KPIs: <= good threshold = green
MANUAL_REVIEW_THRESHOLDS = {"good": 20, "warning": 35}
ARCHIVE_THRESHOLDS = {"good": 10, "warning": 20}

KPI_TARGETS = {
    "accuracy_pct": {"thresholds": ACCURACY_THRESHOLDS, "higher_is_better": True},
    "manual_review_rate_pct": {"thresholds": MANUAL_REVIEW_THRESHOLDS, "higher_is_better": False},
    "linking_rate_pct": {"thresholds": LINKING_THRESHOLDS, "higher_is_better": True},
    "archive_rate_pct": {"thresholds": ARCHIVE_THRESHOLDS, "higher_is_better": False},
}

# The 7 manual review reason columns (database snake_case names)
MANUAL_REVIEW_REASONS = [
    "total_primary_low_confidence",
    "total_secondary_low_confidence",
    "total_secondary_not_working",
    "total_different_reading",
    "total_missing_identifiers",
    "total_no_in_for_out",
    "total_no_in_from_main",
]

# Human-readable display names for manual review reasons
REASON_DISPLAY_NAMES = {
    "total_primary_low_confidence": "Primary Low Confidence",
    "total_secondary_low_confidence": "Secondary Low Confidence",
    "total_secondary_not_working": "Secondary Not Working",
    "total_different_reading": "Different Reading",
    "total_missing_identifiers": "Missing Identifiers",
    "total_no_in_for_out": "No IN for OUT",
    "total_no_in_from_main": "No IN from Main",
}

# All numeric columns used in aggregation
NUMERIC_COLUMNS = [
    "total_transactions", "total_accurated", "total_inaccurated",
    "total_archived", "total_archived_accurated", "total_archived_inaccurated",
    "total_manual_review", "total_primary_low_confidence",
    "total_secondary_low_confidence", "total_secondary_not_working",
    "total_different_reading", "total_missing_identifiers",
    "total_no_in_for_out", "total_no_in_from_main",
    "total_archived_ocr", "total_archived_ops", "total_archived_auto_archive",
    "total_pending", "total_manual_link", "total_ocr_review", "total_linked",
]


# ---------------------------------------------------------------------------
# Core Utility
# ---------------------------------------------------------------------------

def safe_divide(numerator: float, denominator: float, multiply: float = 100.0) -> float:
    """Safely divide and multiply. Returns 0.0 when denominator is 0."""
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * multiply


def get_kpi_status(kpi_name: str, value: float) -> str:
    """
    Return 'good', 'warning', or 'critical' based on KPI thresholds.

    Args:
        kpi_name: Key into KPI_TARGETS (e.g., 'accuracy_pct')
        value: The computed KPI percentage value
    """
    if kpi_name not in KPI_TARGETS:
        return "unknown"

    target = KPI_TARGETS[kpi_name]
    thresholds = target["thresholds"]
    higher_is_better = target["higher_is_better"]

    if higher_is_better:
        if value >= thresholds["good"]:
            return "good"
        elif value >= thresholds["warning"]:
            return "warning"
        else:
            return "critical"
    else:
        if value <= thresholds["good"]:
            return "good"
        elif value <= thresholds["warning"]:
            return "warning"
        else:
            return "critical"


def get_kpi_color(kpi_name: str, value: float) -> str:
    """Return 'green', 'yellow', or 'red' based on KPI thresholds."""
    status = get_kpi_status(kpi_name, value)
    return {"good": "green", "warning": "yellow", "critical": "red"}.get(status, "gray")


# ---------------------------------------------------------------------------
# KPI Computation from Aggregated Sums
# ---------------------------------------------------------------------------

def compute_kpis(row: pd.Series) -> dict:
    """
    Compute all KPIs from a row (or Series) of summed values.
    Implements the exact formulas from the specification.

    Args:
        row: A pandas Series with summed numeric columns.

    Returns:
        Dict with all computed KPI values.
    """
    total_detected = row.get("total_transactions", 0) + row.get("total_archived", 0)
    total_archived = row.get("total_archived", 0)
    total_manual_review = row.get("total_manual_review", 0)

    kpis = {
        "total_detected": total_detected,
        "total_transactions": row.get("total_transactions", 0),
        "total_archived": total_archived,

        # Core KPIs
        "accuracy_pct": safe_divide(
            row.get("total_accurated", 0) + row.get("total_archived_accurated", 0),
            total_detected
        ),
        "manual_review_rate_pct": safe_divide(
            total_manual_review, total_detected
        ),
        "linking_rate_pct": safe_divide(
            row.get("total_linked", 0), total_detected
        ),
        "pending_rate_pct": safe_divide(
            row.get("total_pending", 0), total_detected
        ),
        "ocr_review_rate_pct": safe_divide(
            row.get("total_ocr_review", 0), total_detected
        ),
        "manual_link_rate_pct": safe_divide(
            row.get("total_manual_link", 0), total_detected
        ),
        "archive_rate_pct": safe_divide(
            total_archived, total_detected
        ),

        # Archive sub-rates
        "archive_by_reviewer_rate_pct": safe_divide(
            row.get("total_archived_ocr", 0), total_archived
        ),
        "archive_by_ops_rate_pct": safe_divide(
            row.get("total_archived_ops", 0), total_archived
        ),
        "archive_by_auto_rate_pct": safe_divide(
            row.get("total_archived_auto_archive", 0), total_archived
        ),
    }

    # Manual review reason breakdowns (two percentages each)
    for reason in MANUAL_REVIEW_REASONS:
        reason_count = row.get(reason, 0)
        reason_short = reason.replace("total_", "")

        # % of Manual Review
        kpis[f"{reason_short}_pct_of_review"] = safe_divide(
            reason_count, total_manual_review
        )
        # % of Total Detected
        kpis[f"{reason_short}_pct_of_detected"] = safe_divide(
            reason_count, total_detected
        )

    # Add color status for target KPIs
    for kpi_name in KPI_TARGETS:
        kpis[f"{kpi_name}_color"] = get_kpi_color(kpi_name, kpis[kpi_name])
        kpis[f"{kpi_name}_status"] = get_kpi_status(kpi_name, kpis[kpi_name])

    return kpis


# ---------------------------------------------------------------------------
# Fleet-Wide Aggregation
# ---------------------------------------------------------------------------

def compute_fleet_kpis(df: pd.DataFrame) -> dict:
    """
    Aggregate across ALL rows in the DataFrame (fleet-wide).
    Returns a dict with all KPI values and color statuses.
    """
    if df.empty:
        return compute_kpis(pd.Series({col: 0 for col in NUMERIC_COLUMNS}))

    totals = df[NUMERIC_COLUMNS].sum()
    return compute_kpis(totals)


# ---------------------------------------------------------------------------
# Per-Camera Aggregation
# ---------------------------------------------------------------------------

def compute_per_camera_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by camera_name, compute all KPIs per camera.
    Returns a DataFrame with one row per camera.
    """
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(["camera_name", "lot_name", "camera_direction"], as_index=False)[
        NUMERIC_COLUMNS
    ].sum()

    kpi_rows = []
    for _, row in grouped.iterrows():
        kpis = compute_kpis(row)
        kpis["camera_name"] = row["camera_name"]
        kpis["lot_name"] = row["lot_name"]
        kpis["camera_direction"] = row["camera_direction"]
        kpi_rows.append(kpis)

    result = pd.DataFrame(kpi_rows)
    # Reorder columns: identifiers first
    id_cols = ["camera_name", "lot_name", "camera_direction"]
    other_cols = [c for c in result.columns if c not in id_cols]
    return result[id_cols + other_cols]


# ---------------------------------------------------------------------------
# Per-Lot Aggregation
# ---------------------------------------------------------------------------

def compute_per_lot_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Group by lot_name, compute all KPIs per lot."""
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("lot_name", as_index=False)[NUMERIC_COLUMNS].sum()

    kpi_rows = []
    for _, row in grouped.iterrows():
        kpis = compute_kpis(row)
        kpis["lot_name"] = row["lot_name"]
        kpi_rows.append(kpis)

    result = pd.DataFrame(kpi_rows)
    id_cols = ["lot_name"]
    other_cols = [c for c in result.columns if c not in id_cols]
    return result[id_cols + other_cols]


# ---------------------------------------------------------------------------
# By Direction Aggregation
# ---------------------------------------------------------------------------

def compute_by_direction_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Group by camera_direction, compute all KPIs."""
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("camera_direction", as_index=False)[NUMERIC_COLUMNS].sum()

    kpi_rows = []
    for _, row in grouped.iterrows():
        kpis = compute_kpis(row)
        kpis["camera_direction"] = row["camera_direction"]
        kpi_rows.append(kpis)

    result = pd.DataFrame(kpi_rows)
    id_cols = ["camera_direction"]
    other_cols = [c for c in result.columns if c not in id_cols]
    return result[id_cols + other_cols]


# ---------------------------------------------------------------------------
# Daily Trend Aggregation
# ---------------------------------------------------------------------------

def compute_daily_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Group by date, compute KPIs for each day (fleet-wide daily trend)."""
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("date", as_index=False)[NUMERIC_COLUMNS].sum()

    kpi_rows = []
    for _, row in grouped.iterrows():
        kpis = compute_kpis(row)
        kpis["date"] = row["date"]
        kpi_rows.append(kpis)

    result = pd.DataFrame(kpi_rows)
    id_cols = ["date"]
    other_cols = [c for c in result.columns if c not in id_cols]
    return result[id_cols + other_cols].sort_values("date")


def compute_camera_daily_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Group by (date, camera_name), compute KPIs for per-camera daily trends."""
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(["date", "camera_name"], as_index=False)[NUMERIC_COLUMNS].sum()

    kpi_rows = []
    for _, row in grouped.iterrows():
        kpis = compute_kpis(row)
        kpis["date"] = row["date"]
        kpis["camera_name"] = row["camera_name"]
        kpi_rows.append(kpis)

    result = pd.DataFrame(kpi_rows)
    id_cols = ["date", "camera_name"]
    other_cols = [c for c in result.columns if c not in id_cols]
    return result[id_cols + other_cols].sort_values(["date", "camera_name"])


# ---------------------------------------------------------------------------
# Manual Review Reason Breakdown
# ---------------------------------------------------------------------------

def compute_manual_review_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate the 7 manual review reasons fleet-wide.
    Returns a DataFrame with columns: reason, display_name, count,
    pct_of_review, pct_of_detected.
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "reason", "display_name", "count", "pct_of_review", "pct_of_detected"
        ])

    total_manual_review = df["total_manual_review"].sum()
    total_detected = df["total_transactions"].sum() + df["total_archived"].sum()

    rows = []
    for reason in MANUAL_REVIEW_REASONS:
        count = df[reason].sum()
        rows.append({
            "reason": reason,
            "display_name": REASON_DISPLAY_NAMES[reason],
            "count": int(count),
            "pct_of_review": safe_divide(count, total_manual_review),
            "pct_of_detected": safe_divide(count, total_detected),
        })

    return pd.DataFrame(rows)
