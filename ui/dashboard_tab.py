"""
dashboard_tab.py — KPI summary cards and matplotlib charts.

Main overview screen with fleet-wide KPI cards and interactive charts:
- Bar chart: Accuracy % per camera
- Pie/donut chart: Manual review reason breakdown
- Line chart: Accuracy & Linking trend over time
- Bar chart: Manual Review Rate per camera
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
from ui import (
    FONT_SUBTITLE, FONT_KPI_VALUE, FONT_KPI_LABEL, FONT_BODY, FONT_SMALL,
    COLORS, STATUS_COLORS, CHART_BG, CHART_FACE, CHART_TEXT, CHART_GRID,
    REASON_COLORS,
)

logger = logging.getLogger(__name__)


class DashboardTab(ctk.CTkFrame):
    """KPI dashboard with summary cards and charts."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._kpi_cards = {}
        self._chart_canvases = {}
        self._chart_figures = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Build KPI cards row and 2x2 chart grid."""
        # --- KPI Cards Row ---
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=15, pady=(15, 10))

        kpi_defs = [
            ("accuracy_pct", "Camera Accuracy"),
            ("manual_review_rate_pct", "Manual Review Rate"),
            ("linking_rate_pct", "Linking Rate"),
            ("archive_rate_pct", "Archive Rate"),
        ]

        for i, (kpi_key, label) in enumerate(kpi_defs):
            cards_frame.columnconfigure(i, weight=1)
            card = self._create_kpi_card(cards_frame, kpi_key, label)
            card.grid(row=0, column=i, padx=5, sticky="nsew")

        # --- Charts Grid (2x2) ---
        charts_frame = ctk.CTkFrame(self, fg_color="transparent")
        charts_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        charts_frame.rowconfigure(0, weight=1)
        charts_frame.rowconfigure(1, weight=1)
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.columnconfigure(1, weight=1)

        # Chart containers
        self._create_chart_container(charts_frame, "accuracy_bar", "Accuracy % by Camera", 0, 0)
        self._create_chart_container(charts_frame, "review_pie", "Manual Review Reasons", 0, 1)
        self._create_chart_container(charts_frame, "trend_line", "Accuracy & Linking Trend", 1, 0)
        self._create_chart_container(charts_frame, "mr_bar", "Manual Review Rate by Camera", 1, 1)

    def _create_kpi_card(self, parent, kpi_key: str, label: str) -> ctk.CTkFrame:
        """Create a single KPI card widget."""
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=10)

        ctk.CTkLabel(
            card, text=label, font=FONT_KPI_LABEL,
            text_color=COLORS["text"]
        ).pack(padx=15, pady=(12, 0))

        value_label = ctk.CTkLabel(
            card, text="--", font=FONT_KPI_VALUE,
            text_color=COLORS["text"]
        )
        value_label.pack(padx=15, pady=(0, 5))

        indicator = ctk.CTkFrame(card, height=4, corner_radius=2, fg_color="gray")
        indicator.pack(fill="x", padx=15, pady=(0, 12))

        self._kpi_cards[kpi_key] = {
            "value_label": value_label,
            "indicator": indicator,
        }

        return card

    def _create_chart_container(self, parent, chart_key: str, title: str,
                                row: int, col: int) -> None:
        """Create a chart container with matplotlib canvas."""
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=10)
        frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        ctk.CTkLabel(
            frame, text=title, font=FONT_SMALL,
            text_color=COLORS["text"], anchor="w"
        ).pack(fill="x", padx=10, pady=(8, 0))

        fig = Figure(figsize=(5, 3), dpi=100)
        fig.patch.set_facecolor(CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)
        fig.subplots_adjust(left=0.15, right=0.95, top=0.92, bottom=0.15)

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self._chart_figures[chart_key] = fig
        self._chart_canvases[chart_key] = canvas

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

        # Fleet KPIs
        fleet = analytics.compute_fleet_kpis(df)
        self._update_kpi_cards(fleet)

        # Charts
        camera_kpis = analytics.compute_per_camera_kpis(df)
        review_breakdown = analytics.compute_manual_review_breakdown(df)
        daily_kpis = analytics.compute_daily_kpis(df)

        self._draw_accuracy_bar(camera_kpis)
        self._draw_review_pie(review_breakdown)
        self._draw_trend_line(daily_kpis)
        self._draw_mr_bar(camera_kpis)

    def _update_kpi_cards(self, fleet: dict) -> None:
        """Update KPI card values and colors."""
        for kpi_key, widgets in self._kpi_cards.items():
            value = fleet.get(kpi_key, 0.0)
            color = STATUS_COLORS.get(fleet.get(f"{kpi_key}_status", ""), "gray")

            widgets["value_label"].configure(text=f"{value:.1f}%")
            widgets["indicator"].configure(fg_color=color)

    def _draw_accuracy_bar(self, camera_kpis: 'pd.DataFrame') -> None:
        """Draw horizontal bar chart of accuracy % per camera."""
        fig = self._chart_figures["accuracy_bar"]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        if camera_kpis.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._chart_canvases["accuracy_bar"].draw()
            return

        cameras = camera_kpis["camera_name"].tolist()
        values = camera_kpis["accuracy_pct"].tolist()
        colors = [STATUS_COLORS.get(analytics.get_kpi_status("accuracy_pct", v), "gray")
                  for v in values]

        y_pos = range(len(cameras))
        ax.barh(y_pos, values, color=colors, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(cameras, fontsize=7, color=CHART_TEXT)
        ax.set_xlabel("Accuracy %", fontsize=8, color=CHART_TEXT)
        ax.set_xlim(0, 105)
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="x", color=CHART_GRID, alpha=0.3)

        # Threshold lines
        ax.axvline(x=95, color=COLORS["green"], linestyle="--", alpha=0.5, linewidth=0.8)
        ax.axvline(x=85, color=COLORS["yellow"], linestyle="--", alpha=0.5, linewidth=0.8)

        fig.subplots_adjust(left=0.3, right=0.95, top=0.95, bottom=0.12)
        self._chart_canvases["accuracy_bar"].draw()

    def _draw_review_pie(self, review_df: 'pd.DataFrame') -> None:
        """Draw donut chart of manual review reason breakdown."""
        fig = self._chart_figures["review_pie"]
        fig.clear()
        ax = fig.add_subplot(111)

        if review_df.empty or review_df["count"].sum() == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            ax.set_facecolor(CHART_FACE)
            self._chart_canvases["review_pie"].draw()
            return

        labels = review_df["display_name"].tolist()
        sizes = review_df["count"].tolist()
        colors = REASON_COLORS[:len(labels)]

        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct="%1.0f%%",
            colors=colors, startangle=90,
            pctdistance=0.75,
            wedgeprops={"width": 0.4, "edgecolor": CHART_BG}
        )

        for text in autotexts:
            text.set_fontsize(7)
            text.set_color(CHART_TEXT)

        ax.legend(
            wedges, labels, loc="center left",
            bbox_to_anchor=(0.95, 0.5), fontsize=6,
            labelcolor=CHART_TEXT, frameon=False
        )

        fig.subplots_adjust(left=0.0, right=0.60, top=0.95, bottom=0.05)
        self._chart_canvases["review_pie"].draw()

    def _draw_trend_line(self, daily_kpis: 'pd.DataFrame') -> None:
        """Draw line chart of accuracy & linking rate over time."""
        fig = self._chart_figures["trend_line"]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        if daily_kpis.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._chart_canvases["trend_line"].draw()
            return

        dates = daily_kpis["date"].tolist()
        accuracy = daily_kpis["accuracy_pct"].tolist()
        linking = daily_kpis["linking_rate_pct"].tolist()

        ax.plot(dates, accuracy, color=COLORS["green"], marker="o",
                markersize=3, linewidth=1.5, label="Accuracy %")
        ax.plot(dates, linking, color="#3498DB", marker="s",
                markersize=3, linewidth=1.5, label="Linking %")

        # Threshold reference lines
        ax.axhline(y=95, color=COLORS["green"], linestyle="--", alpha=0.3, linewidth=0.8)
        ax.axhline(y=85, color=COLORS["yellow"], linestyle="--", alpha=0.3, linewidth=0.8)

        ax.set_ylabel("%", fontsize=8, color=CHART_TEXT)
        ax.legend(fontsize=7, labelcolor=CHART_TEXT, frameon=False)
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(color=CHART_GRID, alpha=0.3)

        # Rotate x-axis labels
        if len(dates) > 5:
            ax.set_xticks(range(0, len(dates), max(1, len(dates) // 5)))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=6)

        fig.subplots_adjust(left=0.12, right=0.95, top=0.95, bottom=0.20)
        self._chart_canvases["trend_line"].draw()

    def _draw_mr_bar(self, camera_kpis: 'pd.DataFrame') -> None:
        """Draw horizontal bar chart of manual review rate per camera."""
        fig = self._chart_figures["mr_bar"]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_FACE)

        if camera_kpis.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=CHART_TEXT, fontsize=12, transform=ax.transAxes)
            self._chart_canvases["mr_bar"].draw()
            return

        cameras = camera_kpis["camera_name"].tolist()
        values = camera_kpis["manual_review_rate_pct"].tolist()
        colors = [STATUS_COLORS.get(analytics.get_kpi_status("manual_review_rate_pct", v), "gray")
                  for v in values]

        y_pos = range(len(cameras))
        ax.barh(y_pos, values, color=colors, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(cameras, fontsize=7, color=CHART_TEXT)
        ax.set_xlabel("Manual Review %", fontsize=8, color=CHART_TEXT)
        ax.tick_params(colors=CHART_TEXT, labelsize=7)
        ax.grid(axis="x", color=CHART_GRID, alpha=0.3)

        # Threshold lines
        ax.axvline(x=20, color=COLORS["green"], linestyle="--", alpha=0.5, linewidth=0.8)
        ax.axvline(x=35, color=COLORS["yellow"], linestyle="--", alpha=0.5, linewidth=0.8)

        fig.subplots_adjust(left=0.3, right=0.95, top=0.95, bottom=0.12)
        self._chart_canvases["mr_bar"].draw()

    def get_combined_figure(self) -> Figure:
        """Create a combined figure of all charts for PNG export."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.patch.set_facecolor(CHART_BG)

        # Copy chart data to combined figure
        for ax_item in axes.flat:
            ax_item.set_facecolor(CHART_FACE)
            ax_item.tick_params(colors=CHART_TEXT)

        fig.suptitle("Parking Analytics Dashboard", color=CHART_TEXT, fontsize=14)
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        return fig
