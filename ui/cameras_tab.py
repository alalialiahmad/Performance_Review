"""
cameras_tab.py — Per-camera sortable KPI table with filters.

Displays a tabular view of all KPIs per camera, with sortable columns,
color-coded KPI cells, and search functionality.
"""

import logging
from tkinter import filedialog

import customtkinter as ctk
import pandas as pd

import database
import analytics
import exporter
from ui import (
    FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_TABLE_HEADER, FONT_TABLE_BODY,
    COLORS, STATUS_COLORS,
)

logger = logging.getLogger(__name__)

# Column definitions: (key, display_name, width, is_kpi)
TABLE_COLUMNS = [
    ("camera_name", "Camera Name", 150, False),
    ("lot_name", "Lot", 100, False),
    ("camera_direction", "Direction", 70, False),
    ("total_detected", "Detected", 80, False),
    ("accuracy_pct", "Accuracy %", 85, True),
    ("manual_review_rate_pct", "MR Rate %", 80, True),
    ("linking_rate_pct", "Linking %", 80, True),
    ("archive_rate_pct", "Archive %", 80, True),
    ("pending_rate_pct", "Pending %", 75, True),
    ("ocr_review_rate_pct", "OCR Rev %", 75, True),
    ("manual_link_rate_pct", "Man Link %", 80, True),
]

# Sort arrow unicode characters
SORT_ASC = " \u25B2"
SORT_DESC = " \u25BC"


class CamerasTab(ctk.CTkFrame):
    """Per-camera KPI table with sorting and search."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._camera_df = pd.DataFrame()
        self._sort_column = "camera_name"
        self._sort_ascending = True
        self._search_text = ""
        self._header_labels = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Build search bar, table header, scrollable body, and export button."""
        # --- Search & Controls ---
        controls_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        controls_frame.pack(fill="x", padx=15, pady=(15, 10))

        controls_inner = ctk.CTkFrame(controls_frame, fg_color="transparent")
        controls_inner.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            controls_inner, text="Search:", font=FONT_BODY
        ).pack(side="left", padx=(0, 5))

        self._search_entry = ctk.CTkEntry(
            controls_inner, placeholder_text="Filter by camera name...", width=250
        )
        self._search_entry.pack(side="left", padx=(0, 15))
        self._search_entry.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(
            controls_inner, text="Export to Excel",
            command=self._on_export, width=130
        ).pack(side="right")

        # --- Table Container ---
        table_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Header row
        self._header_frame = ctk.CTkFrame(table_frame, fg_color=COLORS["accent"], corner_radius=5)
        self._header_frame.pack(fill="x", padx=10, pady=(10, 0))

        for key, display, width, _ in TABLE_COLUMNS:
            label = ctk.CTkLabel(
                self._header_frame, text=display, font=FONT_TABLE_HEADER,
                width=width, anchor="center", cursor="hand2"
            )
            label.pack(side="left", padx=2, pady=6)
            label.bind("<Button-1>", lambda e, k=key: self._on_sort(k))
            self._header_labels[key] = label

        # Scrollable body
        self._body_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self._body_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh(self) -> None:
        """Refresh table data from database with current filters."""
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
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Rebuild the table rows based on current sort and search state."""
        # Clear existing rows
        for widget in self._body_scroll.winfo_children():
            widget.destroy()

        df = self._camera_df.copy()

        if df.empty:
            ctk.CTkLabel(
                self._body_scroll,
                text="No camera data available. Import data from the Import tab.",
                font=FONT_BODY, text_color="gray"
            ).pack(pady=20)
            return

        # Apply search filter
        if self._search_text:
            mask = df["camera_name"].str.contains(
                self._search_text, case=False, na=False
            )
            df = df[mask]

        # Apply sort
        if self._sort_column in df.columns:
            df = df.sort_values(
                self._sort_column, ascending=self._sort_ascending,
                ignore_index=True
            )

        # Update header sort indicator
        for key, label in self._header_labels.items():
            display = [d for k, d, _, _ in TABLE_COLUMNS if k == key][0]
            if key == self._sort_column:
                arrow = SORT_ASC if self._sort_ascending else SORT_DESC
                label.configure(text=f"{display}{arrow}")
            else:
                label.configure(text=display)

        # Build rows
        for idx, (_, row) in enumerate(df.iterrows()):
            bg_color = COLORS["bg_dark"] if idx % 2 == 0 else COLORS["card_bg"]
            row_frame = ctk.CTkFrame(
                self._body_scroll, fg_color=bg_color,
                corner_radius=3, height=32
            )
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)

            for key, _, width, is_kpi in TABLE_COLUMNS:
                value = row.get(key, "")

                if is_kpi and isinstance(value, (int, float)):
                    text = f"{value:.1f}%"
                    status = analytics.get_kpi_status(key, value)
                    text_color = STATUS_COLORS.get(status, COLORS["text"])
                elif key == "total_detected":
                    text = f"{int(value):,}" if pd.notna(value) else "0"
                    text_color = COLORS["text"]
                else:
                    text = str(value)
                    text_color = COLORS["text"]

                ctk.CTkLabel(
                    row_frame, text=text, font=FONT_TABLE_BODY,
                    width=width, anchor="center", text_color=text_color
                ).pack(side="left", padx=2)

    def _on_sort(self, column: str) -> None:
        """Toggle sort on column click."""
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        self._rebuild_table()

    def _on_search(self, event=None) -> None:
        """Filter table by search text."""
        self._search_text = self._search_entry.get().strip()
        self._rebuild_table()

    def _on_export(self) -> None:
        """Export current camera KPIs to Excel."""
        if self._camera_df.empty:
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Camera KPIs",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not file_path:
            return

        try:
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

            fleet = analytics.compute_fleet_kpis(df)
            reasons = analytics.compute_manual_review_breakdown(df)

            from outliers import generate_outlier_report
            outlier_report = generate_outlier_report(df)

            exporter.export_to_excel(
                file_path, fleet, self._camera_df, reasons, outlier_report
            )
            logger.info("Exported camera KPIs to %s", file_path)
        except Exception as e:
            logger.exception("Export failed")
            from tkinter import messagebox
            messagebox.showerror("Export Error", f"Failed to export: {e}")
