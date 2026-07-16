import subprocess
from pathlib import Path

from config import ALLOWED_AUDIO_BITRATES
from converters.ffmpeg_setup import get_ffmpeg_path


def convert_audio(input_path: str, output_path: str, bitrate: str) -> str:
    """오디오 파일이나 영상 파일에서 오디오만 뽑아 MP3로 인코딩한다.

    입력이 영상(mp4/mov)이어도 '-vn'으로 영상 스트림을 버리고 오디오만 남기기 때문에,
    같은 함수로 '오디오 포맷 변환'과 '영상에서 오디오 추출'을 모두 처리할 수 있다.
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    if bitrate not in ALLOWED_AUDIO_BITRATES:
        raise ValueError(f"지원하지 않는 음질입니다: {bitrate}")

    command = [
        ffmpeg_path, "-y", "-i", input_path,
        "-vn", "-c:a", "libmp3lame", "-b:a", bitrate,
        output_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "오디오 변환에 실패했습니다.")

    return output_path
