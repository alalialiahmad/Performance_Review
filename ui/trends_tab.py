"""
trends_tab.py — Time-series trend charts per camera/lot.

Provides interactive line charts showing KPI trends over time,
with camera/lot selection and KPI metric chooser.
"""

import logging

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import database
import analytics
from ui import (
    FONT_SUBTITLE, FONT_BODY, FONT_SMALL,
    COLORS, STATUS_COLORS, CHART_BG, CHART_FACE, CHART_TEXT, CHART_GRID,
)

logger = logging.getLogger(__name__)

# Available KPI metrics for trend plotting
TREND_METRICS = {
    "accuracy_pct": "Accuracy %",
    "manual_review_rate_pct": "Manual Review Rate %",
    "linking_rate_pct": "Linking Rate %",
    "archive_rate_pct": "Archive Rate %",
    "pending_rate_pct": "Pending Rate %",
}

# Line colors for different cameras
LINE_COLORS = [
    "#3498DB", "#E74C3C", "#27AE60", "#F39C12", "#9B59B6",
    "#1ABC9C", "#E67E22", "#2ECC71", "#34495E", "#C0392B",
    "#2980B9", "#8E44AD", "#D35400", "#16A085", "#7F8C8D",
]


class TrendsTab(ctk.CTkFrame):
    """Time-series trend analysis tab."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._selected_metric = "accuracy_pct"
        self._group_by = "camera_name"
        self._selected_items: set[str] = set()
        self._all_items: list[str] = []
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Build metric selector, camera/lot selection, and chart area."""
        # --- Controls Bar ---
        controls_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        controls_frame.pack(fill="x", padx=15, pady=(15, 10))

        controls_inner = ctk.CTkFrame(controls_frame, fg_color="transparent")
        controls_inner.pack(fill="x", padx=15, pady=10)

        # Metric selector
        ctk.CTkLabel(
            controls_inner, text="Metric:", font=FONT_BODY
        ).pack(side="left", padx=(0, 5))

        self._metric_menu = ctk.CTkOptionMenu(
            controls_inner,
            values=list(TREND_METRICS.values()),
            command=self._on_metric_changed,
            width=180
        )
        self._metric_menu.set("Accuracy %")
        self._metric_menu.pack(side="left", padx=(0, 20))

        # Group-by selector
        ctk.CTkLabel(
            controls_inner, text="Group by:", font=FONT_BODY
        ).pack(side="left", padx=(0, 5))

        self._group_menu = ctk.CTkOptionMenu(
            controls_inner,
            values=["Camera", "Lot"],
            command=self._on_group_changed,
            width=120
        )
        self._group_menu.set("Camera")
        self._group_menu.pack(side="left", padx=(0, 20))

        # Select all / deselect all buttons
        ctk.CTkButton(
            controls_inner, text="Select All",
            command=self._select_all, width=80, height=28
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            controls_inner, text="Clear", command=self._deselect_all,
            width=60, height=28
        ).pack(side="left", padx=2)

        # --- Main Content (Camera list + Chart) ---
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)

        # Camera/Lot selection list (left side)
        selection_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["card_bg"],
                                       corner_radius=10, width=180)
        selection_frame.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        selection_frame.grid_propagate(False)

        ctk.CTkLabel(
            selection_frame, text="Select Items", font=FONT_SMALL,
            anchor="w"
        ).pack(fill="x", padx=10, pady=(10, 5))

        self._selection_scroll = ctk.CTkScrollableFrame(
            selection_frame, fg_color="transparent"
        )
        self._selection_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        # Chart area (right side)
        chart_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["card_bg"], corner_radius=10)
        chart_frame.grid(row=0, column=1, sticky="nsew")

        fig = Figure(figsize=(8, 5), dpi=100)
        fig.patch.set_facecolor(CHART_BG)
        self._fig = fig
        self._ax = fig.add_subplot(111)
        self._ax.set_facecolor(CHART_FACE)

        self._canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        """Refresh the selection list and chart with current data."""
        conn = database.get_connection()
        try:
            if self._group_by == "camera_name":
                self._all_items = database.get_distinct_cameras(conn)
            else:
                self._all_items = database.get_distinct_lots(conn)
        finally:
            conn.close()

        self._rebuild_selection_list()

        # Default: select first 5 items
        if not self._selected_items and self._all_items:
            self._selected_items = set(self._all_items[:5])
            self._update_checkboxes()

        self._redraw_chart()

    def _rebuild_selection_list(self) -> None:
        """Rebuild the checkbox selection list."""
        for widget in self._selection_scroll.winfo_children():
            widget.destroy()

        self._check_vars = {}
        for item in self._all_items:
            var = ctk.BooleanVar(value=item in self._selected_items)
            self._check_vars[item] = var

            cb = ctk.CTkCheckBox(
                self._selection_scroll, text=item,
                variable=var, font=FONT_SMALL,
                command=self._on_selection_changed,
                checkbox_width=18, checkbox_height=18
            )
            cb.pack(fill="x", pady=1)

    def _update_checkboxes(self) -> None:
        """Update checkbox states to match _selected_items."""
        for item, var in self._check_vars.items():
            var.set(item in self._selected_items)

    def _on_selection_changed(self) -> None:
        """Update selected items from checkbox states."""
        self._selected_items = {
            item for item, var in self._check_vars.items() if var.get()
        }
        self._redraw_chart()

    def _on_metric_changed(self, value: str) -> None:
        """Handle metric selector change."""
        reverse_map = {v: k for k, v in TREND_METRICS.items()}
        self._selected_metric = reverse_map.get(value, "accuracy_pct")
        self._redraw_chart()

    def _on_group_changed(self, value: str) -> None:
        """Handle group-by selector change."""
        self._group_by = "camera_name" if value == "Camera" else "lot_name"
        self._selected_items.clear()
        self.refresh()

    def _select_all(self) -> None:
        """Select all items."""
        self._selected_items = set(self._all_items)
        self._update_checkboxes()
        self._redraw_chart()

    def _deselect_all(self) -> None:
        """Deselect all items."""
        self._selected_items.clear()
        self._update_checkboxes()
        self._redraw_chart()

    def _redraw_chart(self) -> None:
        """Redraw the trend line chart."""
        self._ax.clear()
        self._ax.set_facecolor(CHART_FACE)

        if not self._selected_items:
            self._ax.text(
                0.5, 0.5, "Select items to display trends",
                ha="center", va="center", color=CHART_TEXT,
                fontsize=12, transform=self._ax.transAxes
            )
            self._canvas.draw()
            return

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

        if df.empty:
            self._ax.text(
                0.5, 0.5, "No data available",
                ha="center", va="center", color=CHART_TEXT,
                fontsize=12, transform=self._ax.transAxes
            )
            self._canvas.draw()
            return

        # Compute trends
        if self._group_by == "camera_name":
            trend_df = analytics.compute_camera_daily_kpis(df)
        else:
            # Group by (date, lot_name)
            grouped = df.groupby(["date", "lot_name"], as_index=False)[
                analytics.NUMERIC_COLUMNS
            ].sum()
            kpi_rows = []
            for _, row in grouped.iterrows():
                kpis = analytics.compute_kpis(row)
                kpis["date"] = row["date"]
                kpis["lot_name"] = row["lot_name"]
                kpi_rows.append(kpis)
            trend_df = __import__("pandas").DataFrame(kpi_rows)

        if trend_df.empty:
            self._ax.text(
                0.5, 0.5, "No trend data available",
                ha="center", va="center", color=CHART_TEXT,
                fontsize=12, transform=self._ax.transAxes
            )
            self._canvas.draw()
            return

        metric = self._selected_metric
        metric_display = TREND_METRICS.get(metric, metric)

        for i, item in enumerate(sorted(self._selected_items)):
            color = LINE_COLORS[i % len(LINE_COLORS)]
            item_data = trend_df[trend_df[self._group_by] == item].sort_values("date")

            if not item_data.empty and metric in item_data.columns:
                self._ax.plot(
                    item_data["date"].tolist(),
                    item_data[metric].tolist(),
                    color=color, marker="o", markersize=3,
                    linewidth=1.5, label=item
                )

        # Threshold reference lines
        if metric in analytics.KPI_TARGETS:
            target = analytics.KPI_TARGETS[metric]
            thresholds = target["thresholds"]
            self._ax.axhline(
                y=thresholds["good"], color=COLORS["green"],
                linestyle="--", alpha=0.4, linewidth=0.8,
                label=f"Good: {thresholds['good']}%"
            )
            self._ax.axhline(
                y=thresholds["warning"], color=COLORS["yellow"],
                linestyle="--", alpha=0.4, linewidth=0.8,
                label=f"Warning: {thresholds['warning']}%"
            )

        self._ax.set_ylabel(metric_display, fontsize=9, color=CHART_TEXT)
        self._ax.set_xlabel("Date", fontsize=9, color=CHART_TEXT)
        self._ax.tick_params(colors=CHART_TEXT, labelsize=7)
        self._ax.grid(color=CHART_GRID, alpha=0.3)

        # Rotate x-axis labels
        import matplotlib.pyplot as plt
        plt.setp(self._ax.get_xticklabels(), rotation=45, ha="right", fontsize=6)

        # Legend
        if len(self._selected_items) <= 10:
            self._ax.legend(
                fontsize=6, labelcolor=CHART_TEXT, frameon=False,
                loc="upper left", bbox_to_anchor=(1.0, 1.0)
            )
            self._fig.subplots_adjust(left=0.08, right=0.82, top=0.95, bottom=0.18)
        else:
            self._fig.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.18)

        self._canvas.draw()
