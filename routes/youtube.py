import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from config import OUTPUT_FOLDER, UPLOAD_FOLDER
from converters.ffmpeg_setup import is_ffmpeg_available
from converters.history import add_record
from converters.vocal_isolator import remove_instrumental
from converters.youtube_audio import download_youtube_audio

youtube_bp = Blueprint("youtube", __name__)


def _download_filename(title: str, suffix: str = "") -> str:
    safe = secure_filename(title) or "youtube_audio"
    return f"{safe}{suffix}.mp3"


@youtube_bp.post("/api/youtube/extract-audio")
def extract_audio_route():
    url = (request.form.get("url") or "").strip()

    if not url:
        return jsonify({"error": "유튜브 링크를 입력해주세요."}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex

    try:
        result = download_youtube_audio(url, str(OUTPUT_FOLDER), job_id)
        add_record(result["title"], "youtube", "mp3")
    except Exception as error:
        return jsonify({"error": f"오디오 추출에 실패했습니다: {error}"}), 500

    return send_file(result["path"], as_attachment=True, download_name=_download_filename(result["title"]))


@youtube_bp.post("/api/youtube/remove-mr")
def remove_mr_route():
    url = (request.form.get("url") or "").strip()

    if not url:
        return jsonify({"error": "유튜브 링크를 입력해주세요."}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex
    downloaded_path = None

    try:
        result = download_youtube_audio(url, str(UPLOAD_FOLDER), job_id)
        downloaded_path = result["path"]

        output_path = OUTPUT_FOLDER / f"{job_id}_보컬.mp3"
        remove_instrumental(downloaded_path, str(output_path))
        add_record(result["title"], "youtube", "mp3(mr제거)")
    except Exception as error:
        return jsonify({"error": f"MR 제거에 실패했습니다: {error}"}), 500
    finally:
        if downloaded_path:
            Path(downloaded_path).unlink(missing_ok=True)

    download_name = _download_filename(result["title"], "_보컬")
    return send_file(output_path, as_attachment=True, download_name=download_name)
