"""FFmpeg가 있는지 확인하고, 없으면 자동으로 설치를 시도한다."""

import platform
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VENDOR_DIR = BASE_DIR / "vendor" / "ffmpeg"

# 커뮤니티에서 널리 쓰이는 공식 정적 빌드 배포처 (Windows용).
WINDOWS_BUILD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def _bundled_ffmpeg_path() -> str | None:
    """자동 설치로 vendor 폴더에 내려받은 ffmpeg 실행 파일을 찾는다."""
    if not VENDOR_DIR.exists():
        return None
    exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    matches = list(VENDOR_DIR.rglob(exe_name))
    return str(matches[0]) if matches else None


def get_ffmpeg_path() -> str | None:
    """시스템에 설치된 ffmpeg 또는 자동 설치로 받아둔 ffmpeg 경로를 반환한다."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    return _bundled_ffmpeg_path()


def is_ffmpeg_available() -> bool:
    return get_ffmpeg_path() is not None


def install_ffmpeg() -> dict:
    system = platform.system()

    if system == "Windows":
        return _install_windows()
    if system == "Darwin":
        return _install_mac()

    return {
        "success": False,
        "message": "이 운영체제에서는 자동 설치를 지원하지 않습니다. FFmpeg를 직접 설치한 뒤 다시 시도해주세요.",
    }


def _install_windows() -> dict:
    try:
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = VENDOR_DIR / "ffmpeg.zip"
        urllib.request.urlretrieve(WINDOWS_BUILD_URL, zip_path)

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(VENDOR_DIR)
        zip_path.unlink(missing_ok=True)

        if is_ffmpeg_available():
            return {"success": True, "message": "FFmpeg 설치가 완료됐습니다."}
        return {
            "success": False,
            "message": "설치 파일은 받았지만 ffmpeg.exe를 찾지 못했습니다. 수동 설치를 시도해주세요.",
        }
    except Exception as error:
        return {"success": False, "message": f"자동 설치에 실패했습니다: {error}"}


def _install_mac() -> dict:
    if not shutil.which("brew"):
        return {
            "success": False,
            "message": (
                "Homebrew가 설치되어 있지 않습니다. "
                "https://brew.sh 에서 Homebrew를 설치한 뒤, "
                "터미널에서 'brew install ffmpeg'를 실행하고 다시 시도해주세요."
            ),
        }

    try:
        result = subprocess.run(
            ["brew", "install", "ffmpeg"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        if result.returncode == 0 and is_ffmpeg_available():
            return {"success": True, "message": "FFmpeg 설치가 완료됐습니다."}
        return {
            "success": False,
            "message": (result.stderr or "").strip()[-500:] or "brew install ffmpeg에 실패했습니다.",
        }
    except Exception as error:
        return {"success": False, "message": f"자동 설치에 실패했습니다: {error}"}
