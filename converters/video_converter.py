import subprocess
from pathlib import Path

from converters.ffmpeg_setup import get_ffmpeg_path

CONTAINER_FORMATS = {"mp4", "mov"}

CODEC_ENCODERS = {"h264": "libx264", "h265": "libx265"}


def convert_video(
    input_path: str,
    output_format: str,
    output_path: str,
    max_width: int | None = None,
    codec: str = "h264",
    crf: int = 23,
) -> str:
    """FFmpeg로 영상을 원하는 컨테이너/해상도/코덱/화질로 변환한다.

    Args:
        max_width: 가로 기준 최대 픽셀 크기. None이면 원본 해상도를 유지한다 (업스케일은 하지 않는다).
        codec: "h264" 또는 "h265".
        crf: 화질 지표. 낮을수록 고화질·큰 용량, 높을수록 저화질·작은 용량 (권장 18~28).
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    output_format = output_format.lower()
    if output_format not in CONTAINER_FORMATS:
        raise ValueError(f"지원하지 않는 영상 포맷입니다: {output_format}")

    encoder = CODEC_ENCODERS.get(codec)
    if encoder is None:
        raise ValueError(f"지원하지 않는 코덱입니다: {codec}")

    command = [ffmpeg_path, "-y", "-i", input_path]

    if max_width:
        # 가로가 max_width보다 작으면 그대로 두고(업스케일 방지), 크면 비율을 유지해 줄인다.
        # -2는 x264/x265가 요구하는 짝수 높이를 자동으로 맞춰준다.
        command += ["-vf", f"scale='min(iw,{max_width})':-2"]

    command += [
        "-c:v", encoder, "-crf", str(crf), "-preset", "medium",
        "-c:a", "aac",
        output_path,
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "영상 변환에 실패했습니다.")

    return output_path
