import io
import zipfile
from pathlib import Path

from PIL import Image

# PPTX/DOCX/XLSX는 내부적으로 zip 구조라, 이미지만 다운샘플·재압축하고
# XML/관계 파일 등 나머지는 그대로 복사해서 문서 구조를 깨지 않는다.
COMPRESSION_PRESETS = {
    "screen": {"max_dimension": 800, "quality": 60},
    "ebook": {"max_dimension": 1200, "quality": 75},
    "print": {"max_dimension": 1920, "quality": 85},
}

RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}


def _recompress_image_bytes(data: bytes, extension: str, max_dimension: int, quality: int) -> bytes:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception:
        return data

    longest_side = max(image.size)
    if longest_side > max_dimension:
        scale = max_dimension / longest_side
        new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    if extension in (".jpg", ".jpeg"):
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=quality)
    elif extension == ".png":
        image.save(buffer, format="PNG", optimize=True)
    elif extension == ".bmp":
        image.save(buffer, format="BMP")
    elif extension == ".tiff":
        image.save(buffer, format="TIFF")
    elif extension == ".gif":
        image.save(buffer, format="GIF")
    else:
        return data

    new_bytes = buffer.getvalue()
    return new_bytes if len(new_bytes) < len(data) else data


def compress_office_document(input_path: str, output_path: str, preset: str = "ebook") -> str:
    """DOCX/PPTX/XLSX 안의 이미지만 재압축한다. 문서 구조(XML/관계 파일)는 그대로 복사해 손대지 않는다."""
    settings = COMPRESSION_PRESETS.get(preset, COMPRESSION_PRESETS["ebook"])
    max_dimension = settings["max_dimension"]
    quality = settings["quality"]

    with zipfile.ZipFile(input_path, "r") as source_zip:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target_zip:
            for item in source_zip.infolist():
                data = source_zip.read(item.filename)
                extension = Path(item.filename).suffix.lower()

                if "/media/" in item.filename.lower() and extension in RASTER_EXTENSIONS:
                    data = _recompress_image_bytes(data, extension, max_dimension, quality)

                target_zip.writestr(item, data)

    return output_path
