import subprocess
from pathlib import Path

from converters.ffmpeg_setup import get_ffmpeg_path

CONTAINER_FORMATS = {"mp4", "mov", "webm"}

CODEC_ENCODERS = {"h264": "libx264", "h265": "libx265"}


def convert_video(
    input_path: str,
    output_format: str,
    output_path: str,
    max_width: int | None = None,
    codec: str = "h264",
    crf: int = 23,
    strip_metadata: bool = True,
) -> str:
    """FFmpeg로 영상을 원하는 컨테이너/해상도/코덱/화질로 변환한다.

    Args:
        max_width: 가로 기준 최대 픽셀 크기. None이면 원본 해상도를 유지한다 (업스케일은 하지 않는다).
        codec: "h264" 또는 "h265". output_format이 "webm"이면 무시하고 VP9를 쓴다.
        crf: 화질 지표. 낮을수록 고화질·큰 용량, 높을수록 저화질·작은 용량 (권장 18~28, VP9는 24~40).
        strip_metadata: True면 촬영 기기·위치 등 컨테이너 메타데이터를 결과물에서 제거한다 (기본값).
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    output_format = output_format.lower()
    if output_format not in CONTAINER_FORMATS:
        raise ValueError(f"지원하지 않는 영상 포맷입니다: {output_format}")

    command = [ffmpeg_path, "-y", "-i", input_path]

    if max_width:
        # 가로가 max_width보다 작으면 그대로 두고(업스케일 방지), 크면 비율을 유지해 줄인다.
        # -2는 x264/x265/VP9가 요구하는 짝수 높이를 자동으로 맞춰준다.
        command += ["-vf", f"scale='min(iw,{max_width})':-2"]

    if strip_metadata:
        command += ["-map_metadata", "-1"]

    if output_format == "webm":
        # WEBM 컨테이너는 VP9 영상 + Opus 오디오만 담을 수 있어서, 요청된 코덱과 무관하게 VP9로 인코딩한다.
        command += [
            "-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0",
            "-c:a", "libopus",
            output_path,
        ]
    else:
        encoder = CODEC_ENCODERS.get(codec)
        if encoder is None:
            raise ValueError(f"지원하지 않는 코덱입니다: {codec}")

        command += [
            "-c:v", encoder, "-crf", str(crf), "-preset", "medium",
            "-c:a", "aac",
            output_path,
        ]

    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "영상 변환에 실패했습니다.")

    return output_path


def extract_thumbnail(input_path: str, output_path: str, timestamp_seconds: float) -> str:
    """영상의 특정 시점 한 프레임을 JPG로 뽑는다."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    command = [
        ffmpeg_path, "-y",
        "-ss", str(timestamp_seconds),
        "-i", input_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ]

    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "썸네일 추출에 실패했습니다.")

    return output_path
