import io
import os
import re
import subprocess
from pathlib import Path

from PIL import Image

from converters.ffmpeg_setup import get_ffmpeg_path
from converters.image_converter import prepare_image_orientation_and_exif

MIN_IMAGE_WIDTH = 150
MIN_IMAGE_QUALITY = 10
IMAGE_MAX_ATTEMPTS = 40
IMAGE_SHRINK_FACTOR = 0.7

DEFAULT_AUDIO_BITRATE_KBPS = 128
MIN_VIDEO_BITRATE_KBPS = 50


def compress_image_to_target_size(
    input_path: str,
    output_path: str,
    target_bytes: int,
    strip_metadata: bool = True,
) -> tuple[str, int, bool]:
    """이미지를 목표 용량 이하가 되도록 품질/크기를 자동으로 낮춰가며 저장한다.

    무손실 포맷(PNG 등)은 압축이 잘 안 먹히므로 JPEG로 저장해서라도 용량 목표를 우선한다.

    Returns:
        (저장 경로, 실제 결과 용량, 목표 용량 달성 여부)
    """
    with Image.open(input_path) as opened:
        image, exif_bytes = prepare_image_orientation_and_exif(opened, strip_metadata)

        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

    current_image = image
    quality = 90
    best_bytes = None

    for _ in range(IMAGE_MAX_ATTEMPTS):
        buffer = io.BytesIO()
        save_kwargs = {"quality": quality}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        current_image.save(buffer, format="JPEG", **save_kwargs)
        result_bytes = buffer.getvalue()
        if best_bytes is None or len(result_bytes) < len(best_bytes):
            best_bytes = result_bytes

        if len(result_bytes) <= target_bytes:
            with open(output_path, "wb") as file_out:
                file_out.write(result_bytes)
            return output_path, len(result_bytes), True

        if quality > MIN_IMAGE_QUALITY:
            quality -= 10
            continue

        # 품질을 최저까지 낮춰도 안 되면 이미지 자체를 줄이고 품질을 다시 올려서 시도한다.
        new_width = round(current_image.width * IMAGE_SHRINK_FACTOR)
        if new_width < MIN_IMAGE_WIDTH or new_width == current_image.width:
            break
        scale = new_width / current_image.width
        current_image = current_image.resize(
            (new_width, max(1, round(current_image.height * scale))), Image.Resampling.LANCZOS
        )
        quality = 90

    # 목표 용량에 끝내 못 미쳤어도, 가장 작게 나온 결과라도 저장해서 돌려준다.
    with open(output_path, "wb") as file_out:
        file_out.write(best_bytes)
    return output_path, len(best_bytes), False


def _get_duration_seconds(ffmpeg_path: str, input_path: str) -> float:
    result = subprocess.run(
        [ffmpeg_path, "-i", input_path], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        raise RuntimeError("영상 길이를 확인하지 못했습니다.")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def compress_video_to_target_size(
    input_path: str,
    output_path: str,
    target_bytes: int,
) -> tuple[str, int, bool]:
    """2-pass 인코딩으로 목표 용량에 최대한 정확히 맞춘다.

    목표 용량과 영상 길이로 필요한 총 비트레이트를 역산하고, 오디오 몫을 뺀 나머지를
    영상 비트레이트로 정해 1차(통계 수집)·2차(실제 인코딩) 두 번 인코딩한다.

    Returns:
        (저장 경로, 실제 결과 용량, 목표 용량 달성 여부)
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    duration_seconds = _get_duration_seconds(ffmpeg_path, input_path)
    if duration_seconds <= 0:
        raise RuntimeError("영상 길이를 확인하지 못했습니다.")

    total_kilobits = target_bytes * 8 / 1000
    total_bitrate_kbps = total_kilobits / duration_seconds

    # 목표 용량이 작을 땐 오디오도 고정 128kbps 대신 예산의 일부만 쓰도록 줄여서,
    # 작은 목표에서도 영상 비트레이트가 늘 같은 최솟값으로 눌리지 않게 한다.
    audio_bitrate_kbps = min(DEFAULT_AUDIO_BITRATE_KBPS, max(32, round(total_bitrate_kbps * 0.15)))
    video_bitrate_kbps = max(MIN_VIDEO_BITRATE_KBPS, round(total_bitrate_kbps - audio_bitrate_kbps))

    passlog_prefix = str(Path(output_path).with_suffix("")) + "_2pass"
    null_output = "NUL" if os.name == "nt" else "/dev/null"

    pass1_command = [
        ffmpeg_path, "-y", "-i", input_path,
        "-c:v", "libx264", "-b:v", f"{video_bitrate_kbps}k",
        "-pass", "1", "-passlogfile", passlog_prefix,
        "-an", "-f", "null", null_output,
    ]
    pass2_command = [
        ffmpeg_path, "-y", "-i", input_path,
        "-c:v", "libx264", "-b:v", f"{video_bitrate_kbps}k",
        "-pass", "2", "-passlogfile", passlog_prefix,
        "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
        output_path,
    ]

    try:
        result1 = subprocess.run(
            pass1_command, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result1.returncode != 0:
            raise RuntimeError((result1.stderr or "").strip()[-500:] or "1차 인코딩에 실패했습니다.")

        result2 = subprocess.run(
            pass2_command, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result2.returncode != 0 or not Path(output_path).exists():
            raise RuntimeError((result2.stderr or "").strip()[-500:] or "2차 인코딩에 실패했습니다.")
    finally:
        for suffix in ("-0.log", "-0.log.mbtree", "-0.log.temp"):
            Path(f"{passlog_prefix}{suffix}").unlink(missing_ok=True)

    result_size = Path(output_path).stat().st_size
    return output_path, result_size, result_size <= target_bytes * 1.05
