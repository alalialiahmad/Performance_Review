"""
outliers_tab.py — Outlier report with flags and reasons.

Displays cameras that deviate statistically from fleet averages,
breach KPI thresholds, or have dominant manual review reasons.
"""

import logging
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pandas as pd

import database
import analytics
import outliers as outlier_module
from ui import (
    FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_TABLE_HEADER, FONT_TABLE_BODY,
    COLORS, STATUS_COLORS,
)

logger = logging.getLogger(__name__)

# Flag type display colors
FLAG_COLORS = {
    "Z-Score": "#F39C12",
    "IQR": "#E67E22",
    "Threshold Breach": "#E74C3C",
    "Dominant Reason": "#9B59B6",
}

# Table columns for outlier report
OUTLIER_COLUMNS = [
    ("camera_name", "Camera", 130),
    ("lot_name", "Lot", 100),
    ("metric", "Metric", 160),
    ("value", "Value", 70),
    ("fleet_mean", "Fleet Mean", 85),
    ("z_score", "Z-Score", 70),
    ("flag_type", "Flag Type", 120),
    ("reason", "Reason", 300),
]


class OutliersTab(ctk.CTkFrame):
    """Outlier detection and reporting tab."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._outlier_df = pd.DataFrame()
        self._flag_filters: dict[str, ctk.BooleanVar] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Build summary cards, filter checkboxes, and outlier table."""
        # --- Summary Section ---
        summary_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        summary_frame.pack(fill="x", padx=15, pady=(15, 10))

        summary_inner = ctk.CTkFrame(summary_frame, fg_color="transparent")
        summary_inner.pack(fill="x", padx=15, pady=10)

        self._summary_label = ctk.CTkLabel(
            summary_inner, text="No outlier analysis run yet",
            font=FONT_SUBTITLE, anchor="w"
        )
        self._summary_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            summary_inner, text="Export Report",
            command=self._on_export, width=120
        ).pack(side="right")

        # --- Filter Checkboxes ---
        filter_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        filter_frame.pack(fill="x", padx=15, pady=(0, 10))

        filter_inner = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_inner.pack(fill="x", padx=15, pady=8)

        ctk.CTkLabel(
            filter_inner, text="Show:", font=FONT_BODY
        ).pack(side="left", padx=(0, 10))

        for flag_type, color in FLAG_COLORS.items():
            var = ctk.BooleanVar(value=True)
            self._flag_filters[flag_type] = var
            ctk.CTkCheckBox(
                filter_inner, text=flag_type, variable=var,
                font=FONT_SMALL, command=self._rebuild_table,
                checkbox_width=18, checkbox_height=18,
                text_color=color
            ).pack(side="left", padx=8)

        # --- Summary Cards Row ---
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=15, pady=(0, 10))

        self._count_labels = {}
        for flag_type, color in FLAG_COLORS.items():
            card = ctk.CTkFrame(cards_frame, fg_color=COLORS["card_bg"], corner_radius=8)
            card.pack(side="left", fill="x", expand=True, padx=3)

            ctk.CTkLabel(
                card, text=flag_type, font=FONT_SMALL,
                text_color=color
            ).pack(padx=10, pady=(8, 0))

            count_label = ctk.CTkLabel(
                card, text="0", font=("Segoe UI", 20, "bold"),
                text_color=color
            )
            count_label.pack(padx=10, pady=(0, 8))
            self._count_labels[flag_type] = count_label

        # --- Table ---
        table_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        table_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Header row
        header_frame = ctk.CTkFrame(table_frame, fg_color=COLORS["accent"], corner_radius=5)
        header_frame.pack(fill="x", padx=10, pady=(10, 0))

        for _, display, width in OUTLIER_COLUMNS:
            ctk.CTkLabel(
                header_frame, text=display, font=FONT_TABLE_HEADER,
                width=width, anchor="center"
            ).pack(side="left", padx=2, pady=6)

        # Scrollable body
        self._body_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self._body_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh(self) -> None:
        """Run outlier analysis and display results."""
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

        self._outlier_df = outlier_module.generate_outlier_report(df)
        self._update_summary()
        self._rebuild_table()

    def _update_summary(self) -> None:
        """Update summary label and count cards."""
        if self._outlier_df.empty:
            self._summary_label.configure(text="No outliers detected")
            for label in self._count_labels.values():
                label.configure(text="0")
            return

        total = len(self._outlier_df)
        counts = self._outlier_df["flag_type"].value_counts().to_dict()

        parts = []
        for flag_type in FLAG_COLORS:
            count = counts.get(flag_type, 0)
            self._count_labels[flag_type].configure(text=str(count))
            if count > 0:
                parts.append(f"{count} {flag_type}")

        self._summary_label.configure(
            text=f"{total} outlier(s) detected: {', '.join(parts)}"
        )

    def _rebuild_table(self) -> None:
        """Rebuild the outlier table rows with current filter state."""
        for widget in self._body_scroll.winfo_children():
            widget.destroy()

        if self._outlier_df.empty:
            ctk.CTkLabel(
                self._body_scroll,
                text="No outliers detected. All cameras are within normal parameters.",
                font=FONT_BODY, text_color="gray"
            ).pack(pady=20)
            return

        # Apply flag type filters
        active_flags = {ft for ft, var in self._flag_filters.items() if var.get()}
        filtered_df = self._outlier_df[
            self._outlier_df["flag_type"].isin(active_flags)
        ]

        if filtered_df.empty:
            ctk.CTkLabel(
                self._body_scroll,
                text="No outliers match the selected filters.",
                font=FONT_BODY, text_color="gray"
            ).pack(pady=20)
            return

        for idx, (_, row) in enumerate(filtered_df.iterrows()):
            flag_type = row.get("flag_type", "")
            flag_color = FLAG_COLORS.get(flag_type, COLORS["text"])

            bg_color = COLORS["bg_dark"] if idx % 2 == 0 else COLORS["card_bg"]
            row_frame = ctk.CTkFrame(
                self._body_scroll, fg_color=bg_color,
                corner_radius=3, height=36
            )
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)

            for key, _, width in OUTLIER_COLUMNS:
                value = row.get(key, "")

                if isinstance(value, float) and value != 0:
                    text = f"{value:.1f}"
                elif isinstance(value, float) and value == 0:
                    text = "-"
                else:
                    text = str(value)

                text_color = flag_color if key == "flag_type" else COLORS["text"]

                ctk.CTkLabel(
                    row_frame, text=text, font=FONT_TABLE_BODY,
                    width=width, anchor="center" if key != "reason" else "w",
                    text_color=text_color
                ).pack(side="left", padx=2)

    def _on_export(self) -> None:
        """Export outlier report to Excel."""
        if self._outlier_df.empty:
            messagebox.showinfo("No Data", "No outliers to export.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Outlier Report",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not file_path:
            return

        try:
            # Get full data for complete export
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
            camera_kpis = analytics.compute_per_camera_kpis(df)
            reasons = analytics.compute_manual_review_breakdown(df)

            from exporter import export_to_excel
            export_to_excel(file_path, fleet, camera_kpis, reasons, self._outlier_df)
            messagebox.showinfo("Export Complete", f"Report saved to:\n{file_path}")
        except Exception as e:
            logger.exception("Export failed")
            messagebox.showerror("Export Error", f"Failed to export: {e}")
