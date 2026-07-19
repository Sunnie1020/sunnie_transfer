import re
from pathlib import Path
from typing import Callable

import yt_dlp

from converters.ffmpeg_setup import get_ffmpeg_path

_X_URL_PATTERN = re.compile(r"^https?://(www\.)?(twitter\.com|x\.com)/")
_INSTAGRAM_URL_PATTERN = re.compile(r"^https?://(www\.)?instagram\.com/")


def is_x_url(url: str) -> bool:
    return bool(_X_URL_PATTERN.match(url.strip()))


def is_instagram_url(url: str) -> bool:
    return bool(_INSTAGRAM_URL_PATTERN.match(url.strip()))


def _download_media(
    url: str,
    base_output_dir: str,
    job_id: str,
    on_progress: Callable[[float], None] | None = None,
) -> list[str]:
    """yt-dlp로 링크의 사진·영상을 모두 내려받아, 전용 폴더에 저장하고 파일 목록을 돌려준다."""
    job_dir = Path(base_output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def _hook(status):
        if not on_progress or status.get("status") != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        downloaded = status.get("downloaded_bytes")
        if total and downloaded:
            on_progress(min(99, round(downloaded / total * 100)))

    ydl_opts = {
        "outtmpl": str(job_dir / "%(autonumber)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "progress_hooks": [_hook] if on_progress else [],
    }

    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = str(Path(ffmpeg_path).parent)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    files = sorted(str(path) for path in job_dir.iterdir() if path.is_file())
    if not files:
        raise RuntimeError("다운로드할 파일을 찾지 못했습니다.")

    if on_progress:
        on_progress(100)

    return files


def download_x_media(
    url: str, base_output_dir: str, job_id: str, on_progress: Callable[[float], None] | None = None
) -> list[str]:
    """X(트위터) 게시물의 영상을 모두 내려받는다."""
    if not is_x_url(url):
        raise ValueError("올바른 X(트위터) 링크가 아닙니다.")
    return _download_media(url, base_output_dir, job_id, on_progress)


def download_instagram_media(
    url: str, base_output_dir: str, job_id: str, on_progress: Callable[[float], None] | None = None
) -> list[str]:
    """인스타그램 게시물의 사진·영상을 모두 내려받는다."""
    if not is_instagram_url(url):
        raise ValueError("올바른 인스타그램 링크가 아닙니다.")
    return _download_media(url, base_output_dir, job_id, on_progress)
