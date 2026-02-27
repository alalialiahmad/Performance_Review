"""
database.py — SQLite schema, all queries, and upload history management.

Provides the data access layer for the Parking Analytics application.
All database interactions go through this module.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "parking_analytics.db"

# Column names in the transactions table (excluding id and upload_id)
TRANSACTION_COLUMNS = [
    "date", "camera_name", "camera_direction", "lot_name",
    "total_transactions", "total_accurated", "total_inaccurated",
    "total_archived", "total_archived_accurated", "total_archived_inaccurated",
    "total_manual_review", "total_primary_low_confidence",
    "total_secondary_low_confidence", "total_secondary_not_working",
    "total_different_reading", "total_missing_identifiers",
    "total_no_in_for_out", "total_no_in_from_main",
    "total_archived_ocr", "total_archived_ops", "total_archived_auto_archive",
    "total_pending", "total_manual_link", "total_ocr_review", "total_linked",
]

# Numeric columns only (for aggregation)
NUMERIC_COLUMNS = TRANSACTION_COLUMNS[4:]  # Everything after lot_name


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a connection with WAL mode and foreign keys enabled."""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Create tables and indexes if they do not exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                upload_timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                date_range_start TEXT,
                date_range_end TEXT,
                record_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                camera_name TEXT NOT NULL,
                camera_direction TEXT NOT NULL,
                lot_name TEXT NOT NULL,
                total_transactions INTEGER NOT NULL DEFAULT 0,
                total_accurated INTEGER NOT NULL DEFAULT 0,
                total_inaccurated INTEGER NOT NULL DEFAULT 0,
                total_archived INTEGER NOT NULL DEFAULT 0,
                total_archived_accurated INTEGER NOT NULL DEFAULT 0,
                total_archived_inaccurated INTEGER NOT NULL DEFAULT 0,
                total_manual_review INTEGER NOT NULL DEFAULT 0,
                total_primary_low_confidence INTEGER NOT NULL DEFAULT 0,
                total_secondary_low_confidence INTEGER NOT NULL DEFAULT 0,
                total_secondary_not_working INTEGER NOT NULL DEFAULT 0,
                total_different_reading INTEGER NOT NULL DEFAULT 0,
                total_missing_identifiers INTEGER NOT NULL DEFAULT 0,
                total_no_in_for_out INTEGER NOT NULL DEFAULT 0,
                total_no_in_from_main INTEGER NOT NULL DEFAULT 0,
                total_archived_ocr INTEGER NOT NULL DEFAULT 0,
                total_archived_ops INTEGER NOT NULL DEFAULT 0,
                total_archived_auto_archive INTEGER NOT NULL DEFAULT 0,
                total_pending INTEGER NOT NULL DEFAULT 0,
                total_manual_link INTEGER NOT NULL DEFAULT 0,
                total_ocr_review INTEGER NOT NULL DEFAULT 0,
                total_linked INTEGER NOT NULL DEFAULT 0,
                upload_id INTEGER NOT NULL,
                UNIQUE(date, camera_name),
                FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
            CREATE INDEX IF NOT EXISTS idx_transactions_camera ON transactions(camera_name);
            CREATE INDEX IF NOT EXISTS idx_transactions_lot ON transactions(lot_name);
            CREATE INDEX IF NOT EXISTS idx_transactions_direction ON transactions(camera_direction);
            CREATE INDEX IF NOT EXISTS idx_transactions_upload ON transactions(upload_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_date_lot_dir
                ON transactions(date, lot_name, camera_direction);

            CREATE TABLE IF NOT EXISTS kpi_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT NOT NULL UNIQUE,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
        """)
        conn.commit()
        logger.info("Database initialized successfully at %s", db_path or DB_PATH)
    finally:
        conn.close()


def insert_upload(conn: sqlite3.Connection, file_name: str,
                  date_start: Optional[str] = None,
                  date_end: Optional[str] = None,
                  record_count: int = 0,
                  skipped_count: int = 0) -> int:
    """Record a new upload and return its upload_id."""
    cursor = conn.execute(
        """INSERT INTO uploads (file_name, date_range_start, date_range_end,
           record_count, skipped_count) VALUES (?, ?, ?, ?, ?)""",
        (file_name, date_start, date_end, record_count, skipped_count)
    )
    conn.commit()
    return cursor.lastrowid


def update_upload(conn: sqlite3.Connection, upload_id: int,
                  date_start: str, date_end: str,
                  record_count: int, skipped_count: int) -> None:
    """Update upload record with final import statistics."""
    conn.execute(
        """UPDATE uploads SET date_range_start=?, date_range_end=?,
           record_count=?, skipped_count=? WHERE id=?""",
        (date_start, date_end, record_count, skipped_count, upload_id)
    )
    conn.commit()


def insert_transactions(conn: sqlite3.Connection, records: list[dict],
                        upload_id: int) -> tuple[int, int]:
    """
    Bulk insert transaction rows using INSERT OR IGNORE for deduplication.
    Returns (inserted_count, skipped_count).
    """
    if not records:
        return 0, 0

    columns = TRANSACTION_COLUMNS + ["upload_id"]
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    sql = f"INSERT OR IGNORE INTO transactions ({col_names}) VALUES ({placeholders})"

    total = len(records)
    inserted = 0
    for record in records:
        values = [record.get(col, 0) for col in TRANSACTION_COLUMNS] + [upload_id]
        cursor = conn.execute(sql, values)
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    skipped = total - inserted
    logger.info("Inserted %d rows, skipped %d duplicates", inserted, skipped)
    return inserted, skipped


def delete_upload(conn: sqlite3.Connection, upload_id: int) -> int:
    """Delete an upload and cascade-delete its transactions. Returns deleted transaction count."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE upload_id=?", (upload_id,)
    )
    count = cursor.fetchone()[0]
    conn.execute("DELETE FROM uploads WHERE id=?", (upload_id,))
    conn.commit()
    logger.info("Deleted upload %d and %d associated transactions", upload_id, count)
    return count


