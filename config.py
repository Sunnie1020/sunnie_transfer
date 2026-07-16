from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"
SHARE_FOLDER = BASE_DIR / "shares"
HISTORY_DB_PATH = BASE_DIR / "history.db"

# 서버가 실제로 뜨는 포트. QR 공유 링크를 만들 때도 이 값을 그대로 쓴다.
APP_PORT = 1020

# QR 공유 링크가 자동으로 만료되기까지의 시간(분).
SHARE_EXPIRY_MINUTES = 20

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

# 이미지 변환 옵션: 크기(긴 변 기준 최대 픽셀)와 품질.
IMAGE_MAX_DIMENSION_CHOICES = {"original", "1920", "1280", "800"}
DEFAULT_IMAGE_QUALITY = 85
MIN_IMAGE_QUALITY = 1
MAX_IMAGE_QUALITY = 100

# 영상 변환 옵션: 해상도(가로 기준 최대 픽셀), 코덱, 화질(CRF).
VIDEO_MAX_WIDTH_CHOICES = {"original", "1920", "1280", "854"}
VIDEO_CODEC_CHOICES = {"h264", "h265"}
DEFAULT_VIDEO_CODEC = "h264"
DEFAULT_VIDEO_CRF = 23
MIN_VIDEO_CRF = 0
MAX_VIDEO_CRF = 51

# 이미지 가공(리사이즈/압축/워터마크) 옵션.
PROCESS_WIDTH_CHOICES = {"original", "1920", "1280", "800", "500"}
WATERMARK_POSITION_CHOICES = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}
DEFAULT_WATERMARK_POSITION = "bottom-right"
MIN_WATERMARK_OPACITY = 1
MAX_WATERMARK_OPACITY = 100
DEFAULT_WATERMARK_OPACITY = 50

# 움짤(GIF) 옵션: 영상 구간 -> GIF, GIF -> 영상.
GIF_WIDTH_CHOICES = {"320", "480", "640"}
DEFAULT_GIF_WIDTH = 480
GIF_FPS_CHOICES = {"5", "10", "15"}
DEFAULT_GIF_FPS = 10
MAX_GIF_DURATION_SECONDS = 30

# 문서 도구: PDF <-> 이미지.
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf"}
PDF_TO_IMAGE_DPI_CHOICES = {"100", "150", "200"}
DEFAULT_PDF_TO_IMAGE_DPI = "150"

# PDF 압축 강도 (화면용/전자책/인쇄용).
PDF_COMPRESSION_PRESET_CHOICES = {"screen", "ebook", "print"}
DEFAULT_PDF_COMPRESSION_PRESET = "ebook"

# 오피스 문서(PPTX/DOCX/XLSX) 압축.
ALLOWED_OFFICE_EXTENSIONS = {"docx", "pptx", "xlsx"}
OFFICE_COMPRESSION_PRESET_CHOICES = {"screen", "ebook", "print"}
DEFAULT_OFFICE_COMPRESSION_PRESET = "ebook"

# 만능 압축: 목표 용량(MB)을 입력하면 그 이하가 되도록 자동으로 맞춘다.
UNIVERSAL_COMPRESS_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS
MIN_TARGET_SIZE_MB = 0.05
MAX_TARGET_SIZE_MB = 2000
DEFAULT_TARGET_SIZE_MB = 8

# 업로드 최대 용량 (bytes). 영상 파일을 고려해 넉넉하게 잡는다.
MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB
