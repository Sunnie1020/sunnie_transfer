import re
import subprocess
from pathlib import Path
from typing import Callable

from faster_whisper import WhisperModel

from config import HF_TOKEN
from converters.ffmpeg_setup import get_ffmpeg_path

# small 모델: base보다 언어 판별과 인식 정확도가 눈에 띄게 좋으면서도 CPU에서 충분히 빠르다.
MODEL_SIZE = "small"
DIARIZATION_MODEL_ID = "pyannote/speaker-diarization-3.1"

_HANGUL_PATTERN = re.compile(r"[가-힣]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")

_model: WhisperModel | None = None
_diarization_pipeline = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def _get_diarization_pipeline():
    global _diarization_pipeline
    if _diarization_pipeline is None:
        from pyannote.audio import Pipeline

        _diarization_pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL_ID, use_auth_token=HF_TOKEN)
    return _diarization_pipeline


def _diarize_speakers(wav_path: str) -> list[tuple[float, float, str]]:
    """오디오에서 화자 구간을 뽑는다. [(시작초, 끝초, 원본 화자 라벨), ...] 시간순으로 반환한다."""
    pipeline = _get_diarization_pipeline()
    diarization = pipeline(wav_path)

    turns = [(turn.start, turn.end, speaker) for turn, _, speaker in diarization.itertracks(yield_label=True)]
    turns.sort(key=lambda item: item[0])
    return turns


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


def _speaker_prefix_builder():
    """화자 구간(turns)과 구간이 겹치는 세그먼트에 "화자1: " 같은 접두어를 붙여주는 함수를 만든다.

    화자 라벨은 등장한 순서대로 화자1, 화자2, ...로 번호를 매긴다.
    """
    speaker_numbers: dict[str, int] = {}

    def assign(turns: list[tuple[float, float, str]], seg_start: float, seg_end: float) -> str:
        best_label = None
        best_overlap = 0.0
        for turn_start, turn_end, label in turns:
            overlap = min(seg_end, turn_end) - max(seg_start, turn_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = label

        if best_label is None:
            return ""

        if best_label not in speaker_numbers:
            speaker_numbers[best_label] = len(speaker_numbers) + 1

        return f"화자{speaker_numbers[best_label]}: "

    return assign


def extract_subtitles(
    input_path: str,
    srt_output_path: str,
    txt_output_path: str,
    on_progress: Callable[[float], None] | None = None,
) -> dict:
    """영상/오디오의 말소리를 받아 적어 SRT(타임코드 포함)와 TXT(순수 텍스트) 두 파일로 저장한다.

    HF_TOKEN이 설정되어 있으면 화자를 구분해서 "화자1: ", "화자2: " 접두어를 붙인다.
    토큰이 없으면 화자 구분 없이 기존처럼 자막만 뽑는다.

    Returns:
        {"language": 감지된 언어 코드, "language_probability": 확신도(0~1), "diarization_enabled": 화자 구분 적용 여부}
    """
    src = Path(input_path)
    wav_path = str(src.with_name(f"{src.stem}_whisper_temp.wav"))

    try:
        _extract_audio_to_wav(input_path, wav_path)
        if on_progress:
            on_progress(5)

        diarization_turns: list[tuple[float, float, str]] = []
        if HF_TOKEN:
            diarization_turns = _diarize_speakers(wav_path)
            if on_progress:
                on_progress(30)

        transcribe_start_percent = 30 if diarization_turns else 5

        model = _get_model()
        # language=None -> 한국어/영어 등 언어를 자동으로 판별한다.
        segments, info = model.transcribe(wav_path, task="transcribe", language=None, vad_filter=True)

        assign_speaker_prefix = _speaker_prefix_builder()
        srt_blocks = []
        txt_lines = []
        index = 0

        for segment in segments:
            if on_progress and info.duration > 0:
                progress_span = 100 - transcribe_start_percent
                on_progress(min(99, transcribe_start_percent + round(segment.end / info.duration * progress_span)))

            text = segment.text.strip()
            if not text:
                continue
            index += 1

            prefix = assign_speaker_prefix(diarization_turns, segment.start, segment.end) if diarization_turns else ""
            labeled_text = f"{prefix}{text}"

            start = _format_srt_timestamp(segment.start)
            end = _format_srt_timestamp(segment.end)
            srt_blocks.append(f"{index}\n{start} --> {end}\n{labeled_text}\n")
            txt_lines.append(labeled_text)

        Path(srt_output_path).write_text("\n".join(srt_blocks), encoding="utf-8")
        Path(txt_output_path).write_text("\n".join(txt_lines), encoding="utf-8")

        full_text = " ".join(txt_lines)
        language, language_probability = _guess_language_from_text(
            full_text, info.language, info.language_probability
        )
        if on_progress:
            on_progress(100)
        return {
            "language": language,
            "language_probability": language_probability,
            "diarization_enabled": bool(diarization_turns),
        }
    finally:
        Path(wav_path).unlink(missing_ok=True)