def get_uploads(conn: sqlite3.Connection) -> list[dict]:
    """Fetch all upload history records, newest first."""
    cursor = conn.execute(
        "SELECT * FROM uploads ORDER BY upload_timestamp DESC"
    )
    return [dict(row) for row in cursor.fetchall()]


def get_transactions(conn: sqlite3.Connection,
                     date_start: Optional[str] = None,
                     date_end: Optional[str] = None,
                     lot_name: Optional[str] = None,
                     camera_direction: Optional[str] = None,
                     camera_name: Optional[str] = None) -> pd.DataFrame:
    """
    Query transactions with optional filters and return as a pandas DataFrame.
    Pass None for any filter to skip it (include all values).
    """
    sql = "SELECT * FROM transactions WHERE 1=1"
    params: list = []

    if date_start:
        sql += " AND date >= ?"
        params.append(date_start)
    if date_end:
        sql += " AND date <= ?"
        params.append(date_end)
    if lot_name:
        sql += " AND lot_name = ?"
        params.append(lot_name)
    if camera_direction:
        sql += " AND camera_direction = ?"
        params.append(camera_direction)
    if camera_name:
        sql += " AND camera_name = ?"
        params.append(camera_name)

    sql += " ORDER BY date, camera_name"

    # Use a regular connection for pd.read_sql_query (row_factory must be default)
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    plain_conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql, plain_conn, params=params)
    finally:
        plain_conn.close()

    return df


def get_distinct_lots(conn: sqlite3.Connection) -> list[str]:
    """Return sorted distinct lot names."""
    cursor = conn.execute("SELECT DISTINCT lot_name FROM transactions ORDER BY lot_name")
    return [row[0] for row in cursor.fetchall()]


def get_distinct_cameras(conn: sqlite3.Connection,
                         lot_name: Optional[str] = None) -> list[str]:
    """Return sorted distinct camera names, optionally filtered by lot."""
    if lot_name:
        cursor = conn.execute(
            "SELECT DISTINCT camera_name FROM transactions WHERE lot_name=? ORDER BY camera_name",
            (lot_name,)
        )
    else:
        cursor = conn.execute(
            "SELECT DISTINCT camera_name FROM transactions ORDER BY camera_name"
        )
    return [row[0] for row in cursor.fetchall()]


def get_date_range(conn: sqlite3.Connection) -> tuple[Optional[str], Optional[str]]:
    """Return (min_date, max_date) from the transactions table."""
    cursor = conn.execute("SELECT MIN(date), MAX(date) FROM transactions")
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    return None, None


# ---------------------------------------------------------------------------
# KPI Cache Functions
# ---------------------------------------------------------------------------

def get_cache(conn: sqlite3.Connection, cache_key: str) -> Optional[str]:
    """Return cached JSON string for the given cache key, or None if not found."""
    cursor = conn.execute(
        "SELECT data_json FROM kpi_cache WHERE cache_key = ?", (cache_key,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def set_cache(conn: sqlite3.Connection, cache_key: str, data_json: str) -> None:
    """Store or update a cache entry."""
    conn.execute(
        "INSERT OR REPLACE INTO kpi_cache (cache_key, data_json) VALUES (?, ?)",
        (cache_key, data_json)
    )
    conn.commit()


def invalidate_cache(conn: sqlite3.Connection) -> None:
    """Delete all cache entries. Called after data import or deletion."""
    conn.execute("DELETE FROM kpi_cache")
    conn.commit()
    logger.info("KPI cache invalidated")
