from pathlib import Path

from PIL import Image

from converters.image_converter import _png_compress_level

# 워터마크가 원본보다 너무 크지 않도록 원본 폭의 이 비율로 제한한다.
WATERMARK_MAX_WIDTH_RATIO = 1 / 5
# 워터마크와 이미지 가장자리 사이 여백 (원본 폭 기준 비율).
WATERMARK_MARGIN_RATIO = 1 / 50


def _resize_to_width(image: Image.Image, target_width: int) -> Image.Image:
    """가로 폭 기준으로 줄인다. 원본이 이미 더 작으면 그대로 둔다 (업스케일 안 함)."""
    if image.width <= target_width:
        return image

    scale = target_width / image.width
    new_size = (target_width, max(1, round(image.height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _watermark_position_xy(position: str, base_size: tuple, mark_size: tuple, margin: int) -> tuple:
    base_w, base_h = base_size
    mark_w, mark_h = mark_size
    positions = {
        "top-left": (margin, margin),
        "top-right": (base_w - mark_w - margin, margin),
        "bottom-left": (margin, base_h - mark_h - margin),
        "bottom-right": (base_w - mark_w - margin, base_h - mark_h - margin),
        "center": ((base_w - mark_w) // 2, (base_h - mark_h) // 2),
    }
    return positions.get(position, positions["bottom-right"])


def _apply_watermark(image: Image.Image, watermark_path: str, position: str, opacity: int) -> Image.Image:
    with Image.open(watermark_path) as raw_watermark:
        watermark = raw_watermark.convert("RGBA")

    max_watermark_width = max(1, round(image.width * WATERMARK_MAX_WIDTH_RATIO))
    if watermark.width > max_watermark_width:
        scale = max_watermark_width / watermark.width
        watermark = watermark.resize(
            (max_watermark_width, max(1, round(watermark.height * scale))),
            Image.Resampling.LANCZOS,
        )

    # 알파 채널에 투명도 비율을 곱해 로고 자체 농도와 무관하게 opacity를 반영한다.
    alpha = watermark.split()[-1].point(lambda a: int(a * opacity / 100))
    watermark.putalpha(alpha)

    margin = max(8, round(image.width * WATERMARK_MARGIN_RATIO))
    x, y = _watermark_position_xy(position, image.size, watermark.size, margin)

    result = image.copy()
    result.paste(watermark, (x, y), watermark)
    return result


def process_image(
    input_path: str,
    output_path: str,
    target_width: int | None = None,
    quality: int = 85,
    watermark_path: str | None = None,
    watermark_position: str = "bottom-right",
    watermark_opacity: int = 50,
) -> str:
    """리사이즈(가로 폭 기준) + 압축 + 워터마크를 한 번에 처리해서 원본과 같은 포맷으로 저장한다."""
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

    with Image.open(src) as opened:
        original_format = opened.format or "PNG"
        image = opened.convert("RGBA")

        if target_width:
            image = _resize_to_width(image, target_width)

        if watermark_path:
            image = _apply_watermark(image, watermark_path, watermark_position, watermark_opacity)

        if original_format == "JPEG":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image_to_save = background
        else:
            image_to_save = image

        save_kwargs = {}
        if original_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = quality
        elif original_format == "PNG":
            save_kwargs["compress_level"] = _png_compress_level(quality)

        image_to_save.save(output_path, format=original_format, **save_kwargs)

    return output_path
