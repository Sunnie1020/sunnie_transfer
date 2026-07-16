import io

import fitz
from PIL import Image

# 화면용: 가장 많이 줄임. 전자책: 적당히. 인쇄용: 화질을 최대한 지켜서 조금만 줄임.
COMPRESSION_PRESETS = {
    "screen": {"max_dimension": 1000, "quality": 60},
    "ebook": {"max_dimension": 1500, "quality": 75},
    "print": {"max_dimension": 2000, "quality": 85},
}


def compress_pdf(input_path: str, output_path: str, preset: str = "ebook") -> str:
    """PDF 안에 박힌 이미지만 다운샘플·재압축한다. 글자는 벡터 그대로라 손대지 않는다."""
    settings = COMPRESSION_PRESETS.get(preset, COMPRESSION_PRESETS["ebook"])
    max_dimension = settings["max_dimension"]
    quality = settings["quality"]

    document = fitz.open(input_path)
    processed_xrefs = set()

    try:
        for page in document:
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                if xref in processed_xrefs:
                    continue
                processed_xrefs.add(xref)

                try:
                    extracted = document.extract_image(xref)
                except Exception:
                    continue

                original_bytes = extracted["image"]

                try:
                    pil_image = Image.open(io.BytesIO(original_bytes))
                    pil_image.load()
                except Exception:
                    continue

                if pil_image.mode in ("RGBA", "LA", "P"):
                    rgba = pil_image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, (255, 255, 255))
                    background.paste(rgba, mask=rgba.split()[-1])
                    pil_image = background
                elif pil_image.mode != "RGB":
                    pil_image = pil_image.convert("RGB")

                longest_side = max(pil_image.size)
                if longest_side > max_dimension:
                    scale = max_dimension / longest_side
                    new_size = (
                        max(1, round(pil_image.width * scale)),
                        max(1, round(pil_image.height * scale)),
                    )
                    pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                pil_image.save(buffer, format="JPEG", quality=quality)
                new_bytes = buffer.getvalue()

                # 재압축 결과가 오히려 더 크면(이미 작은 이미지 등) 원본을 그대로 둔다.
                if len(new_bytes) >= len(original_bytes):
                    continue

                try:
                    page.replace_image(xref, stream=new_bytes)
                except Exception:
                    continue

        document.save(output_path, garbage=4, deflate=True)
    finally:
        document.close()

    return output_path
