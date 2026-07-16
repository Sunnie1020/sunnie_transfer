import subprocess
from pathlib import Path

from converters.ffmpeg_setup import get_ffmpeg_path

CONTAINER_FORMATS = {"mp4", "mov"}


def convert_video(input_path: str, output_format: str, output_path: str) -> str:
    """FFmpeg로 영상 컨테이너를 변환한다 (MP4 <-> MOV).

    먼저 코덱을 그대로 옮기는 remux(-c copy)로 빠르게 시도하고,
    대상 컨테이너가 원본 코덱을 담을 수 없으면 재인코딩으로 다시 시도한다.
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    output_format = output_format.lower()
    if output_format not in CONTAINER_FORMATS:
        raise ValueError(f"지원하지 않는 영상 포맷입니다: {output_format}")

    remux_command = [ffmpeg_path, "-y", "-i", input_path, "-c", "copy", output_path]
    result = subprocess.run(remux_command, capture_output=True, text=True)
    if result.returncode == 0 and Path(output_path).exists():
        return output_path

    reencode_command = [
        ffmpeg_path, "-y", "-i", input_path,
        "-c:v", "libx264", "-c:a", "aac",
        output_path,
    ]
    result = subprocess.run(reencode_command, capture_output=True, text=True)
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "영상 변환에 실패했습니다.")

    return output_path
