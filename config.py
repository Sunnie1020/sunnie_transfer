from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"

# 이미지 변환에서 허용하는 입력 확장자.
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}

# 영상 변환에서 허용하는 입력 확장자.
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov"}

# 업로드 최대 용량 (bytes). 영상 파일을 고려해 넉넉하게 잡는다.
MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB
