"""
dashboard_tab.py — KPI summary cards paired with time-series trend charts.

Main overview screen with 4 panels arranged in a 2x2 grid. Each panel
contains a KPI card showing the current fleet-wide value and a line chart
showing that KPI over time. Lines are colored green when meeting the
target threshold and red when below.
"""

import logging

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import database
import analytics
from analytics import KPI_TARGETS
from ui import (
    FONT_KPI_VALUE, FONT_KPI_LABEL, FONT_SMALL,
    COLORS, STATUS_COLORS, CHART_BG, CHART_FACE, CHART_TEXT, CHART_GRID,
)

logger = logging.getLogger(__name__)

# The 4 dashboard chart definitions — one per KPI
DASHBOARD_CHARTS = [
    {"key": "accuracy_pct", "label": "Overall Accuracy %", "row": 0, "col": 0},
    {"key": "manual_review_rate_pct", "label": "Overall Manual Review Rate", "row": 0, "col": 1},
    {"key": "archive_rate_pct", "label": "Overall Archive Rate", "row": 1, "col": 0},
    {"key": "linking_rate_pct", "label": "Overall Linking Rate", "row": 1, "col": 1},
]


class DashboardTab(ctk.CTkFrame):
    """KPI dashboard with paired summary cards and trend charts."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._kpi_cards = {}
        self._chart_canvases = {}
        self._chart_figures = {}
        self._daily_kpis = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build 2x2 grid of KPI card + chart panels."""
        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        grid_frame.rowconfigure(0, weight=1)
        grid_frame.rowconfigure(1, weight=1)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        for chart_def in DASHBOARD_CHARTS:
            self._create_kpi_chart_pair(
                grid_frame,
                chart_def["key"],
                chart_def["label"],
                chart_def["row"],
                chart_def["col"],
            )

    def _create_kpi_chart_pair(self, parent, kpi_key: str, label: str,
                                row: int, col: int) -> None:
        """Create a panel with a KPI card on top and a trend chart below."""
        panel = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=10)
        panel.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        # --- KPI Card (top of panel) ---
        card_frame = ctk.CTkFrame(panel, fg_color="transparent")
        card_frame.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            card_frame, text=label, font=FONT_KPI_LABEL,
            text_color=COLORS["text"], anchor="w"
        ).pack(side="left", padx=(5, 0))

        value_label = ctk.CTkLabel(
            card_frame, text="--", font=FONT_KPI_VALUE,
            text_color=COLORS["text"]
        )
        value_label.pack(side="right", padx=(0, 5))

        indicator = ctk.CTkFrame(panel, height=3, corner_radius=2, fg_color="gray")
        indicator.pack(fill="x", padx=10, pady=(2, 0))

        self._kpi_cards[kpi_key] = {
            "value_label": value_label,
            "indicator": indicator,
        }

        # --- Chart (bottom of panel) ---
        fig = Figure(figsize=(5, 2.5), dpi=100)
        fig.patch.set_facecolor(CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)
        fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.18)

        canvas = FigureCanvasTkAgg(fig, master=panel)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self._chart_figures[kpi_key] = fig
        self._chart_canvases[kpi_key] = canvas

    def refresh(self) -> None:
        """Refresh all KPI cards and charts with current filtered data."""
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

        # Compute fleet KPIs and daily trend
        fleet = analytics.compute_fleet_kpis(df)
        self._daily_kpis = analytics.compute_daily_kpis(df)

        # Update cards and draw charts
        self._update_kpi_cards(fleet)
        for chart_def in DASHBOARD_CHARTS:
            self._draw_kpi_trend(chart_def["key"])

    def _update_kpi_cards(self, fleet: dict) -> None:
        """Update KPI card values and color indicators."""
        for kpi_key, widgets in self._kpi_cards.items():
            value = fleet.get(kpi_key, 0.0)
            status = fleet.get(f"{kpi_key}_status", "")
            color = STATUS_COLORS.get(status, "gray")

            widgets["value_label"].configure(text=f"{value:.1f}%")
            widgets["indicator"].configure(fg_color=color)

    def _draw_kpi_trend(self, kpi_key: str) -> None:
        """Draw a time-series trend chart for a single KPI with green/red coloring."""
        fig = self._chart_figures[kpi_key]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        daily = self._daily_kpis
        if daily is None or daily.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.18)
            self._chart_canvases[kpi_key].draw()
            return

        # Get target threshold and direction for this KPI
        target_info = KPI_TARGETS.get(kpi_key, {})
        threshold = target_info.get("thresholds", {}).get("good", 0)
        higher_is_better = target_info.get("higher_is_better", True)

        dates = daily["date"].tolist()
        values = daily[kpi_key].tolist()

        # Draw line segments colored green/red based on threshold
        for i in range(len(dates) - 1):
            v = values[i]
            meets_target = v >= threshold if higher_is_better else v <= threshold
            color = COLORS["green"] if meets_target else COLORS["red"]
            ax.plot(dates[i:i+2], values[i:i+2], color=color, linewidth=1.5,
                    solid_capstyle="round")

        # Draw data point markers with per-point coloring
        for d, v in zip(dates, values):
            meets_target = v >= threshold if higher_is_better else v <= threshold
            color = COLORS["green"] if meets_target else COLORS["red"]
            ax.plot(d, v, "o", color=color, markersize=4, zorder=5)

        # Horizontal threshold reference line
        ax.axhline(y=threshold, color=COLORS["yellow"], linestyle="--",
                    alpha=0.6, linewidth=0.8,
                    label=f"Target: {threshold}%")

        # Styling
        ax.set_ylabel("%", fontsize=8, color=CHART_TEXT)
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(color=CHART_GRID, alpha=0.3)

        # Rotate x-axis labels for readability
        if len(dates) > 5:
            step = max(1, len(dates) // 6)
            ax.set_xticks(range(0, len(dates), step))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=6)

        # Legend
        ax.legend(fontsize=6, labelcolor=CHART_TEXT, frameon=False, loc="upper right")

        fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.22)
        self._chart_canvases[kpi_key].draw()

    def get_combined_figure(self) -> Figure:
        """Create a combined 2x2 figure of all trend charts for PNG export."""
        # Re-fetch data for export
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

        daily = analytics.compute_daily_kpis(df)

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.patch.set_facecolor(CHART_BG)
        fig.suptitle("Parking Analytics Dashboard", color=CHART_TEXT, fontsize=14)

        for chart_def, ax in zip(DASHBOARD_CHARTS, axes.flat):
            kpi_key = chart_def["key"]
            label = chart_def["label"]
            ax.set_facecolor(CHART_FACE)
            ax.set_title(label, color=CHART_TEXT, fontsize=10)

            if daily.empty:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
                continue

            target_info = KPI_TARGETS.get(kpi_key, {})
            threshold = target_info.get("thresholds", {}).get("good", 0)
            higher_is_better = target_info.get("higher_is_better", True)

            dates = daily["date"].tolist()
            values = daily[kpi_key].tolist()

            for i in range(len(dates) - 1):
                v = values[i]
                meets = v >= threshold if higher_is_better else v <= threshold
                color = COLORS["green"] if meets else COLORS["red"]
                ax.plot(dates[i:i+2], values[i:i+2], color=color, linewidth=1.5)

            for d, v in zip(dates, values):
                meets = v >= threshold if higher_is_better else v <= threshold
                color = COLORS["green"] if meets else COLORS["red"]
                ax.plot(d, v, "o", color=color, markersize=3)

            ax.axhline(y=threshold, color=COLORS["yellow"], linestyle="--",
                        alpha=0.6, linewidth=0.8)
            ax.tick_params(colors=CHART_TEXT, labelsize=7)
            ax.grid(color=CHART_GRID, alpha=0.3)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=6)

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        return fig
