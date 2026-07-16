from pathlib import Path

from PIL import Image

# JPEG는 알파 채널을 지원하지 않으므로 투명 영역을 이 색으로 채운다.
JPEG_BACKGROUND_COLOR = (255, 255, 255)

# Pillow가 요구하는 포맷명과 실제 저장 확장자가 다른 경우를 매핑한다.
FORMAT_TO_EXTENSION = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "GIF": ".gif",
    "TIFF": ".tiff",
}


def _resize_to_max_dimension(image: Image.Image, max_dimension: int) -> Image.Image:
    """긴 변이 max_dimension을 넘으면 비율을 유지한 채 줄인다. 원본보다 키우지는 않는다."""
    longest_side = max(image.size)
    if longest_side <= max_dimension:
        return image

    scale = max_dimension / longest_side
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _png_compress_level(quality: int) -> int:
    """PNG는 무손실이라 quality가 화질에 영향을 주진 않지만, 압축 강도(속도<->용량)에는 반영한다."""
    return max(0, min(9, round((100 - quality) / 100 * 9)))


def convert_image(
    input_path: str,
    output_format: str,
    output_path: str | None = None,
    max_dimension: int | None = None,
    quality: int = 85,
) -> str:
    """이미지 파일을 읽어 지정한 포맷으로 변환해 저장한다.

    Args:
        input_path: 변환할 원본 이미지 경로.
        output_format: 목표 포맷 (예: "jpeg", "png", "webp"). 대소문자 무관.
        output_path: 저장 경로. 생략하면 원본과 같은 폴더에 확장자만 바꿔 저장한다.
        max_dimension: 긴 변 기준 최대 픽셀 크기. None이면 원본 크기를 유지한다.
        quality: JPEG/WEBP 저장 품질 (1~100). PNG는 압축 강도로 환산해 반영한다.

    Returns:
        실제로 저장된 파일의 경로(문자열).
    """
    output_format = output_format.upper()
    if output_format == "JPG":
        output_format = "JPEG"

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

    if output_path is None:
        extension = FORMAT_TO_EXTENSION.get(output_format, f".{output_format.lower()}")
        output_path = str(src.with_suffix(extension))

    with Image.open(src) as image:
        # JPEG로 저장할 때 알파 채널이 있으면 흰 배경 위에 합성한다.
        if output_format == "JPEG" and image.mode in ("RGBA", "LA", "P"):
            rgba_image = image.convert("RGBA")
            background = Image.new("RGB", rgba_image.size, JPEG_BACKGROUND_COLOR)
            background.paste(rgba_image, mask=rgba_image.split()[-1])
            image_to_save = background
        elif output_format == "JPEG" and image.mode != "RGB":
            image_to_save = image.convert("RGB")
        else:
            image_to_save = image

        if max_dimension:
            image_to_save = _resize_to_max_dimension(image_to_save, max_dimension)

        save_kwargs = {}
        if output_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = quality
        elif output_format == "PNG":
            save_kwargs["compress_level"] = _png_compress_level(quality)

        image_to_save.save(output_path, format=output_format, **save_kwargs)

    return output_path
