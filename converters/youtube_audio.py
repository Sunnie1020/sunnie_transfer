import re
from pathlib import Path

import yt_dlp

from converters.ffmpeg_setup import get_ffmpeg_path

_YOUTUBE_URL_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)"
)


def is_youtube_url(url: str) -> bool:
    return bool(_YOUTUBE_URL_PATTERN.match(url.strip()))


def download_youtube_audio(url: str, output_dir: str, job_id: str) -> dict:
    """유튜브 영상의 오디오를 통째로 뽑아 MP3로 저장한다.

    Returns:
        {"path": mp3 파일 경로, "title": 영상 제목}
    """
    url = url.strip()
    if not is_youtube_url(url):
        raise ValueError("올바른 유튜브 링크가 아닙니다.")

    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    output_template = str(Path(output_dir) / f"{job_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "ffmpeg_location": str(Path(ffmpeg_path).parent),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    output_path = Path(output_dir) / f"{job_id}.mp3"
    if not output_path.exists():
        raise RuntimeError("오디오 추출에 실패했습니다.")

    return {"path": str(output_path), "title": info.get("title") or "youtube_audio"}
