"""
archive_tab.py — Archive Rate Analysis dashboard.

Section A: Archive rate distribution histogram.
Section B: Table of cameras with high archive rates (>1%).
Section C: Grouped bar chart of archive reasons per camera.
Section D: Potential Manual Link Rate for IN cameras only.
"""

import logging

import numpy as np
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd

import database
import analytics
from analytics import safe_divide
from ui import (
    FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_KPI_VALUE, FONT_KPI_LABEL,
    FONT_TABLE_HEADER, FONT_TABLE_BODY,
    COLORS, CHART_BG, CHART_FACE, CHART_TEXT, CHART_GRID,
)

logger = logging.getLogger(__name__)

ARCHIVE_CRITICAL_THRESHOLD = 1   # Cameras above 1% archive rate are flagged
PMLR_CRITICAL_THRESHOLD = 50     # Potential Manual Link Rate > 50% flagged

# Table columns for Section B
ARCHIVE_TABLE_COLUMNS = [
    ("camera_name", "Camera Name", 140),
    ("lot_name", "Lot Name", 110),
    ("camera_direction", "Direction", 75),
    ("archive_rate_pct", "Archive %", 80),
    ("total_archived", "Archived", 80),
    ("total_detected", "Detected", 85),
    ("archive_by_reviewer_rate_pct", "By Reviewer %", 95),
    ("archive_by_ops_rate_pct", "By Ops %", 80),
]

# Colors for archive reason groups
ARCHIVE_REASON_COLORS = {
    "archive_by_reviewer_rate_pct": "#3498DB",  # Blue
    "archive_by_ops_rate_pct": "#E67E22",       # Orange
    "archive_by_auto_rate_pct": "#2ECC71",      # Green
}

ARCHIVE_REASON_LABELS = {
    "archive_by_reviewer_rate_pct": "OCR Reviewer %",
    "archive_by_ops_rate_pct": "Operations %",
    "archive_by_auto_rate_pct": "Auto Archive %",
}

ROW_RED_BG = "#3d1a1a"


