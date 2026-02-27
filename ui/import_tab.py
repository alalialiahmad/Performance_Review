"""
import_tab.py — File upload UI and upload history table.

Provides the interface for importing Excel files, viewing upload history,
and deleting previously imported reports.
"""

import logging
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import database
import ingestion
from ui import FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_TABLE_HEADER, FONT_TABLE_BODY, COLORS

logger = logging.getLogger(__name__)


class ImportTab(ctk.CTkFrame):
    """File upload and upload history management tab."""

    def __init__(self, master, app):
        """
        Args:
            master: Parent CTkFrame (tab container)
            app: Reference to main ParkingAnalyticsApp for callbacks
        """
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._selected_files: list[str] = []
        self._history_frame_inner = None
        self._build_ui()
        self.refresh_history()

    def _build_ui(self) -> None:
        """Build the import section and upload history table."""
        # --- Import Section ---
        import_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        import_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            import_frame, text="Import Excel Data",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 5))

        # File selection row
        select_row = ctk.CTkFrame(import_frame, fg_color="transparent")
        select_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkButton(
            select_row, text="Select File(s)...",
            command=self._on_select_files, width=140
        ).pack(side="left", padx=(0, 10))

        self._file_label = ctk.CTkLabel(
            select_row, text="No file selected",
            font=FONT_SMALL, text_color="gray", anchor="w"
        )
        self._file_label.pack(side="left", fill="x", expand=True)

        # Import button and progress
        action_row = ctk.CTkFrame(import_frame, fg_color="transparent")
        action_row.pack(fill="x", padx=15, pady=5)

        self._import_btn = ctk.CTkButton(
            action_row, text="Import",
            command=self._on_import, width=140,
            state="disabled"
        )
        self._import_btn.pack(side="left", padx=(0, 10))

        self._progress = ctk.CTkProgressBar(action_row, mode="indeterminate")
        self._progress.pack(side="left", fill="x", expand=True)
        self._progress.set(0)

        # Status message
        self._status_label = ctk.CTkLabel(
            import_frame, text="", font=FONT_SMALL, anchor="w"
        )
        self._status_label.pack(fill="x", padx=15, pady=(5, 15))

        # --- Upload History Section ---
        history_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        history_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        ctk.CTkLabel(
            history_frame, text="Upload History",
            font=FONT_SUBTITLE, anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 5))

        # Header row
        header_row = ctk.CTkFrame(history_frame, fg_color=COLORS["accent"], corner_radius=5)
        header_row.pack(fill="x", padx=15, pady=(5, 0))

        headers = [
            ("File Name", 3),
            ("Upload Date", 2),
            ("Date Range", 2),
            ("Records", 1),
            ("Skipped", 1),
            ("Actions", 1),
        ]
        for text, weight in headers:
            ctk.CTkLabel(
                header_row, text=text, font=FONT_TABLE_HEADER,
                anchor="center"
            ).pack(side="left", fill="x", expand=True, padx=5, pady=8)

        # Scrollable history list
        self._history_scroll = ctk.CTkScrollableFrame(
            history_frame, fg_color="transparent"
        )
        self._history_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def _on_select_files(self) -> None:
        """Open file dialog to select .xlsx files."""
        files = filedialog.askopenfilenames(
            title="Select Excel Report Files",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if files:
            self._selected_files = list(files)
            names = ", ".join(Path(f).name for f in self._selected_files)
            self._file_label.configure(
                text=names if len(names) < 80 else f"{len(self._selected_files)} file(s) selected",
                text_color=COLORS["text"]
            )
            self._import_btn.configure(state="normal")

    def _on_import(self) -> None:
        """Start import in a background thread."""
        if not self._selected_files:
            return

        self._import_btn.configure(state="disabled")
        self._progress.start()
        self._status_label.configure(text="Importing...", text_color=COLORS["yellow"])

        thread = threading.Thread(target=self._run_import, daemon=True)
        thread.start()

    def _run_import(self) -> None:
        """Run import operations in background thread."""
        results = []
        for file_path in self._selected_files:
            result = ingestion.ingest_file(file_path)
            results.append(result)

        # Update UI on main thread
        self.after(0, self._on_import_complete, results)

    def _on_import_complete(self, results: list) -> None:
        """Handle import completion on the main thread."""
        self._progress.stop()
        self._progress.set(0)

        total_inserted = sum(r.rows_inserted for r in results)
        total_skipped = sum(r.rows_skipped for r in results)
        errors = []
        warnings = []
        for r in results:
            errors.extend(r.errors)
            warnings.extend(r.warnings)

        if errors:
            status_text = f"Errors: {'; '.join(errors)}"
            self._status_label.configure(text=status_text, text_color=COLORS["red"])
        elif warnings:
            status_text = (
                f"Imported {total_inserted} rows, {total_skipped} duplicates skipped. "
                f"Warnings: {'; '.join(warnings)}"
            )
            self._status_label.configure(text=status_text, text_color=COLORS["yellow"])
        else:
            status_text = f"Successfully imported {total_inserted} rows, {total_skipped} duplicates skipped."
            self._status_label.configure(text=status_text, text_color=COLORS["green"])

        self._selected_files = []
        self._file_label.configure(text="No file selected", text_color="gray")
        self._import_btn.configure(state="disabled")

        self.refresh_history()
        self.app.on_data_changed()

    def _on_delete_upload(self, upload_id: int, file_name: str) -> None:
        """Delete an upload after confirmation."""
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete upload '{file_name}' and all associated transactions?\n\n"
            "This action cannot be undone."
        )
        if not confirm:
            return

        conn = database.get_connection()
        try:
            count = database.delete_upload(conn, upload_id)
            self._status_label.configure(
                text=f"Deleted '{file_name}' ({count} transactions removed)",
                text_color=COLORS["text"]
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")
        finally:
            conn.close()

        self.refresh_history()
        self.app.on_data_changed()

    def refresh_history(self) -> None:
        """Reload and display upload history from database."""
        # Clear existing rows
        for widget in self._history_scroll.winfo_children():
            widget.destroy()

        conn = database.get_connection()
        try:
            uploads = database.get_uploads(conn)
        finally:
            conn.close()

        if not uploads:
            ctk.CTkLabel(
                self._history_scroll,
                text="No files imported yet. Use the Import button above to get started.",
                font=FONT_BODY, text_color="gray"
            ).pack(pady=20)
            return

        for upload in uploads:
            row_frame = ctk.CTkFrame(
                self._history_scroll, fg_color=COLORS["bg_dark"],
                corner_radius=5, height=40
            )
            row_frame.pack(fill="x", pady=2)
            row_frame.pack_propagate(False)

            # File name
            ctk.CTkLabel(
                row_frame, text=upload["file_name"],
                font=FONT_TABLE_BODY, anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=10)

            # Upload timestamp
            ctk.CTkLabel(
                row_frame, text=upload.get("upload_timestamp", "")[:19],
                font=FONT_TABLE_BODY, width=150, anchor="center"
            ).pack(side="left", padx=5)

            # Date range
            date_start = upload.get("date_range_start", "") or ""
            date_end = upload.get("date_range_end", "") or ""
            date_range = f"{date_start} to {date_end}" if date_start else "N/A"
            ctk.CTkLabel(
                row_frame, text=date_range,
                font=FONT_TABLE_BODY, width=180, anchor="center"
            ).pack(side="left", padx=5)

            # Record count
            ctk.CTkLabel(
                row_frame, text=str(upload.get("record_count", 0)),
                font=FONT_TABLE_BODY, width=60, anchor="center"
            ).pack(side="left", padx=5)

            # Skipped count
            ctk.CTkLabel(
                row_frame, text=str(upload.get("skipped_count", 0)),
                font=FONT_TABLE_BODY, width=60, anchor="center"
            ).pack(side="left", padx=5)

            # Delete button
            upload_id = upload["id"]
            file_name = upload["file_name"]
            ctk.CTkButton(
                row_frame, text="Delete", width=70, height=28,
                fg_color=COLORS["red"], hover_color="#C0392B",
                command=lambda uid=upload_id, fn=file_name: self._on_delete_upload(uid, fn)
            ).pack(side="left", padx=10)
