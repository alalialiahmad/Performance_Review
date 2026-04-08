"""
ingestion.py — Excel parser, validator, and database loader.

Reads .xlsx files exported from the parking reporting system,
validates their structure, normalizes data, and loads into SQLite.
"""

import logging
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd

import database

logger = logging.getLogger(__name__)

# The exact 25 expected column headers from the Excel export
EXPECTED_COLUMNS = [
    "Date", "Camera Name", "Camera Direction", "Lot Name",
    "TotalTransactions", "TotalAccurated", "TotalInaccurated",
    "TotalArchived", "TotalArchivedAccurated", "TotalArchivedInaccurated",
    "TotalManualReview", "TotalPrimaryLowConfidence",
    "TotalSecondaryLowConfidence", "TotalSecondaryNotWorking",
    "TotalDifferentReading", "TotalMissingIdentifiers",
    "TotalNoInForOut", "TotalNoInFromMain",
    "TotalArchivedOCR", "TotalArchivedOPS", "TotalArchivedAutoArchive",
    "TotalPending", "TotalManualLink", "TotalOCRReview", "TotalLinked",
]

# Mapping from Excel column names to database column names (snake_case)
COLUMN_MAP = {
    "Date": "date",
    "Camera Name": "camera_name",
    "Camera Direction": "camera_direction",
    "Lot Name": "lot_name",
    "TotalTransactions": "total_transactions",
    "TotalAccurated": "total_accurated",
    "TotalInaccurated": "total_inaccurated",
    "TotalArchived": "total_archived",
    "TotalArchivedAccurated": "total_archived_accurated",
    "TotalArchivedInaccurated": "total_archived_inaccurated",
    "TotalManualReview": "total_manual_review",
    "TotalPrimaryLowConfidence": "total_primary_low_confidence",
    "TotalSecondaryLowConfidence": "total_secondary_low_confidence",
    "TotalSecondaryNotWorking": "total_secondary_not_working",
    "TotalDifferentReading": "total_different_reading",
    "TotalMissingIdentifiers": "total_missing_identifiers",
    "TotalNoInForOut": "total_no_in_for_out",
    "TotalNoInFromMain": "total_no_in_from_main",
    "TotalArchivedOCR": "total_archived_ocr",
    "TotalArchivedOPS": "total_archived_ops",
    "TotalArchivedAutoArchive": "total_archived_auto_archive",
    "TotalPending": "total_pending",
    "TotalManualLink": "total_manual_link",
    "TotalOCRReview": "total_ocr_review",
    "TotalLinked": "total_linked",
}

# Numeric columns in the Excel file
NUMERIC_EXCEL_COLUMNS = EXPECTED_COLUMNS[4:]  # Everything after "Lot Name"


