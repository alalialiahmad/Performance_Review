"""
outliers.py — Statistical outlier detection for camera KPIs.

Uses Z-score and IQR methods to flag cameras deviating from fleet averages,
detects threshold breaches, and identifies dominant manual review reasons.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from analytics import (
    compute_per_camera_kpis,
    KPI_TARGETS,
    MANUAL_REVIEW_REASONS,
    REASON_DISPLAY_NAMES,
    safe_divide,
    get_kpi_status,
    NUMERIC_COLUMNS,
)

logger = logging.getLogger(__name__)

# Configuration constants
ZSCORE_THRESHOLD = 2.0       # Flag cameras > 2 std devs from mean
IQR_MULTIPLIER = 1.5         # Standard IQR fence
DOMINANT_REASON_PCT = 50.0   # Flag if single reason > 50% of manual reviews
MIN_CAMERAS_FOR_ZSCORE = 3   # Need at least 3 cameras for meaningful Z-scores

# KPI columns to analyze for Z-score and IQR outliers
OUTLIER_KPI_COLUMNS = [
    "accuracy_pct", "manual_review_rate_pct",
    "linking_rate_pct", "archive_rate_pct",
]

KPI_DISPLAY_NAMES = {
    "accuracy_pct": "Accuracy %",
    "manual_review_rate_pct": "Manual Review Rate %",
    "linking_rate_pct": "Linking Rate %",
    "archive_rate_pct": "Archive Rate %",
    "pending_rate_pct": "Pending Rate %",
    "ocr_review_rate_pct": "OCR Review Rate %",
    "manual_link_rate_pct": "Manual Link Rate %",
}


def detect_zscore_outliers(camera_df: pd.DataFrame,
                           threshold: float = ZSCORE_THRESHOLD) -> pd.DataFrame:
    """
    For each KPI, compute Z-scores across cameras and flag those beyond threshold.

    Args:
        camera_df: Per-camera KPI DataFrame from compute_per_camera_kpis()
        threshold: Z-score threshold (default 2.0)

    Returns:
        DataFrame with columns: camera_name, lot_name, metric, value,
        fleet_mean, z_score, flag_type, reason
    """
    if camera_df.empty or len(camera_df) < MIN_CAMERAS_FOR_ZSCORE:
        return _empty_outlier_df()

    results = []
    for kpi in OUTLIER_KPI_COLUMNS:
        if kpi not in camera_df.columns:
            continue

        values = camera_df[kpi].fillna(0).astype(float)
        mean = values.mean()
        std = values.std()

        if std == 0:
            continue

        z_scores = (values - mean) / std

        for idx, z in z_scores.items():
            if abs(z) > threshold:
                row = camera_df.loc[idx]
                display = KPI_DISPLAY_NAMES.get(kpi, kpi)
                direction = "above" if z > 0 else "below"
                results.append({
                    "camera_name": row["camera_name"],
                    "lot_name": row.get("lot_name", ""),
                    "metric": display,
                    "value": round(row[kpi], 1),
                    "fleet_mean": round(mean, 1),
                    "z_score": round(z, 2),
                    "flag_type": "Z-Score",
                    "reason": (
                        f"{display} of {row[kpi]:.1f}% is {abs(z):.1f} std devs "
                        f"{direction} fleet mean {mean:.1f}%"
                    ),
                })

    return pd.DataFrame(results) if results else _empty_outlier_df()


def detect_iqr_outliers(camera_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each KPI, flag cameras outside the IQR fences.

    Returns:
        DataFrame with same columns as detect_zscore_outliers().
    """
    if camera_df.empty or len(camera_df) < MIN_CAMERAS_FOR_ZSCORE:
        return _empty_outlier_df()

    results = []
    for kpi in OUTLIER_KPI_COLUMNS:
        if kpi not in camera_df.columns:
            continue

        values = camera_df[kpi].fillna(0).astype(float)
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue

        lower = q1 - IQR_MULTIPLIER * iqr
        upper = q3 + IQR_MULTIPLIER * iqr

        for idx, val in values.items():
            if val < lower or val > upper:
                row = camera_df.loc[idx]
                display = KPI_DISPLAY_NAMES.get(kpi, kpi)
                side = "below" if val < lower else "above"
                fence = lower if val < lower else upper
                results.append({
                    "camera_name": row["camera_name"],
                    "lot_name": row.get("lot_name", ""),
                    "metric": display,
                    "value": round(val, 1),
                    "fleet_mean": round(values.mean(), 1),
                    "z_score": 0.0,
                    "flag_type": "IQR",
                    "reason": (
                        f"{display} of {val:.1f}% is {side} IQR fence {fence:.1f}%"
                    ),
                })

    return pd.DataFrame(results) if results else _empty_outlier_df()


