import base64
import io
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import qrcode

from config import APP_PORT, SHARE_EXPIRY_MINUTES, SHARE_FOLDER

_shares: dict[str, dict] = {}
_lock = threading.Lock()


def get_lan_ip() -> str:
    """같은 와이파이의 다른 기기에서 접속할 수 있는, 이 PC의 로컬 네트워크 IP를 알아낸다."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 실제로 패킷을 보내지 않고, 라우팅에 쓰일 로컬 IP만 확인하는 용도다.
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _remove_share(share_id: str) -> None:
    entry = _shares.pop(share_id, None)
    if entry is not None:
        Path(entry["path"]).unlink(missing_ok=True)


def create_share(file_bytes: bytes, filename: str) -> dict:
    SHARE_FOLDER.mkdir(exist_ok=True)

    share_id = uuid.uuid4().hex
    safe_name = filename or "file"
    file_path = SHARE_FOLDER / f"{share_id}_{safe_name}"
    file_path.write_bytes(file_bytes)

    expires_at = datetime.now() + timedelta(minutes=SHARE_EXPIRY_MINUTES)

    with _lock:
        _shares[share_id] = {
            "path": file_path,
            "filename": safe_name,
            "expires_at": expires_at,
        }

    url = f"http://{get_lan_ip()}:{APP_PORT}/share/{share_id}"

    qr_image = qrcode.make(url)
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    qr_data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    return {
        "share_id": share_id,
        "url": url,
        "qr_data_uri": qr_data_uri,
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "expires_in_minutes": SHARE_EXPIRY_MINUTES,
    }


def get_share(share_id: str) -> dict | None:
    with _lock:
        entry = _shares.get(share_id)
        if entry is None:
            return None
        if datetime.now() >= entry["expires_at"]:
            _remove_share(share_id)
            return None
        return entry


def _cleanup_loop() -> None:
    while True:
        time.sleep(60)
        with _lock:
            now = datetime.now()
            expired_ids = [share_id for share_id, entry in _shares.items() if now >= entry["expires_at"]]
            for share_id in expired_ids:
                _remove_share(share_id)


def start_cleanup_thread() -> None:
    thread = threading.Thread(target=_cleanup_loop, daemon=True)
    thread.start()


def cleanup_stale_share_files() -> None:
    """앱을 껐다 켜면 메모리 속 만료 정보가 사라지므로, 시작할 때 폴더에 남은 오래된 파일을 한 번 정리한다."""
    if not SHARE_FOLDER.exists():
        return

    cutoff = time.time() - SHARE_EXPIRY_MINUTES * 60
    for file_path in SHARE_FOLDER.iterdir():
        if file_path.is_file() and file_path.stat().st_mtime < cutoff:
            file_path.unlink(missing_ok=True)