@dataclass
class IngestionResult:
    """Result of an import operation, returned to the UI."""
    success: bool
    upload_id: int | None = None
    rows_inserted: int = 0
    rows_skipped: int = 0
    total_rows: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_excel(file_path: str) -> tuple[bool, list[str]]:
    """
    Validate that the file exists, is .xlsx, and contains all 25 expected columns.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    path = Path(file_path)

    if not path.exists():
        errors.append(f"File not found: {file_path}")
        return False, errors

    if path.suffix.lower() != ".xlsx":
        errors.append(f"File must be .xlsx format, got: {path.suffix}")
        return False, errors

    try:
        df = pd.read_excel(file_path, engine="openpyxl", nrows=0)
        actual_cols_lower = set(c.strip().lower() for c in df.columns)
        expected_cols_lower = {c.lower() for c in EXPECTED_COLUMNS}

        missing_lower = expected_cols_lower - actual_cols_lower
        if missing_lower:
            # Report using original expected names for clarity
            missing_display = sorted(
                c for c in EXPECTED_COLUMNS if c.lower() in missing_lower
            )
            errors.append(f"Missing columns: {', '.join(missing_display)}")

    except Exception as e:
        errors.append(f"Could not read Excel file: {e}")
        return False, errors

    return len(errors) == 0, errors


def _build_column_rename_map(actual_columns: pd.Index) -> dict[str, str]:
    """
    Build a mapping from actual Excel column names to expected names,
    matching case-insensitively after stripping whitespace.
    """
    expected_by_lower = {c.lower(): c for c in EXPECTED_COLUMNS}
    rename_map = {}
    for actual in actual_columns:
        key = str(actual).strip().lower()
        if key in expected_by_lower:
            rename_map[actual] = expected_by_lower[key]
    return rename_map


def parse_excel(file_path: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Read the Excel file, normalize columns, and return a cleaned DataFrame.
    Returns (cleaned_df, list_of_warnings).
    """
    warnings = []

    df = pd.read_excel(file_path, engine="openpyxl")

    # Normalize column names: strip whitespace and map to expected casing
    col_rename = _build_column_rename_map(df.columns)
    df = df.rename(columns=col_rename)

    # Normalize Date column to YYYY-MM-DD string
    if "Date" in df.columns:
        try:
            df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.strftime("%Y-%m-%d")
        except Exception:
            try:
                df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
            except Exception as e:
                warnings.append(f"Date parsing issue: {e}")

    # Strip whitespace from string columns
    for col in ["Camera Name", "Camera Direction", "Lot Name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Validate Camera Direction — normalize to uppercase before checking
    if "Camera Direction" in df.columns:
        df["Camera Direction"] = df["Camera Direction"].str.upper()
        valid_directions = {"IN", "OUT"}
        invalid_mask = ~df["Camera Direction"].isin(valid_directions)
        if invalid_mask.any():
            count = invalid_mask.sum()
            warnings.append(f"{count} rows with invalid Camera Direction dropped")
            df = df[~invalid_mask].copy()

    # Coerce numeric columns to integers
    for col in NUMERIC_EXCEL_COLUMNS:
        if col in df.columns:
            original = df[col].copy()
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            coerced = (original != df[col]).sum()
            if coerced > 0:
                warnings.append(f"Column '{col}': {coerced} values coerced to 0")

    # Rename columns to database snake_case names
    df = df.rename(columns=COLUMN_MAP)

    return df, warnings


def ingest_file(file_path: str) -> IngestionResult:
    """
    Full ingestion pipeline: validate -> parse -> insert into database.
    Returns an IngestionResult with counts and any errors/warnings.
    """
    result = IngestionResult(success=False)

    # Step 1: Validate
    is_valid, errors = validate_excel(file_path)
    if not is_valid:
        result.errors = errors
        return result

    # Step 2: Parse
    try:
        df, warnings = parse_excel(file_path)
        result.warnings = warnings
        result.total_rows = len(df)
    except Exception as e:
        result.errors.append(f"Failed to parse file: {e}")
        logger.exception("Parse error for %s", file_path)
        return result

    if df.empty:
        result.errors.append("File contains no valid data rows")
        return result

    # Step 3: Insert into database
    conn = database.get_connection()
    try:
        # Create upload record
        file_name = Path(file_path).name
        upload_id = database.insert_upload(conn, file_name)
        result.upload_id = upload_id

        # Convert DataFrame to list of dicts
        records = df.to_dict(orient="records")

        # Bulk insert with deduplication
        inserted, skipped = database.insert_transactions(conn, records, upload_id)
        result.rows_inserted = inserted
        result.rows_skipped = skipped

        # Update upload record with final stats
        date_start = df["date"].min() if not df.empty else None
        date_end = df["date"].max() if not df.empty else None
        database.update_upload(conn, upload_id, date_start, date_end, inserted, skipped)

        result.success = True
        logger.info("Successfully imported %s: %d inserted, %d skipped",
                     file_name, inserted, skipped)

    except Exception as e:
        result.errors.append(f"Database error: {e}")
        logger.exception("Database error during import of %s", file_path)
        # Clean up partial upload
        if result.upload_id:
            try:
                database.delete_upload(conn, result.upload_id)
            except Exception:
                pass
    finally:
        conn.close()

    return result
