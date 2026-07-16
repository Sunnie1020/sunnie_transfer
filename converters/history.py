import sqlite3
from datetime import datetime

from config import HISTORY_DB_PATH


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                source_format TEXT NOT NULL,
                target_format TEXT NOT NULL,
                converted_at TEXT NOT NULL
            )
            """
        )


def add_record(filename: str, source_format: str, target_format: str) -> None:
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO conversions (filename, source_format, target_format, converted_at) VALUES (?, ?, ?, ?)",
            (filename, source_format.lower(), target_format.lower(), datetime.now().isoformat(timespec="seconds")),
        )


def get_recent_records(limit: int = 100) -> list[dict]:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT filename, source_format, target_format, converted_at
            FROM conversions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
