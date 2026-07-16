import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from config import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_VIDEO_EXTENSIONS, HISTORY_DB_PATH
from converters.ffmpeg_setup import is_ffmpeg_available
from converters.file_type import detect_file_type
from converters.history import add_record
from converters.image_converter import convert_image
from converters.video_converter import convert_video

POLL_INTERVAL_SECONDS = 3
STABLE_CHECK_DELAY_SECONDS = 1  # 파일이 아직 복사/다운로드 중인지 확인하려고 잠깐 기다리는 시간
IGNORED_FILENAME_PREFIXES = (".", "~$")
IGNORED_FILENAMES = {"thumbs.db", "desktop.ini", ".ds_store"}


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hotfolder_processed (
                fingerprint TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                processed_at TEXT NOT NULL
            )
            """
        )


def _is_processed(fingerprint: str) -> bool:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM hotfolder_processed WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
    return row is not None


def _mark_processed(fingerprint: str, filename: str) -> None:
    with _get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO hotfolder_processed (fingerprint, filename, processed_at) VALUES (?, ?, ?)",
            (fingerprint, filename, datetime.now().isoformat(timespec="seconds")),
        )


def _unique_path(path: Path) -> Path:
    """같은 이름의 결과물이 완료 폴더에 이미 있으면 (1), (2)를 붙여 겹치지 않게 한다."""
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _should_ignore(filename: str) -> bool:
    lowered = filename.lower()
    if lowered in IGNORED_FILENAMES:
        return True
    return any(lowered.startswith(prefix) for prefix in IGNORED_FILENAME_PREFIXES)


class HotFolderWatcher:
    """지정한 폴더를 주기적으로 스캔해서, 새 이미지/영상 파일을 규칙대로 자동 변환한다."""

    def __init__(self, watch_dir: str, output_dir: str):
        self.watch_dir = Path(watch_dir)
        self.output_dir = Path(output_dir)
        self.processed_count = 0
        self.last_error: str | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._scan_once()
            except Exception as error:
                self.last_error = str(error)
            self._stop_event.wait(POLL_INTERVAL_SECONDS)

    def _scan_once(self) -> None:
        if not self.watch_dir.exists():
            self.last_error = "감시 폴더를 찾을 수 없습니다."
            return

        for entry in sorted(self.watch_dir.iterdir()):
            if self._stop_event.is_set():
                return
            if not entry.is_file() or _should_ignore(entry.name):
                continue

            try:
                stat = entry.stat()
            except OSError:
                continue

            fingerprint = f"{entry.name}:{stat.st_size}:{int(stat.st_mtime)}"
            if _is_processed(fingerprint):
                continue

            # 파일이 아직 복사/다운로드되는 중일 수 있으니, 크기가 안정될 때까지 기다렸다 다시 확인한다.
            time.sleep(STABLE_CHECK_DELAY_SECONDS)
            try:
                stat_again = entry.stat()
            except OSError:
                continue
            if stat_again.st_size != stat.st_size:
                continue  # 아직 쓰는 중이면 다음번 스캔 때 다시 시도한다.

            self._process_file(entry, fingerprint)

    def _process_file(self, entry: Path, fingerprint: str) -> None:
        extension = entry.suffix.lower().lstrip(".")

        try:
            with open(entry, "rb") as file_handle:
                header = file_handle.read(32)
            detection = detect_file_type(header, entry.name)

            if detection["category"] == "image" and extension in ALLOWED_IMAGE_EXTENSIONS:
                output_path = _unique_path(self.output_dir / f"{entry.stem}.jpg")
                convert_image(str(entry), "jpeg", str(output_path))
                add_record(entry.name, extension, "jpg")
                self.processed_count += 1
            elif detection["category"] == "video" and extension in ALLOWED_VIDEO_EXTENSIONS:
                if not is_ffmpeg_available():
                    self.last_error = "FFmpeg가 설치되어 있지 않아 영상 파일은 건너뛰었습니다."
                    return
                output_path = _unique_path(self.output_dir / f"{entry.stem}.mp4")
                convert_video(str(entry), "mp4", str(output_path))
                add_record(entry.name, extension, "mp4")
                self.processed_count += 1
            # 그 외 형식은 규칙이 없으니 건너뛴다 (아래 finally에서 처리 완료로 표시해 재시도하지 않음).
        except Exception as error:
            self.last_error = f"{entry.name} 처리 실패: {error}"
        finally:
            _mark_processed(fingerprint, entry.name)


_watcher: HotFolderWatcher | None = None


def start_watching(watch_dir: str, output_dir: str) -> dict:
    global _watcher

    if _watcher is not None and _watcher.is_alive():
        return {"success": False, "message": "이미 감시 중입니다. 먼저 중지해주세요."}

    watch_path = Path(watch_dir)
    if not watch_path.exists() or not watch_path.is_dir():
        return {"success": False, "message": "감시 폴더 경로가 올바르지 않습니다."}

    _watcher = HotFolderWatcher(watch_dir, output_dir)
    _watcher.start()
    return {"success": True, "message": "감시를 시작했습니다."}


def stop_watching() -> dict:
    global _watcher

    if _watcher is None or not _watcher.is_alive():
        return {"success": False, "message": "감시 중이 아닙니다."}

    _watcher.stop()
    return {"success": True, "message": "감시를 중지했습니다."}


def get_status() -> dict:
    if _watcher is None:
        return {
            "running": False,
            "watch_dir": None,
            "output_dir": None,
            "processed_count": 0,
            "last_error": None,
        }

    return {
        "running": _watcher.is_alive(),
        "watch_dir": str(_watcher.watch_dir),
        "output_dir": str(_watcher.output_dir),
        "processed_count": _watcher.processed_count,
        "last_error": _watcher.last_error,
    }
