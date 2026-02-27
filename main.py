"""
main.py — Application entry point and main window.

Wires together the database, UI tabs, global filter bar, and export functionality.
Uses CustomTkinter for a modern dark-themed Windows desktop application.
"""

import sys
import logging
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import database
import analytics
import exporter as export_module
from outliers import generate_outlier_report
from ui.dashboard_tab import DashboardTab
from ui.import_tab import ImportTab
from ui.cameras_tab import CamerasTab
from ui.trends_tab import TrendsTab
from ui.outliers_tab import OutliersTab

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "parking_analytics.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class ParkingAnalyticsApp(ctk.CTk):
    """Main application window for Parking Analytics."""

    def __init__(self):
        super().__init__()

        self.title("LPR KPIs Analytics")
        self.geometry("1400x900")
        self.minsize(1200, 700)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize database
        database.init_db()

        # Shared filter state
        self.filters: dict = {
            "date_start": None,
            "date_end": None,
            "lot_name": None,
            "camera_direction": None,
        }

        # Track which tabs are stale and need refresh
        self._stale_tabs: set[str] = set()

        self._build_ui()
        self._load_initial_data()

    def _build_ui(self) -> None:
        """Build the main application layout."""
        # --- Top Bar: Title + Filters ---
        top_frame = ctk.CTkFrame(self, fg_color="#0f3460", corner_radius=0, height=60)
        top_frame.pack(fill="x")
        top_frame.pack_propagate(False)

        ctk.CTkLabel(
            top_frame, text="LPR KPIs Analytics",
            font=("Segoe UI", 18, "bold"), text_color="white"
        ).pack(side="left", padx=20)

        # Filter controls (right side of top bar)
        filter_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        filter_frame.pack(side="right", padx=20)

        # Date range
        ctk.CTkLabel(filter_frame, text="From:", font=("Segoe UI", 11),
                      text_color="white").pack(side="left", padx=(0, 3))
        self._date_start_entry = ctk.CTkEntry(
            filter_frame, placeholder_text="YYYY-MM-DD", width=110, height=28
        )
        self._date_start_entry.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(filter_frame, text="To:", font=("Segoe UI", 11),
                      text_color="white").pack(side="left", padx=(0, 3))
        self._date_end_entry = ctk.CTkEntry(
            filter_frame, placeholder_text="YYYY-MM-DD", width=110, height=28
        )
        self._date_end_entry.pack(side="left", padx=(0, 12))

        # Lot filter
        ctk.CTkLabel(filter_frame, text="Lot:", font=("Segoe UI", 11),
                      text_color="white").pack(side="left", padx=(0, 3))
        self._lot_menu = ctk.CTkOptionMenu(
            filter_frame, values=["All Lots"], width=140, height=28
        )
        self._lot_menu.pack(side="left", padx=(0, 12))

        # Direction filter
        ctk.CTkLabel(filter_frame, text="Direction:", font=("Segoe UI", 11),
                      text_color="white").pack(side="left", padx=(0, 3))
        self._direction_menu = ctk.CTkOptionMenu(
            filter_frame, values=["All", "IN", "OUT"], width=80, height=28
        )
        self._direction_menu.pack(side="left", padx=(0, 12))

        # Apply button
        ctk.CTkButton(
            filter_frame, text="Apply Filters",
            command=self._on_apply_filters, width=100, height=28,
            fg_color="#27AE60", hover_color="#219A52"
        ).pack(side="left", padx=(0, 5))

        # Reset button
        ctk.CTkButton(
            filter_frame, text="Reset",
            command=self._on_reset_filters, width=60, height=28,
            fg_color="#7f8c8d", hover_color="#636e72"
        ).pack(side="left")

        # --- Tab View ---
        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(5, 5))

        # Create tabs
        self.tabview.add("Dashboard")
        self.tabview.add("Import Data")
        self.tabview.add("Cameras")
        self.tabview.add("Trends")
        self.tabview.add("Outliers")

        # Instantiate tab content
        self.dashboard_tab = DashboardTab(self.tabview.tab("Dashboard"), self)
        self.dashboard_tab.pack(fill="both", expand=True)

        self.import_tab = ImportTab(self.tabview.tab("Import Data"), self)
        self.import_tab.pack(fill="both", expand=True)

        self.cameras_tab = CamerasTab(self.tabview.tab("Cameras"), self)
        self.cameras_tab.pack(fill="both", expand=True)

        self.trends_tab = TrendsTab(self.tabview.tab("Trends"), self)
        self.trends_tab.pack(fill="both", expand=True)

        self.outliers_tab = OutliersTab(self.tabview.tab("Outliers"), self)
        self.outliers_tab.pack(fill="both", expand=True)

        # Tab change handler for lazy refresh
        self.tabview.configure(command=self._on_tab_changed)

        # --- Bottom Bar ---
        bottom_frame = ctk.CTkFrame(self, fg_color="#0f3460", corner_radius=0, height=40)
        bottom_frame.pack(fill="x")
        bottom_frame.pack_propagate(False)

        ctk.CTkButton(
            bottom_frame, text="Export Full Report",
            command=self._on_export_full, width=140, height=28,
            fg_color="#27AE60", hover_color="#219A52"
        ).pack(side="left", padx=20, pady=6)

        ctk.CTkButton(
            bottom_frame, text="Export Dashboard PNG",
            command=self._on_export_png, width=160, height=28
        ).pack(side="left", padx=(0, 20), pady=6)

        self._status_label = ctk.CTkLabel(
            bottom_frame, text="Ready", font=("Segoe UI", 10),
            text_color="#aaaaaa", anchor="e"
        )
        self._status_label.pack(side="right", padx=20)

    def _load_initial_data(self) -> None:
        """Load initial filter options and refresh the active tab."""
        self._refresh_filter_options()
        self._refresh_active_tab()

    def _refresh_filter_options(self) -> None:
        """Reload lot and date range options for the filter dropdowns."""
        conn = database.get_connection()
        try:
            lots = database.get_distinct_lots(conn)
            date_range = database.get_date_range(conn)
        finally:
            conn.close()

        lot_values = ["All Lots"] + lots
        self._lot_menu.configure(values=lot_values)

        if date_range[0] and not self._date_start_entry.get():
            self._date_start_entry.delete(0, "end")
            self._date_start_entry.insert(0, date_range[0])
        if date_range[1] and not self._date_end_entry.get():
            self._date_end_entry.delete(0, "end")
            self._date_end_entry.insert(0, date_range[1])

    def _on_apply_filters(self) -> None:
        """Read filter values and refresh all tabs."""
        date_start = self._date_start_entry.get().strip() or None
        date_end = self._date_end_entry.get().strip() or None
        lot = self._lot_menu.get()
        direction = self._direction_menu.get()

        self.filters["date_start"] = date_start
        self.filters["date_end"] = date_end
        self.filters["lot_name"] = None if lot == "All Lots" else lot
        self.filters["camera_direction"] = None if direction == "All" else direction

        self._mark_all_stale()
        self._refresh_active_tab()

    def _on_reset_filters(self) -> None:
        """Reset all filters to defaults."""
        self._date_start_entry.delete(0, "end")
        self._date_end_entry.delete(0, "end")
        self._lot_menu.set("All Lots")
        self._direction_menu.set("All")

        self.filters = {
            "date_start": None,
            "date_end": None,
            "lot_name": None,
            "camera_direction": None,
        }

        self._refresh_filter_options()
        self._mark_all_stale()
        self._refresh_active_tab()

    def _on_tab_changed(self) -> None:
        """Refresh the newly selected tab if it's stale."""
        current = self.tabview.get()
        if current in self._stale_tabs:
            self._stale_tabs.discard(current)
            self._refresh_tab(current)

    def _mark_all_stale(self) -> None:
        """Mark all data tabs as needing refresh."""
        self._stale_tabs = {"Dashboard", "Cameras", "Trends", "Outliers"}

    def _refresh_active_tab(self) -> None:
        """Refresh the currently visible tab."""
        current = self.tabview.get()
        self._stale_tabs.discard(current)
        self._refresh_tab(current)

    def _refresh_tab(self, tab_name: str) -> None:
        """Refresh a specific tab by name."""
        tab_map = {
            "Dashboard": self.dashboard_tab,
            "Cameras": self.cameras_tab,
            "Trends": self.trends_tab,
            "Outliers": self.outliers_tab,
        }
        tab = tab_map.get(tab_name)
        if tab:
            try:
                tab.refresh()
            except Exception as e:
                logger.exception("Error refreshing %s tab", tab_name)

    def on_data_changed(self) -> None:
        """Called by import_tab after data import or deletion."""
        self._refresh_filter_options()
        self._mark_all_stale()
        self._refresh_active_tab()

    def _on_export_full(self) -> None:
        """Export complete analytics report to Excel."""
        file_path = filedialog.asksaveasfilename(
            title="Export Full Report",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile="parking_analytics_report.xlsx"
        )
        if not file_path:
            return

        try:
            self._status_label.configure(text="Exporting...")
            self.update_idletasks()

            conn = database.get_connection()
            try:
                df = database.get_transactions(
                    conn,
                    date_start=self.filters.get("date_start"),
                    date_end=self.filters.get("date_end"),
                    lot_name=self.filters.get("lot_name"),
                    camera_direction=self.filters.get("camera_direction"),
                )
            finally:
                conn.close()

            if df.empty:
                messagebox.showinfo("No Data", "No data to export with current filters.")
                self._status_label.configure(text="Ready")
                return

            fleet = analytics.compute_fleet_kpis(df)
            camera_kpis = analytics.compute_per_camera_kpis(df)
            reasons = analytics.compute_manual_review_breakdown(df)
            outlier_report = generate_outlier_report(df)

            export_module.export_to_excel(
                file_path, fleet, camera_kpis, reasons, outlier_report
            )

            self._status_label.configure(text=f"Exported to {Path(file_path).name}")
            messagebox.showinfo("Export Complete", f"Report saved to:\n{file_path}")

        except Exception as e:
            logger.exception("Export failed")
            messagebox.showerror("Export Error", f"Failed to export: {e}")
            self._status_label.configure(text="Export failed")

    def _on_export_png(self) -> None:
        """Export dashboard charts as PNG."""
        file_path = filedialog.asksaveasfilename(
            title="Export Dashboard as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            initialfile="parking_dashboard.png"
        )
        if not file_path:
            return

        try:
            fig = self.dashboard_tab.get_combined_figure()
            export_module.export_dashboard_png(fig, file_path)
            self._status_label.configure(text=f"Exported PNG to {Path(file_path).name}")
            messagebox.showinfo("Export Complete", f"Dashboard saved to:\n{file_path}")
        except Exception as e:
            logger.exception("PNG export failed")
            messagebox.showerror("Export Error", f"Failed to export: {e}")


def global_exception_handler(exc_type, exc_value, exc_tb):
    """Handle uncaught exceptions with a dialog and logging."""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical("Unhandled exception:\n%s", error_msg)
    try:
        messagebox.showerror(
            "Unexpected Error",
            f"An unexpected error occurred:\n\n{exc_value}\n\n"
            "See parking_analytics.log for details."
        )
    except Exception:
        pass


def main():
    """Application entry point."""
    sys.excepthook = global_exception_handler
    logger.info("Starting LPR KPIs Analytics application")

    app = ParkingAnalyticsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
