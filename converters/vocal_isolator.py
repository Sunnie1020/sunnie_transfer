import shutil
import subprocess
import sys
from pathlib import Path

from converters.ffmpeg_setup import get_ffmpeg_path

MODEL_NAME = "htdemucs"


def remove_instrumental(input_path: str, output_path: str) -> str:
    """Demucs(AI 모델)로 보컬과 반주(MR)를 분리해서, 보컬만 남긴 오디오를 MP3로 저장한다."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    work_dir = Path(input_path).with_name(f"{Path(input_path).stem}_demucs_temp")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        command = [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-n", MODEL_NAME,
            "-d", "cpu",
            "-o", str(work_dir),
            input_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "").strip()[-500:] or "MR 제거에 실패했습니다.")

        stem = Path(input_path).stem
        vocals_path = work_dir / MODEL_NAME / stem / "vocals.wav"
        if not vocals_path.exists():
            raise RuntimeError("보컬 분리 결과를 찾지 못했습니다.")

        convert_command = [
            ffmpeg_path, "-y", "-i", str(vocals_path),
            "-c:a", "libmp3lame", "-b:a", "192k",
            output_path,
        ]
        convert_result = subprocess.run(
            convert_command, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if convert_result.returncode != 0 or not Path(output_path).exists():
            raise RuntimeError((convert_result.stderr or "").strip()[-500:] or "오디오 변환에 실패했습니다.")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return output_path