def detect_threshold_breaches(camera_df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag cameras in the 'critical' (red) zone for any KPI with defined targets.

    Returns:
        DataFrame with same columns as other detectors.
    """
    if camera_df.empty:
        return _empty_outlier_df()

    results = []
    for kpi_name, target_info in KPI_TARGETS.items():
        if kpi_name not in camera_df.columns:
            continue

        for idx, row in camera_df.iterrows():
            value = row[kpi_name]
            status = get_kpi_status(kpi_name, value)

            if status == "critical":
                display = KPI_DISPLAY_NAMES.get(kpi_name, kpi_name)
                thresholds = target_info["thresholds"]
                results.append({
                    "camera_name": row["camera_name"],
                    "lot_name": row.get("lot_name", ""),
                    "metric": display,
                    "value": round(value, 1),
                    "fleet_mean": round(camera_df[kpi_name].mean(), 1),
                    "z_score": 0.0,
                    "flag_type": "Threshold Breach",
                    "reason": (
                        f"{display} of {value:.1f}% breaches critical threshold "
                        f"(warning: {thresholds['warning']}%, good: {thresholds['good']}%)"
                    ),
                })

    return pd.DataFrame(results) if results else _empty_outlier_df()


def detect_dominant_review_reasons(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag cameras where any single manual review reason > 50% of total manual reviews.

    Args:
        raw_df: Raw transaction DataFrame (not per-camera KPI df).

    Returns:
        DataFrame with same columns as other detectors.
    """
    if raw_df.empty:
        return _empty_outlier_df()

    # Group by camera for per-camera analysis
    grouped = raw_df.groupby(["camera_name", "lot_name"], as_index=False)[
        ["total_manual_review"] + MANUAL_REVIEW_REASONS
    ].sum()

    results = []
    for _, row in grouped.iterrows():
        total_mr = row["total_manual_review"]
        if total_mr == 0:
            continue

        for reason in MANUAL_REVIEW_REASONS:
            reason_count = row[reason]
            pct = safe_divide(reason_count, total_mr)

            if pct > DOMINANT_REASON_PCT:
                display_reason = REASON_DISPLAY_NAMES.get(reason, reason)
                results.append({
                    "camera_name": row["camera_name"],
                    "lot_name": row.get("lot_name", ""),
                    "metric": f"Dominant Reason: {display_reason}",
                    "value": round(pct, 1),
                    "fleet_mean": 0.0,
                    "z_score": 0.0,
                    "flag_type": "Dominant Reason",
                    "reason": (
                        f"{display_reason} accounts for {pct:.1f}% of manual reviews "
                        f"({int(reason_count)} of {int(total_mr)})"
                    ),
                })

    return pd.DataFrame(results) if results else _empty_outlier_df()


def generate_outlier_report(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Run all outlier detection methods and combine into a unified report.

    Args:
        raw_df: Raw transaction DataFrame from database.

    Returns:
        Combined DataFrame sorted by flag_type and camera_name.
    """
    if raw_df.empty:
        return _empty_outlier_df()

    # Compute per-camera KPIs first
    camera_df = compute_per_camera_kpis(raw_df)

    if camera_df.empty:
        return _empty_outlier_df()

    # Run all detection methods
    zscore_results = detect_zscore_outliers(camera_df)
    iqr_results = detect_iqr_outliers(camera_df)
    threshold_results = detect_threshold_breaches(camera_df)
    dominant_results = detect_dominant_review_reasons(raw_df)

    # Combine all results
    combined = pd.concat(
        [zscore_results, iqr_results, threshold_results, dominant_results],
        ignore_index=True
    )

    if combined.empty:
        return _empty_outlier_df()

    return combined.sort_values(
        ["flag_type", "camera_name", "metric"],
        ignore_index=True
    )


def _empty_outlier_df() -> pd.DataFrame:
    """Return an empty DataFrame with the standard outlier report columns."""
    return pd.DataFrame(columns=[
        "camera_name", "lot_name", "metric", "value",
        "fleet_mean", "z_score", "flag_type", "reason"
    ])
