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


def convert_image(input_path: str, output_format: str, output_path: str | None = None) -> str:
    """이미지 파일을 읽어 지정한 포맷으로 변환해 저장한다.

    Args:
        input_path: 변환할 원본 이미지 경로.
        output_format: 목표 포맷 (예: "jpeg", "png", "webp"). 대소문자 무관.
        output_path: 저장 경로. 생략하면 원본과 같은 폴더에 확장자만 바꿔 저장한다.

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

        image_to_save.save(output_path, format=output_format)

    return output_path
