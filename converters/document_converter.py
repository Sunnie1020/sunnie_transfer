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


def merge_pdfs(pdf_paths: list[str], output_path: str) -> str:
    """여러 PDF를 (전달된 순서 그대로) 한 권으로 합친다."""
    if not pdf_paths:
        raise ValueError("PDF가 전달되지 않았습니다.")

    merged = fitz.open()
    try:
        for path in pdf_paths:
            document = fitz.open(path)
            try:
                merged.insert_pdf(document)
            finally:
                document.close()
        merged.save(output_path)
    finally:
        merged.close()

    return output_path


def split_pdf_to_zip(pdf_path: str, output_zip_path: str) -> str:
    """PDF를 페이지별 개별 PDF로 나눠 zip 하나로 묶는다."""
    document = fitz.open(pdf_path)

    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for index in range(document.page_count):
                single_page = fitz.open()
                single_page.insert_pdf(document, from_page=index, to_page=index)
                archive.writestr(f"page_{index + 1:03d}.pdf", single_page.write())
                single_page.close()
    finally:
        document.close()

    if Path(output_zip_path).stat().st_size == 0:
        raise RuntimeError("PDF에서 페이지를 찾지 못했습니다.")

    return output_zip_path


def extract_images_zip(pdf_path: str, output_zip_path: str) -> str:
    """PDF에 박힌 이미지를 원본 그대로 뽑아 zip 하나로 묶는다."""
    document = fitz.open(pdf_path)
    processed_xrefs = set()
    image_count = 0

    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for page in document:
                for image_info in page.get_images(full=True):
                    xref = image_info[0]
                    if xref in processed_xrefs:
                        continue
                    processed_xrefs.add(xref)

                    extracted = document.extract_image(xref)
                    image_count += 1
                    archive.writestr(f"image_{image_count:03d}.{extracted['ext']}", extracted["image"])
    finally:
        document.close()

    if image_count == 0:
        raise RuntimeError("PDF에서 이미지를 찾지 못했습니다.")

    return output_zip_path
