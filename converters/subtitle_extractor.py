import re
import subprocess
from pathlib import Path

from faster_whisper import WhisperModel

from converters.ffmpeg_setup import get_ffmpeg_path

# small 모델: base보다 언어 판별과 인식 정확도가 눈에 띄게 좋으면서도 CPU에서 충분히 빠르다.
MODEL_SIZE = "small"

_HANGUL_PATTERN = re.compile(r"[가-힣]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def _extract_audio_to_wav(input_path: str, wav_path: str) -> None:
    """Whisper가 바로 읽을 수 있도록 16kHz 모노 WAV로 오디오만 뽑아둔다."""
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise RuntimeError("FFmpeg가 설치되어 있지 않습니다.")

    command = [
        ffmpeg_path, "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        "-vn", wav_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not Path(wav_path).exists():
        raise RuntimeError((result.stderr or "").strip()[-500:] or "오디오 추출에 실패했습니다.")


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _guess_language_from_text(text: str, fallback: str, fallback_probability: float) -> tuple[str, float]:
    """Whisper의 언어 판별 필드는 짧은 클립에서 가끔 틀리길래, 실제로 받아 적힌 글자로 한 번 더 확인한다."""
    hangul_count = len(_HANGUL_PATTERN.findall(text))
    latin_count = len(_LATIN_PATTERN.findall(text))

    if hangul_count == 0 and latin_count == 0:
        return fallback, fallback_probability
    if hangul_count >= latin_count:
        return "ko", 1.0
    return "en", 1.0


def extract_subtitles(input_path: str, srt_output_path: str, txt_output_path: str) -> dict:
    """영상/오디오의 말소리를 받아 적어 SRT(타임코드 포함)와 TXT(순수 텍스트) 두 파일로 저장한다.

    Returns:
        {"language": 감지된 언어 코드(예: "ko", "en"), "language_probability": 확신도(0~1)}
    """
    src = Path(input_path)
    wav_path = str(src.with_name(f"{src.stem}_whisper_temp.wav"))

    try:
        _extract_audio_to_wav(input_path, wav_path)

        model = _get_model()
        # language=None -> 한국어/영어 등 언어를 자동으로 판별한다.
        segments, info = model.transcribe(wav_path, task="transcribe", language=None, vad_filter=True)

        srt_blocks = []
        txt_lines = []
        index = 0

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            index += 1
            start = _format_srt_timestamp(segment.start)
            end = _format_srt_timestamp(segment.end)
            srt_blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
            txt_lines.append(text)

        Path(srt_output_path).write_text("\n".join(srt_blocks), encoding="utf-8")
        Path(txt_output_path).write_text("\n".join(txt_lines), encoding="utf-8")

        full_text = " ".join(txt_lines)
        language, language_probability = _guess_language_from_text(
            full_text, info.language, info.language_probability
        )
        return {"language": language, "language_probability": language_probability}
    finally:
        Path(wav_path).unlink(missing_ok=True)
