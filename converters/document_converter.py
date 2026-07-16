import io
import zipfile
from pathlib import Path

import fitz
from PIL import Image


def images_to_pdf(image_paths: list[str], output_path: str) -> str:
    """여러 이미지를 (전달된 순서 그대로) PDF 한 권으로 묶는다."""
    if not image_paths:
        raise ValueError("이미지가 전달되지 않았습니다.")

    pages = []
    try:
        for path in image_paths:
            opened = Image.open(path)
            opened.load()

            if opened.mode in ("RGBA", "LA", "P"):
                rgba = opened.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[-1])
                page = background
            elif opened.mode != "RGB":
                page = opened.convert("RGB")
            else:
                page = opened.copy()

            pages.append(page)

        first_page, rest_pages = pages[0], pages[1:]
        first_page.save(output_path, format="PDF", save_all=True, append_images=rest_pages)
    finally:
        for page in pages:
            page.close()

    return output_path


def pdf_to_images_zip(pdf_path: str, output_zip_path: str, dpi: int = 150) -> str:
    """PDF의 각 페이지를 JPG로 뽑아 zip 하나로 묶는다."""
    document = fitz.open(pdf_path)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=matrix)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=90)
                archive.writestr(f"page_{index:03d}.jpg", buffer.getvalue())
    finally:
        document.close()

    if Path(output_zip_path).stat().st_size == 0:
        raise RuntimeError("PDF에서 페이지를 찾지 못했습니다.")

    return output_zip_path
