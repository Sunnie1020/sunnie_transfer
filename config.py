from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"

# 이미지 변환에서 허용하는 입력 확장자.
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}

# 영상 변환에서 허용하는 입력 확장자.
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov"}

# 오디오 변환(MP3로)에서 허용하는 입력 확장자. 영상 파일에서 오디오만 추출하는 것도 지원한다.
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a"}
ALLOWED_AUDIO_INPUT_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

# MP3로 인코딩할 때 고를 수 있는 비트레이트.
ALLOWED_AUDIO_BITRATES = {"128k", "192k", "320k"}
DEFAULT_AUDIO_BITRATE = "192k"

# 업로드 최대 용량 (bytes). 영상 파일을 고려해 넉넉하게 잡는다.
MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB
