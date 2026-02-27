"""
manual_review_tab.py — Manual Review Analysis dashboard.

Section A: Manual review rate distribution histogram.
Section B: Table of cameras with high manual review rates (>35%).
Section C: Two charts side by side — stacked bar per camera showing
           7 review reasons, and fleet-wide donut showing reason breakdown.
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
from analytics import MANUAL_REVIEW_REASONS, REASON_DISPLAY_NAMES
from ui import (
    FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_TABLE_HEADER, FONT_TABLE_BODY,
    COLORS, CHART_BG, CHART_FACE, CHART_TEXT, CHART_GRID, REASON_COLORS,
)

logger = logging.getLogger(__name__)

MR_CRITICAL_THRESHOLD = 35  # Cameras above this are flagged

# Short reason keys derived from column names (strips "total_" prefix)
REASON_SHORT_KEYS = [r.replace("total_", "") for r in MANUAL_REVIEW_REASONS]

# Table column definitions for Section B
HIGH_MR_COLUMNS = [
    ("camera_name", "Camera Name", 150),
    ("lot_name", "Lot Name", 120),
    ("camera_direction", "Direction", 80),
    ("manual_review_rate_pct", "MR Rate %", 100),
    ("total_manual_review", "Manual Reviews", 110),
    ("total_detected", "Total Detected", 100),
]

ROW_RED_BG = "#3d1a1a"


class ManualReviewTab(ctk.CTkFrame):
    """Manual Review Analysis tab with histogram, table, and reason charts."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._camera_df = pd.DataFrame()
        self._review_breakdown = pd.DataFrame()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build all sections."""
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Section A: Histogram ---
        hist_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        hist_frame.pack(fill="x", padx=5, pady=(0, 10))

        ctk.CTkLabel(
            hist_frame, text="Manual Review Rate Distribution",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 0))

        fig_hist = Figure(figsize=(10, 3.5), dpi=100)
        fig_hist.patch.set_facecolor(CHART_BG)
        self._hist_fig = fig_hist
        self._hist_canvas = FigureCanvasTkAgg(fig_hist, master=hist_frame)
        self._hist_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Section B: High MR rate cameras table ---
        table_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        table_frame.pack(fill="x", padx=5, pady=(0, 10))

        self._table_header_label = ctk.CTkLabel(
            table_frame,
            text=f"Cameras Above {MR_CRITICAL_THRESHOLD}% Manual Review Rate",
            font=FONT_SUBTITLE, anchor="w"
        )
        self._table_header_label.pack(fill="x", padx=15, pady=(10, 5))

        header_row = ctk.CTkFrame(table_frame, fg_color=COLORS["accent"], corner_radius=5)
        header_row.pack(fill="x", padx=10)

        for _, display, width in HIGH_MR_COLUMNS:
            ctk.CTkLabel(
                header_row, text=display, font=FONT_TABLE_HEADER,
                width=width, anchor="center"
            ).pack(side="left", padx=2, pady=6)

        self._table_scroll = ctk.CTkScrollableFrame(
            table_frame, fg_color="transparent", height=200
        )
        self._table_scroll.pack(fill="x", padx=10, pady=(0, 10))

        # --- Section C: Reason breakdown charts (side by side) ---
        charts_frame = ctk.CTkFrame(scroll, fg_color=COLORS["card_bg"], corner_radius=10)
        charts_frame.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        ctk.CTkLabel(
            charts_frame, text="Manual Review Reasons Breakdown",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 0))

        charts_inner = ctk.CTkFrame(charts_frame, fg_color="transparent")
        charts_inner.pack(fill="both", expand=True, padx=5, pady=(0, 10))
        charts_inner.columnconfigure(0, weight=1)
        charts_inner.columnconfigure(1, weight=1)
        charts_inner.rowconfigure(0, weight=1)

        # Left: Stacked bar
        fig_stack = Figure(figsize=(6, 4), dpi=100)
        fig_stack.patch.set_facecolor(CHART_BG)
        self._stack_fig = fig_stack
        self._stack_canvas = FigureCanvasTkAgg(fig_stack, master=charts_inner)
        self._stack_canvas.get_tk_widget().grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Right: Fleet donut
        fig_donut = Figure(figsize=(6, 4), dpi=100)
        fig_donut.patch.set_facecolor(CHART_BG)
        self._donut_fig = fig_donut
        self._donut_canvas = FigureCanvasTkAgg(fig_donut, master=charts_inner)
        self._donut_canvas.get_tk_widget().grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

    def refresh(self) -> None:
        """Refresh all sections with current filtered data."""
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
        self._review_breakdown = analytics.compute_manual_review_breakdown(df)

        self._draw_histogram()
        self._rebuild_table()
        self._draw_stacked_bar()
        self._draw_fleet_donut()

    def _draw_histogram(self) -> None:
        """Draw manual review rate distribution histogram."""
        fig = self._hist_fig
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        if self._camera_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._hist_canvas.draw()
            return

        values = self._camera_df["manual_review_rate_pct"].values
        bins = np.arange(0, 110, 10)
        counts, edges = np.histogram(values, bins=bins)

        bar_positions = edges[:-1] + 5
        bar_colors = [COLORS["red"] if mid > MR_CRITICAL_THRESHOLD
                      else COLORS["green"] for mid in bar_positions]

        bars = ax.bar(bar_positions, counts, width=8, color=bar_colors,
                      edgecolor=CHART_BG, linewidth=0.5)

        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        str(int(count)), ha="center", va="bottom",
                        color=CHART_TEXT, fontsize=8, fontweight="bold")

        ax.set_xlabel("Manual Review Rate %", fontsize=9, color=CHART_TEXT)
        ax.set_ylabel("Number of Cameras", fontsize=9, color=CHART_TEXT)
        ax.set_xticks(bar_positions)
        ax.set_xticklabels([f"{int(e)}-{int(e+10)}%" for e in edges[:-1]],
                           fontsize=7, color=CHART_TEXT, rotation=45, ha="right")
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="y", color=CHART_GRID, alpha=0.3)

        ax.axvline(x=MR_CRITICAL_THRESHOLD, color=COLORS["yellow"],
                    linestyle="--", alpha=0.7, linewidth=1,
                    label=f"Threshold: {MR_CRITICAL_THRESHOLD}%")
        ax.legend(fontsize=7, labelcolor=CHART_TEXT, frameon=False)

        fig.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.22)
        self._hist_canvas.draw()

    def _rebuild_table(self) -> None:
        """Rebuild the high manual review rate cameras table."""
        for widget in self._table_scroll.winfo_children():
            widget.destroy()

        if self._camera_df.empty:
            ctk.CTkLabel(
                self._table_scroll, text="No camera data available.",
                font=FONT_BODY, text_color="gray"
            ).pack(pady=20)
            return

        flagged = self._camera_df[
            self._camera_df["manual_review_rate_pct"] > MR_CRITICAL_THRESHOLD
        ].sort_values("manual_review_rate_pct", ascending=False).reset_index(drop=True)

        count = len(flagged)
        self._table_header_label.configure(
            text=f"Cameras Above {MR_CRITICAL_THRESHOLD}% Manual Review Rate ({count} camera{'s' if count != 1 else ''})"
        )

        if flagged.empty:
            ctk.CTkLabel(
                self._table_scroll,
                text="All cameras are within the manual review rate threshold.",
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

            for key, _, width in HIGH_MR_COLUMNS:
                value = row.get(key, "")
                if key == "manual_review_rate_pct":
                    text = f"{value:.1f}%"
                    text_color = COLORS["red"]
                elif key in ("total_manual_review", "total_detected"):
                    text = f"{int(value):,}" if pd.notna(value) else "0"
                    text_color = COLORS["text"]
                else:
                    text = str(value)
                    text_color = COLORS["text"]

                ctk.CTkLabel(
                    row_frame, text=text, font=FONT_TABLE_BODY,
                    width=width, anchor="center", text_color=text_color
                ).pack(side="left", padx=2)

    def _draw_stacked_bar(self) -> None:
        """Draw stacked bar chart showing 7 review reasons per camera."""
        fig = self._stack_fig
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        camera_df = self._camera_df
        if camera_df.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._stack_canvas.draw()
            return

        cameras = camera_df["camera_name"].tolist()
        x = np.arange(len(cameras))
        bar_width = 0.6

        bottom = np.zeros(len(cameras))
        for i, reason_key in enumerate(REASON_SHORT_KEYS):
            col_name = f"{reason_key}_pct_of_review"
            if col_name not in camera_df.columns:
                continue
            values = camera_df[col_name].fillna(0).values
            display_name = REASON_DISPLAY_NAMES.get(f"total_{reason_key}", reason_key)
            color = REASON_COLORS[i % len(REASON_COLORS)]

            ax.bar(x, values, bar_width, bottom=bottom, color=color,
                   label=display_name, edgecolor=CHART_BG, linewidth=0.3)
            bottom += values

        ax.set_xlabel("Camera", fontsize=8, color=CHART_TEXT)
        ax.set_ylabel("% of Manual Review", fontsize=8, color=CHART_TEXT)
        ax.set_xticks(x)
        ax.set_xticklabels(cameras, fontsize=6, color=CHART_TEXT,
                           rotation=45, ha="right")
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="y", color=CHART_GRID, alpha=0.3)
        ax.set_title("Review Reasons per Camera", fontsize=9, color=CHART_TEXT)

        ax.legend(fontsize=5, labelcolor=CHART_TEXT, frameon=False,
                  loc="upper right", ncol=1)

        fig.subplots_adjust(left=0.12, right=0.95, top=0.90, bottom=0.25)
        self._stack_canvas.draw()

    def _draw_fleet_donut(self) -> None:
        """Draw fleet-wide donut chart of review reasons with dual percentages."""
        fig = self._donut_fig
        fig.clear()
        ax = fig.add_subplot(111)

        breakdown = self._review_breakdown
        if breakdown.empty or breakdown["count"].sum() == 0:
            ax.set_facecolor(CHART_FACE)
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._donut_canvas.draw()
            return

        sizes = breakdown["count"].tolist()
        colors = REASON_COLORS[:len(sizes)]

        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct="%1.0f%%",
            colors=colors, startangle=90,
            pctdistance=0.75,
            wedgeprops={"width": 0.4, "edgecolor": CHART_BG}
        )

        for text in autotexts:
            text.set_fontsize(7)
            text.set_color(CHART_TEXT)

        # Legend with dual percentages
        legend_labels = []
        for _, row in breakdown.iterrows():
            name = row["display_name"]
            pct_review = row["pct_of_review"]
            pct_detected = row["pct_of_detected"]
            legend_labels.append(
                f"{name}: {pct_review:.1f}% of Review, {pct_detected:.1f}% of Detected"
            )

        ax.legend(
            wedges, legend_labels, loc="center left",
            bbox_to_anchor=(1.0, 0.5), fontsize=5,
            labelcolor=CHART_TEXT, frameon=False
        )

        ax.set_title("Fleet-Wide Reason Breakdown", fontsize=9, color=CHART_TEXT)
        fig.subplots_adjust(left=0.0, right=0.50, top=0.90, bottom=0.05)
        self._donut_canvas.draw()
