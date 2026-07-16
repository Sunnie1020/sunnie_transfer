import sqlite3
from datetime import datetime, timedelta

from config import HISTORY_DB_PATH

DAILY_STATS_DAYS = 14
TOOL_RANKING_LIMIT = 8


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

        # 이전 버전 DB에는 용량 컬럼이 없을 수 있으니, 없으면 추가한다 (통계 대시보드의 "절약한 용량"용).
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversions)")}
        if "original_size" not in existing_columns:
            conn.execute("ALTER TABLE conversions ADD COLUMN original_size INTEGER")
        if "compressed_size" not in existing_columns:
            conn.execute("ALTER TABLE conversions ADD COLUMN compressed_size INTEGER")


def add_record(
    filename: str,
    source_format: str,
    target_format: str,
    original_size: int | None = None,
    compressed_size: int | None = None,
) -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversions
                (filename, source_format, target_format, converted_at, original_size, compressed_size)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                source_format.lower(),
                target_format.lower(),
                datetime.now().isoformat(timespec="seconds"),
                original_size,
                compressed_size,
            ),
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


def get_stats() -> dict:
    """카드+막대 차트용 통계: 전체/오늘 변환 수, 절약한 총 용량, 도구별 순위, 최근 일별 변환 수."""
    with _get_connection() as conn:
        total_conversions = conn.execute("SELECT COUNT(*) AS count FROM conversions").fetchone()["count"]

        today = datetime.now().date().isoformat()
        today_count = conn.execute(
            "SELECT COUNT(*) AS count FROM conversions WHERE substr(converted_at, 1, 10) = ?",
            (today,),
        ).fetchone()["count"]

        saved_row = conn.execute(
            """
            SELECT COALESCE(SUM(original_size - compressed_size), 0) AS saved
            FROM conversions
            WHERE original_size IS NOT NULL
              AND compressed_size IS NOT NULL
              AND original_size > compressed_size
            """
        ).fetchone()
        total_saved_bytes = saved_row["saved"]

        ranking_rows = conn.execute(
            """
            SELECT source_format, target_format, COUNT(*) AS count
            FROM conversions
            GROUP BY source_format, target_format
            ORDER BY count DESC
            LIMIT ?
            """,
            (TOOL_RANKING_LIMIT,),
        ).fetchall()
        tool_ranking = [
            {"source": row["source_format"], "target": row["target_format"], "count": row["count"]}
            for row in ranking_rows
        ]

        daily_rows = conn.execute(
            """
            SELECT substr(converted_at, 1, 10) AS day, COUNT(*) AS count
            FROM conversions
            WHERE converted_at >= ?
            GROUP BY day
            """,
            ((datetime.now() - timedelta(days=DAILY_STATS_DAYS - 1)).date().isoformat(),),
        ).fetchall()
        counts_by_day = {row["day"]: row["count"] for row in daily_rows}

    daily_counts = []
    for offset in range(DAILY_STATS_DAYS - 1, -1, -1):
        day = (datetime.now() - timedelta(days=offset)).date().isoformat()
        daily_counts.append({"date": day, "count": counts_by_day.get(day, 0)})

    return {
        "total_conversions": total_conversions,
        "today_count": today_count,
        "total_saved_bytes": total_saved_bytes,
        "tool_ranking": tool_ranking,
        "daily_counts": daily_counts,
    }
