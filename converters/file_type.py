"""확장자와 매직 넘버(파일 내용의 시작 바이트)를 함께 봐서 파일 종류를 추정한다."""

CANONICAL_IMAGE_FORMATS = ["jpg", "png", "webp", "bmp", "gif", "tiff"]
CANONICAL_VIDEO_FORMATS = ["mp4", "mov"]

# 오디오는 지금 MP3로만 변환할 수 있어서, 목표 포맷은 항상 mp3 하나뿐이다.
# (mp3/wav/m4a 모두 "입력"으로는 받되, "출력"은 mp3만 지원한다는 뜻.)
CANONICAL_AUDIO_FORMATS = ["mp3"]
AUDIO_INPUT_FORMATS = ["mp3", "wav", "m4a"]

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
    """MP4/MOV/M4A는 모두 'ftyp' 박스로 시작하는 ISO 기반 미디어 컨테이너라, brand 값으로 구분한다."""
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return header[8:12].decode("ascii", errors="ignore").strip()
    return None


# ftyp 박스를 쓰는 컨테이너들. brand가 더 구체적인 것부터 먼저 확인해야
# M4A(오디오)가 MP4(영상)로 잘못 분류되지 않는다.
FTYP_SIGNATURES = [
    ("mov", "video", lambda h: _ftyp_brand(h) == "qt"),
    ("m4a", "audio", lambda h: _ftyp_brand(h) in ("M4A", "M4B")),
    ("mp4", "video", lambda h: _ftyp_brand(h) is not None),
]

AUDIO_SIGNATURES = [
    ("wav", lambda h: h.startswith(b"RIFF") and h[8:12] == b"WAVE"),
    ("mp3", lambda h: h.startswith(b"ID3") or h[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")),
]

# 아직 변환 기능은 없지만, "이 파일은 이런 종류예요"라고 안내하기 위한 시그니처.
OTHER_SIGNATURES = [
    ("pdf", "document", lambda h: h.startswith(b"%PDF")),
    ("webm", "video", lambda h: h.startswith(b"\x1a\x45\xdf\xa3")),
    ("avi", "video", lambda h: h.startswith(b"RIFF") and h[8:12] == b"AVI "),
]


def _normalize_extension(extension: str) -> str:
    return "jpg" if extension == "jpeg" else extension


def _recommend_targets(canonical_formats: list[str], detected_format: str) -> list[str]:
    return [fmt for fmt in canonical_formats if fmt != detected_format]


def _supported_result(category: str, fmt: str, extension: str, canonical_formats: list[str]) -> dict:
    return {
        "category": category,
        "detected_format": fmt,
        "extension": extension,
        "supported": True,
        "content_verified": True,
        "extension_mismatch": bool(extension) and extension != fmt,
        "recommended_formats": _recommend_targets(canonical_formats, fmt),
    }


def detect_file_type(header: bytes, filename: str) -> dict:
    """파일의 앞부분 바이트(header)와 파일명을 보고 종류를 추정한다.

    Returns:
        category: "image" | "video" | "audio" | "document" | "unknown"
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
            return _supported_result("image", fmt, extension, CANONICAL_IMAGE_FORMATS)

    for fmt, category, matcher in FTYP_SIGNATURES:
        if matcher(header):
            canonical = CANONICAL_VIDEO_FORMATS if category == "video" else CANONICAL_AUDIO_FORMATS
            return _supported_result(category, fmt, extension, canonical)

    for fmt, matcher in AUDIO_SIGNATURES:
        if matcher(header):
            return _supported_result("audio", fmt, extension, CANONICAL_AUDIO_FORMATS)

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

    if extension in AUDIO_INPUT_FORMATS:
        return {
            "category": "audio",
            "detected_format": extension,
            "extension": extension,
            "supported": True,
            "content_verified": False,
            "extension_mismatch": False,
            "recommended_formats": _recommend_targets(CANONICAL_AUDIO_FORMATS, extension),
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
