"""확장자와 매직 넘버(파일 내용의 시작 바이트)를 함께 봐서 파일 종류를 추정한다."""

CANONICAL_IMAGE_FORMATS = ["jpg", "png", "webp", "bmp", "gif", "tiff"]
CANONICAL_VIDEO_FORMATS = ["mp4", "mov"]

# (포맷 이름, 헤더 바이트로 판별하는 함수)
IMAGE_SIGNATURES = [
    ("png", lambda h: h.startswith(b"\x89PNG\r\n\x1a\n")),
    ("jpg", lambda h: h.startswith(b"\xff\xd8\xff")),
    ("gif", lambda h: h.startswith(b"GIF87a") or h.startswith(b"GIF89a")),
    ("bmp", lambda h: h.startswith(b"BM")),
    ("webp", lambda h: h.startswith(b"RIFF") and h[8:12] == b"WEBP"),
    ("tiff", lambda h: h.startswith(b"II*\x00") or h.startswith(b"MM\x00*")),
]


def _ftyp_brand(header: bytes) -> str | None:
    """MP4/MOV는 둘 다 'ftyp' 박스로 시작하는 ISO 기반 미디어 컨테이너라, brand 값으로 구분한다."""
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return header[8:12].decode("ascii", errors="ignore").strip()
    return None


VIDEO_SIGNATURES = [
    ("mov", lambda h: _ftyp_brand(h) == "qt"),
    ("mp4", lambda h: _ftyp_brand(h) is not None),
]

# 아직 변환 기능은 없지만, "이 파일은 이런 종류예요"라고 안내하기 위한 시그니처.
OTHER_SIGNATURES = [
    ("pdf", "document", lambda h: h.startswith(b"%PDF")),
    ("webm", "video", lambda h: h.startswith(b"\x1a\x45\xdf\xa3")),
    ("avi", "video", lambda h: h.startswith(b"RIFF") and h[8:12] == b"AVI "),
    ("mp3", "audio", lambda h: h.startswith(b"ID3") or h[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")),
    ("wav", "audio", lambda h: h.startswith(b"RIFF") and h[8:12] == b"WAVE"),
]


def _normalize_extension(extension: str) -> str:
    return "jpg" if extension == "jpeg" else extension


def _recommend_targets(canonical_formats: list[str], detected_format: str) -> list[str]:
    return [fmt for fmt in canonical_formats if fmt != detected_format]


def detect_file_type(header: bytes, filename: str) -> dict:
    """파일의 앞부분 바이트(header)와 파일명을 보고 종류를 추정한다.

    Returns:
        category: "image" | "video" | "document" | "audio" | "unknown"
        detected_format: 추정된 실제 포맷 (예: "png"). 알 수 없으면 None.
        extension: 파일명에서 뽑은 확장자.
        supported: 지금 이 앱에서 변환 가능한 종류인지.
        content_verified: 매직 넘버로 실제 확인했는지, 확장자만으로 추측했는지.
        extension_mismatch: 확장자와 실제 내용이 다른지 (예: .jpg인데 실제로는 PNG).
        recommended_formats: 변환 가능한 목표 포맷 목록.
    """
    raw_extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    extension = _normalize_extension(raw_extension)

    for fmt, matcher in IMAGE_SIGNATURES:
        if matcher(header):
            return {
                "category": "image",
                "detected_format": fmt,
                "extension": extension,
                "supported": True,
                "content_verified": True,
                "extension_mismatch": bool(extension) and extension != fmt,
                "recommended_formats": _recommend_targets(CANONICAL_IMAGE_FORMATS, fmt),
            }

    for fmt, matcher in VIDEO_SIGNATURES:
        if matcher(header):
            return {
                "category": "video",
                "detected_format": fmt,
                "extension": extension,
                "supported": True,
                "content_verified": True,
                "extension_mismatch": bool(extension) and extension != fmt,
                "recommended_formats": _recommend_targets(CANONICAL_VIDEO_FORMATS, fmt),
            }

    for fmt, category, matcher in OTHER_SIGNATURES:
        if matcher(header):
            return {
                "category": category,
                "detected_format": fmt,
                "extension": extension,
                "supported": False,
                "content_verified": True,
                "extension_mismatch": bool(extension) and extension != fmt,
                "recommended_formats": [],
            }

    if extension in CANONICAL_IMAGE_FORMATS:
        return {
            "category": "image",
            "detected_format": extension,
            "extension": extension,
            "supported": True,
            "content_verified": False,
            "extension_mismatch": False,
            "recommended_formats": _recommend_targets(CANONICAL_IMAGE_FORMATS, extension),
        }

    if extension in CANONICAL_VIDEO_FORMATS:
        return {
            "category": "video",
            "detected_format": extension,
            "extension": extension,
            "supported": True,
            "content_verified": False,
            "extension_mismatch": False,
            "recommended_formats": _recommend_targets(CANONICAL_VIDEO_FORMATS, extension),
        }

    return {
        "category": "unknown",
        "detected_format": None,
        "extension": extension,
        "supported": False,
        "content_verified": False,
        "extension_mismatch": False,
        "recommended_formats": [],
    }
