import subprocess
from pathlib import Path

from converters.ffmpeg_setup import get_ffmpeg_path


def convert_video_segment_to_gif(
    input_path: str,
    output_path: str,
    start_seconds: float,
    duration_seconds: float,
    width: int = 480,
    fps: int = 10,
) -> str:
    """영상의 한 구간을 잘라 GIF로 만든다. palettegen/paletteuse로 팔레트를 최적화해 용량 대비 화질을 높인다."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    filter_graph = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"

    command = [
        ffmpeg_path, "-y",
        "-ss", str(start_seconds),
        "-t", str(duration_seconds),
        "-i", input_path,
        "-vf", filter_graph,
        "-loop", "0",
        output_path,
    ]

    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "GIF 변환에 실패했습니다.")

    return output_path


def convert_gif_to_video(input_path: str, output_path: str) -> str:
    """GIF를 MP4 영상으로 만든다."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    command = [
        ffmpeg_path, "-y",
        "-i", input_path,
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        # 홀수 크기 GIF도 h264가 요구하는 짝수 크기로 맞춰준다.
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        output_path,
    ]

    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "MP4 변환에 실패했습니다.")

    return output_path
