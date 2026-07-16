import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from config import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_VIDEO_EXTENSIONS, OUTPUT_FOLDER, UPLOAD_FOLDER
from converters.ffmpeg_setup import install_ffmpeg, is_ffmpeg_available
from converters.file_type import detect_file_type
from converters.image_converter import convert_image
from converters.video_converter import convert_video

convert_bp = Blueprint("convert", __name__)


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@convert_bp.post("/api/detect")
def detect_route():
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    header = uploaded_file.stream.read(32)
    original_name = secure_filename(uploaded_file.filename)
    result = detect_file_type(header, original_name)
    result["filename"] = original_name
    return jsonify(result)


@convert_bp.post("/api/convert/image")
def convert_image_route():
    uploaded_file = request.files.get("file")
    target_format = request.form.get("format", "").strip().lower()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 이미지 형식입니다: .{extension}"}), 400

    if target_format not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 목표 포맷입니다: {target_format}"}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "image"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_extension = "jpg" if target_format == "jpeg" else target_format
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}.{output_extension}"
        convert_image(str(input_path), target_format, str(output_path))
    except Exception as error:
        return jsonify({"error": f"변환에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}.{output_extension}"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.get("/api/ffmpeg/status")
def ffmpeg_status_route():
    return jsonify({"available": is_ffmpeg_available()})


@convert_bp.post("/api/ffmpeg/install")
def ffmpeg_install_route():
    result = install_ffmpeg()
    return jsonify(result), (200 if result["success"] else 500)


@convert_bp.post("/api/convert/video")
def convert_video_route():
    uploaded_file = request.files.get("file")
    target_format = request.form.get("format", "").strip().lower()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 영상 형식입니다: .{extension}"}), 400

    if target_format not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 목표 포맷입니다: {target_format}"}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "video"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}.{target_format}"
        convert_video(str(input_path), target_format, str(output_path))
    except Exception as error:
        return jsonify({"error": f"변환에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}.{target_format}"
    return send_file(output_path, as_attachment=True, download_name=download_name)
