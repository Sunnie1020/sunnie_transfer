import json
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
            CREATE TABLE IF NOT EXISTS presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                preset_key TEXT NOT NULL,
                name TEXT NOT NULL,
                options_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def save_preset(preset_key: str, name: str, options: dict) -> None:
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO presets (preset_key, name, options_json, created_at) VALUES (?, ?, ?, ?)",
            (preset_key, name, json.dumps(options, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
        )


def get_presets(preset_key: str) -> list[dict]:
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, options_json FROM presets WHERE preset_key = ? ORDER BY id DESC",
            (preset_key,),
        ).fetchall()
    return [{"id": row["id"], "name": row["name"], "options": json.loads(row["options_json"])} for row in rows]


def delete_preset(preset_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
