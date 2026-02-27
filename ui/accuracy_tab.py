"""
accuracy_tab.py — Camera Accuracy Analysis dashboard.

Section A: Accuracy distribution histogram showing how cameras are distributed
           across accuracy percentage buckets.
Section B: Table of underperforming cameras below the 85% accuracy threshold.
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
from ui import (
    FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_TABLE_HEADER, FONT_TABLE_BODY,
    COLORS, CHART_BG, CHART_FACE, CHART_TEXT, CHART_GRID,
)

logger = logging.getLogger(__name__)

ACCURACY_CRITICAL_THRESHOLD = 85  # Cameras below this are flagged

# Table column definitions for Section B
UNDERPERFORMING_COLUMNS = [
    ("camera_name", "Camera Name", 150),
    ("lot_name", "Lot Name", 120),
    ("camera_direction", "Direction", 80),
    ("accuracy_pct", "Accuracy %", 90),
    ("total_detected", "Total Detected", 100),
    ("total_accurated", "Accurated", 90),
    ("total_archived_accurated", "Archived Accurated", 120),
]

ROW_RED_BG = "#3d1a1a"  # Dark red tint for flagged rows


class AccuracyTab(ctk.CTkFrame):
    """Camera Accuracy Analysis tab with histogram and underperforming table."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._camera_df = pd.DataFrame()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the histogram and underperforming cameras table."""
        # Scrollable container for all sections
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Section A: Histogram ---
        hist_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        hist_frame.pack(fill="x", padx=5, pady=(0, 10))

        ctk.CTkLabel(
            hist_frame, text="Accuracy Distribution",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 0))

        fig = Figure(figsize=(10, 3.5), dpi=100)
        fig.patch.set_facecolor(CHART_BG)
        self._hist_fig = fig
        self._hist_canvas = FigureCanvasTkAgg(fig, master=hist_frame)
        self._hist_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Section B: Underperforming cameras table ---
        table_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        self._table_header_label = ctk.CTkLabel(
            table_frame,
            text=f"Cameras Below {ACCURACY_CRITICAL_THRESHOLD}% Accuracy",
            font=FONT_SUBTITLE, anchor="w"
        )
        self._table_header_label.pack(fill="x", padx=15, pady=(10, 5))

        # Column headers
        header_row = ctk.CTkFrame(table_frame, fg_color=COLORS["accent"], corner_radius=5)
        header_row.pack(fill="x", padx=10, pady=(0, 0))

        for _, display, width in UNDERPERFORMING_COLUMNS:
            ctk.CTkLabel(
                header_row, text=display, font=FONT_TABLE_HEADER,
                width=width, anchor="center"
            ).pack(side="left", padx=2, pady=6)

        # Scrollable table body
        self._table_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self._table_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh(self) -> None:
        """Refresh histogram and table with current filtered data."""
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

    def _draw_histogram(self) -> None:
        """Draw the accuracy distribution histogram."""
        fig = self._hist_fig
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        if self._camera_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._hist_canvas.draw()
            return

        values = self._camera_df["accuracy_pct"].values
        bins = np.arange(0, 110, 10)  # 0, 10, 20, ..., 100
        counts, edges = np.histogram(values, bins=bins)

        # Bar positions and colors
        bar_positions = edges[:-1] + 5  # Center of each bucket
        bar_colors = [COLORS["red"] if mid < ACCURACY_CRITICAL_THRESHOLD
                      else COLORS["green"] for mid in bar_positions]

        bars = ax.bar(bar_positions, counts, width=8, color=bar_colors,
                      edgecolor=CHART_BG, linewidth=0.5)

        # Labels on top of each bar
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        str(int(count)), ha="center", va="bottom",
                        color=CHART_TEXT, fontsize=8, fontweight="bold")

        ax.set_xlabel("Accuracy %", fontsize=9, color=CHART_TEXT)
        ax.set_ylabel("Number of Cameras", fontsize=9, color=CHART_TEXT)
        ax.set_xticks(bar_positions)
        ax.set_xticklabels([f"{int(e)}-{int(e+10)}%" for e in edges[:-1]],
                           fontsize=7, color=CHART_TEXT, rotation=45, ha="right")
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="y", color=CHART_GRID, alpha=0.3)

        # Threshold reference line
        ax.axvline(x=ACCURACY_CRITICAL_THRESHOLD, color=COLORS["yellow"],
                    linestyle="--", alpha=0.7, linewidth=1,
                    label=f"Threshold: {ACCURACY_CRITICAL_THRESHOLD}%")
        ax.legend(fontsize=7, labelcolor=CHART_TEXT, frameon=False)

        fig.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.22)
        self._hist_canvas.draw()

    def _rebuild_table(self) -> None:
        """Rebuild the underperforming cameras table."""
        for widget in self._table_scroll.winfo_children():
            widget.destroy()

        if self._camera_df.empty:
            ctk.CTkLabel(
                self._table_scroll,
                text="No camera data available.",
                font=FONT_BODY, text_color="gray"
            ).pack(pady=20)
            self._table_header_label.configure(
                text=f"Cameras Below {ACCURACY_CRITICAL_THRESHOLD}% Accuracy"
            )
            return

        # Filter cameras below threshold
        flagged = self._camera_df[
            self._camera_df["accuracy_pct"] < ACCURACY_CRITICAL_THRESHOLD
        ].sort_values("accuracy_pct", ascending=True).reset_index(drop=True)

        count = len(flagged)
        self._table_header_label.configure(
            text=f"Cameras Below {ACCURACY_CRITICAL_THRESHOLD}% Accuracy ({count} camera{'s' if count != 1 else ''})"
        )

        if flagged.empty:
            ctk.CTkLabel(
                self._table_scroll,
                text="All cameras meet the accuracy threshold.",
                font=FONT_BODY, text_color=COLORS["green"]
            ).pack(pady=20)
            return

        for idx, (_, row) in enumerate(flagged.iterrows()):
            row_frame = ctk.CTkFrame(
                self._table_scroll, fg_color=ROW_RED_BG,
                corner_radius=3, height=32
            )
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)

            for key, _, width in UNDERPERFORMING_COLUMNS:
                value = row.get(key, "")
                if key == "accuracy_pct":
                    text = f"{value:.1f}%"
                    text_color = COLORS["red"]
                elif key in ("total_detected", "total_accurated", "total_archived_accurated"):
                    text = f"{int(value):,}" if pd.notna(value) else "0"
                    text_color = COLORS["text"]
                else:
                    text = str(value)
                    text_color = COLORS["text"]

                ctk.CTkLabel(
                    row_frame, text=text, font=FONT_TABLE_BODY,
                    width=width, anchor="center", text_color=text_color
                ).pack(side="left", padx=2)
