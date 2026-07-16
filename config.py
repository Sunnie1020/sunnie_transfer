from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"

# 이미지 변환에서 허용하는 입력 확장자.
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}

# 업로드 최대 용량 (bytes). 너무 큰 파일이 서버를 막지 않도록 제한한다.
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