class ArchiveTab(ctk.CTkFrame):
    """Archive Rate Analysis tab."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._camera_df = pd.DataFrame()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build all 4 sections."""
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Section A: Histogram ---
        hist_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        hist_frame.pack(fill="x", padx=5, pady=(0, 10))

        ctk.CTkLabel(
            hist_frame, text="Archive Rate Distribution",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 0))

        fig_hist = Figure(figsize=(10, 3.5), dpi=100)
        fig_hist.patch.set_facecolor(CHART_BG)
        self._hist_fig = fig_hist
        self._hist_canvas = FigureCanvasTkAgg(fig_hist, master=hist_frame)
        self._hist_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Section B: High archive rate cameras table ---
        table_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        table_frame.pack(fill="x", padx=5, pady=(0, 10))

        self._table_header_label = ctk.CTkLabel(
            table_frame,
            text=f"Cameras Above {ARCHIVE_CRITICAL_THRESHOLD}% Archive Rate",
            font=FONT_SUBTITLE, anchor="w"
        )
        self._table_header_label.pack(fill="x", padx=15, pady=(10, 5))

        header_row = ctk.CTkFrame(table_frame, fg_color=COLORS["accent"], corner_radius=5)
        header_row.pack(fill="x", padx=10)

        for _, display, width in ARCHIVE_TABLE_COLUMNS:
            ctk.CTkLabel(
                header_row, text=display, font=FONT_TABLE_HEADER,
                width=width, anchor="center"
            ).pack(side="left", padx=2, pady=6)

        self._table_scroll = ctk.CTkScrollableFrame(
            table_frame, fg_color="transparent", height=200
        )
        self._table_scroll.pack(fill="x", padx=10, pady=(0, 10))

        # --- Section C: Archive reasons grouped bar chart ---
        reasons_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        reasons_frame.pack(fill="x", padx=5, pady=(0, 10))

        ctk.CTkLabel(
            reasons_frame, text="Archive Reasons Distribution per Camera",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 0))

        fig_reasons = Figure(figsize=(10, 4), dpi=100)
        fig_reasons.patch.set_facecolor(CHART_BG)
        self._reasons_fig = fig_reasons
        self._reasons_canvas = FigureCanvasTkAgg(fig_reasons, master=reasons_frame)
        self._reasons_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Section D: Potential Manual Link Rate (IN cameras) ---
        pmlr_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        pmlr_frame.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        pmlr_header = ctk.CTkFrame(pmlr_frame, fg_color="transparent")
        pmlr_header.pack(fill="x", padx=15, pady=(10, 0))

        ctk.CTkLabel(
            pmlr_header, text="Potential Manual Link Rate (IN Cameras Only)",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(side="left")

        # KPI summary card for fleet avg
        self._pmlr_card = ctk.CTkFrame(pmlr_header, fg_color=COLORS["accent"],
                                        corner_radius=8, width=150)
        self._pmlr_card.pack(side="right", padx=(10, 0))

        ctk.CTkLabel(
            self._pmlr_card, text="Fleet Avg (IN)", font=FONT_KPI_LABEL,
            text_color=COLORS["text"]
        ).pack(padx=10, pady=(5, 0))

        self._pmlr_value_label = ctk.CTkLabel(
            self._pmlr_card, text="--", font=("Segoe UI", 18, "bold"),
            text_color=COLORS["text"]
        )
        self._pmlr_value_label.pack(padx=10, pady=(0, 5))

        # Footnote
        ctk.CTkLabel(
            pmlr_frame,
            text="Estimates the proportion of archived OPS transactions that "
                 "may have had a linkable IN transaction missed. "
                 "Formula: (TotalManualLink / TotalArchivedOPS) \u00d7 2 \u00d7 100",
            font=("Segoe UI", 9), text_color="gray", anchor="w", wraplength=800
        ).pack(fill="x", padx=15, pady=(5, 0))

        fig_pmlr = Figure(figsize=(10, 4), dpi=100)
        fig_pmlr.patch.set_facecolor(CHART_BG)
        self._pmlr_fig = fig_pmlr
        self._pmlr_canvas = FigureCanvasTkAgg(fig_pmlr, master=pmlr_frame)
        self._pmlr_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh(self) -> None:
        """Refresh all sections."""
        conn = database.get_connection()
        try:
            df = database.get_transactions(
                conn,
                date_start=self.app.filters.get("date_start"),
                date_end=self.app.filters.get("date_end"),
                lot_name=self.app.filters.get("lot_name"),
                camera_direction=self.app.filters.get("camera_direction"),
            )
        finally:
            conn.close()

        self._camera_df = analytics.compute_per_camera_kpis(df)

        self._draw_histogram()
        self._rebuild_table()
        self._draw_reasons_chart()
        self._draw_pmlr_chart()

    def _draw_histogram(self) -> None:
        """Draw archive rate distribution histogram."""
        fig = self._hist_fig
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        if self._camera_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._hist_canvas.draw()
            return

        values = self._camera_df["archive_rate_pct"].values

        # Use finer bins for archive rate since most values are small
        max_val = max(values.max(), 10)
        if max_val <= 10:
            bins = np.arange(0, max_val + 2, 1)
        else:
            bins = np.arange(0, min(max_val + 10, 110), 10)

        counts, edges = np.histogram(values, bins=bins)
        bar_positions = edges[:-1] + (edges[1] - edges[0]) / 2
        bar_width = (edges[1] - edges[0]) * 0.8

        bar_colors = [COLORS["red"] if mid > ARCHIVE_CRITICAL_THRESHOLD
                      else COLORS["green"] for mid in bar_positions]

        bars = ax.bar(bar_positions, counts, width=bar_width, color=bar_colors,
                      edgecolor=CHART_BG, linewidth=0.5)

        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        str(int(count)), ha="center", va="bottom",
                        color=CHART_TEXT, fontsize=8, fontweight="bold")

        ax.set_xlabel("Archive Rate %", fontsize=9, color=CHART_TEXT)
        ax.set_ylabel("Number of Cameras", fontsize=9, color=CHART_TEXT)
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="y", color=CHART_GRID, alpha=0.3)

        ax.axvline(x=ARCHIVE_CRITICAL_THRESHOLD, color=COLORS["yellow"],
                    linestyle="--", alpha=0.7, linewidth=1,
                    label=f"Threshold: {ARCHIVE_CRITICAL_THRESHOLD}%")
        ax.legend(fontsize=7, labelcolor=CHART_TEXT, frameon=False)

        fig.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.18)
        self._hist_canvas.draw()

    def _rebuild_table(self) -> None:
        """Rebuild the high archive rate cameras table."""
        for widget in self._table_scroll.winfo_children():
            widget.destroy()

        if self._camera_df.empty:
            ctk.CTkLabel(
                self._table_scroll, text="No camera data available.",
                font=FONT_BODY, text_color="gray"
            ).pack(pady=20)
            return

        flagged = self._camera_df[
            self._camera_df["archive_rate_pct"] > ARCHIVE_CRITICAL_THRESHOLD
        ].sort_values("archive_rate_pct", ascending=False).reset_index(drop=True)

        count = len(flagged)
        self._table_header_label.configure(
            text=f"Cameras Above {ARCHIVE_CRITICAL_THRESHOLD}% Archive Rate ({count} camera{'s' if count != 1 else ''})"
        )

        if flagged.empty:
            ctk.CTkLabel(
                self._table_scroll,
                text="All cameras are within the archive rate threshold.",
                font=FONT_BODY, text_color=COLORS["green"]
            ).pack(pady=20)
            return

        for _, row in flagged.iterrows():
            row_frame = ctk.CTkFrame(
                self._table_scroll, fg_color=ROW_RED_BG,
                corner_radius=3, height=32
            )
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)

            for key, _, width in ARCHIVE_TABLE_COLUMNS:
                value = row.get(key, "")
                if key in ("archive_rate_pct", "archive_by_reviewer_rate_pct",
                           "archive_by_ops_rate_pct"):
                    text = f"{value:.1f}%" if pd.notna(value) else "0.0%"
                    text_color = COLORS["red"] if key == "archive_rate_pct" else COLORS["text"]
                elif key in ("total_archived", "total_detected"):
                    text = f"{int(value):,}" if pd.notna(value) else "0"
                    text_color = COLORS["text"]
                else:
                    text = str(value)
                    text_color = COLORS["text"]

                ctk.CTkLabel(
                    row_frame, text=text, font=FONT_TABLE_BODY,
                    width=width, anchor="center", text_color=text_color
                ).pack(side="left", padx=2)

    def _draw_reasons_chart(self) -> None:
        """Draw grouped bar chart showing archive reasons per camera."""
        fig = self._reasons_fig
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        camera_df = self._camera_df
        if camera_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._reasons_canvas.draw()
            return

        cameras = camera_df["camera_name"].tolist()
        x = np.arange(len(cameras))
        n_groups = len(ARCHIVE_REASON_COLORS)
        bar_width = 0.25

        for i, (col, color) in enumerate(ARCHIVE_REASON_COLORS.items()):
            if col not in camera_df.columns:
                continue
            values = camera_df[col].fillna(0).values
            label = ARCHIVE_REASON_LABELS[col]
            offset = (i - n_groups / 2 + 0.5) * bar_width
            ax.bar(x + offset, values, bar_width, color=color, label=label,
                   edgecolor=CHART_BG, linewidth=0.3)

        ax.set_xlabel("Camera", fontsize=8, color=CHART_TEXT)
        ax.set_ylabel("% of Archived", fontsize=8, color=CHART_TEXT)
        ax.set_xticks(x)
        ax.set_xticklabels(cameras, fontsize=6, color=CHART_TEXT,
                           rotation=45, ha="right")
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="y", color=CHART_GRID, alpha=0.3)
        ax.legend(fontsize=7, labelcolor=CHART_TEXT, frameon=False)

        fig.subplots_adjust(left=0.10, right=0.95, top=0.95, bottom=0.22)
        self._reasons_canvas.draw()

    def _draw_pmlr_chart(self) -> None:
        """Draw Potential Manual Link Rate chart for IN cameras only."""
        fig = self._pmlr_fig
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        camera_df = self._camera_df
        if camera_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._pmlr_value_label.configure(text="--")
            self._pmlr_canvas.draw()
            return

        # Filter to IN cameras only
        in_cameras = camera_df[camera_df["camera_direction"] == "IN"].copy()

        if in_cameras.empty:
            ax.text(0.5, 0.5, "No IN cameras", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._pmlr_value_label.configure(text="N/A")
            self._pmlr_canvas.draw()
            return

        # Compute Potential Manual Link Rate
        # Formula: (TotalManualLink / TotalArchivedOPS) × 2 × 100
        in_cameras["pmlr"] = in_cameras.apply(
            lambda r: safe_divide(r.get("total_manual_link", 0),
                                  r.get("total_archived_ops", 0),
                                  multiply=200.0),
            axis=1
        )

        # Fleet average for IN cameras
        total_ml = in_cameras["total_manual_link"].sum()
        total_aops = in_cameras["total_archived_ops"].sum()
        fleet_avg = safe_divide(total_ml, total_aops, multiply=200.0)

        self._pmlr_value_label.configure(
            text=f"{fleet_avg:.1f}%",
            text_color=COLORS["red"] if fleet_avg > PMLR_CRITICAL_THRESHOLD else COLORS["green"]
        )

        # Sort descending and draw horizontal bar chart
        in_cameras = in_cameras.sort_values("pmlr", ascending=True).reset_index(drop=True)
        cameras = in_cameras["camera_name"].tolist()
        values = in_cameras["pmlr"].tolist()
        colors = [COLORS["red"] if v > PMLR_CRITICAL_THRESHOLD
                  else COLORS["green"] for v in values]

        y_pos = range(len(cameras))
        ax.barh(y_pos, values, color=colors, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(cameras, fontsize=7, color=CHART_TEXT)
        ax.set_xlabel("Potential Manual Link Rate %", fontsize=8, color=CHART_TEXT)
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="x", color=CHART_GRID, alpha=0.3)

        # Threshold line at 50%
        ax.axvline(x=PMLR_CRITICAL_THRESHOLD, color=COLORS["yellow"],
                    linestyle="--", alpha=0.7, linewidth=1,
                    label=f"Threshold: {PMLR_CRITICAL_THRESHOLD}%")
        ax.legend(fontsize=7, labelcolor=CHART_TEXT, frameon=False)

        fig.subplots_adjust(left=0.25, right=0.95, top=0.95, bottom=0.12)
        self._pmlr_canvas.draw()
