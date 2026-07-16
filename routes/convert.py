import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_AUDIO_BITRATES,
    ALLOWED_AUDIO_INPUT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    DEFAULT_AUDIO_BITRATE,
    DEFAULT_GIF_FPS,
    DEFAULT_GIF_WIDTH,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_CRF,
    DEFAULT_WATERMARK_OPACITY,
    DEFAULT_WATERMARK_POSITION,
    GIF_FPS_CHOICES,
    GIF_WIDTH_CHOICES,
    IMAGE_MAX_DIMENSION_CHOICES,
    MAX_GIF_DURATION_SECONDS,
    MAX_IMAGE_QUALITY,
    MAX_VIDEO_CRF,
    MAX_WATERMARK_OPACITY,
    MIN_IMAGE_QUALITY,
    MIN_VIDEO_CRF,
    MIN_WATERMARK_OPACITY,
    OUTPUT_FOLDER,
    PROCESS_WIDTH_CHOICES,
    UPLOAD_FOLDER,
    VIDEO_CODEC_CHOICES,
    VIDEO_MAX_WIDTH_CHOICES,
    WATERMARK_POSITION_CHOICES,
)
from converters.audio_converter import convert_audio
from converters.ffmpeg_setup import install_ffmpeg, is_ffmpeg_available
from converters.file_type import detect_file_type
from converters.gif_converter import convert_gif_to_video, convert_video_segment_to_gif
from converters.history import add_record, get_recent_records
from converters.image_converter import convert_image
from converters.image_processor import process_image
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
    size_choice = request.form.get("max_dimension", "original").strip().lower()
    quality_raw = request.form.get("quality", str(DEFAULT_IMAGE_QUALITY)).strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 이미지 형식입니다: .{extension}"}), 400

    if target_format not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 목표 포맷입니다: {target_format}"}), 400

    if size_choice not in IMAGE_MAX_DIMENSION_CHOICES:
        return jsonify({"error": f"지원하지 않는 크기 옵션입니다: {size_choice}"}), 400

    try:
        quality = int(quality_raw)
    except ValueError:
        return jsonify({"error": f"품질 값이 올바르지 않습니다: {quality_raw}"}), 400

    if not (MIN_IMAGE_QUALITY <= quality <= MAX_IMAGE_QUALITY):
        return jsonify({"error": f"품질은 {MIN_IMAGE_QUALITY}~{MAX_IMAGE_QUALITY} 사이여야 합니다."}), 400

    max_dimension = None if size_choice == "original" else int(size_choice)

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "image"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_extension = "jpg" if target_format == "jpeg" else target_format
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}.{output_extension}"
        convert_image(str(input_path), target_format, str(output_path), max_dimension, quality)
        add_record(original_name, extension, output_extension)
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
    resolution_choice = request.form.get("resolution", "original").strip().lower()
    codec = request.form.get("codec", DEFAULT_VIDEO_CODEC).strip().lower()
    crf_raw = request.form.get("crf", str(DEFAULT_VIDEO_CRF)).strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 영상 형식입니다: .{extension}"}), 400

    if target_format not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 목표 포맷입니다: {target_format}"}), 400

    if resolution_choice not in VIDEO_MAX_WIDTH_CHOICES:
        return jsonify({"error": f"지원하지 않는 해상도 옵션입니다: {resolution_choice}"}), 400

    if codec not in VIDEO_CODEC_CHOICES:
        return jsonify({"error": f"지원하지 않는 코덱입니다: {codec}"}), 400

    try:
        crf = int(crf_raw)
    except ValueError:
        return jsonify({"error": f"화질(CRF) 값이 올바르지 않습니다: {crf_raw}"}), 400

    if not (MIN_VIDEO_CRF <= crf <= MAX_VIDEO_CRF):
        return jsonify({"error": f"화질(CRF)은 {MIN_VIDEO_CRF}~{MAX_VIDEO_CRF} 사이여야 합니다."}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    max_width = None if resolution_choice == "original" else int(resolution_choice)

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "video"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}.{target_format}"
        convert_video(str(input_path), target_format, str(output_path), max_width, codec, crf)
        add_record(original_name, extension, target_format)
    except Exception as error:
        return jsonify({"error": f"변환에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}.{target_format}"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/convert/audio")
def convert_audio_route():
    uploaded_file = request.files.get("file")
    bitrate = request.form.get("bitrate", DEFAULT_AUDIO_BITRATE).strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_AUDIO_INPUT_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 형식입니다: .{extension}"}), 400

    if bitrate not in ALLOWED_AUDIO_BITRATES:
        return jsonify({"error": f"지원하지 않는 음질입니다: {bitrate}"}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "audio"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}.mp3"
        convert_audio(str(input_path), str(output_path), bitrate)
        add_record(original_name, extension, "mp3")
    except Exception as error:
        return jsonify({"error": f"변환에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}.mp3"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.get("/api/history")
def history_route():
    return jsonify({"records": get_recent_records()})


@convert_bp.post("/api/process/image")
def process_image_route():
    uploaded_file = request.files.get("file")
    watermark_file = request.files.get("watermark")
    width_choice = request.form.get("width", "original").strip().lower()
    quality_raw = request.form.get("quality", str(DEFAULT_IMAGE_QUALITY)).strip()
    position = request.form.get("position", DEFAULT_WATERMARK_POSITION).strip().lower()
    opacity_raw = request.form.get("opacity", str(DEFAULT_WATERMARK_OPACITY)).strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 이미지 형식입니다: .{extension}"}), 400

    if width_choice not in PROCESS_WIDTH_CHOICES:
        return jsonify({"error": f"지원하지 않는 크기 옵션입니다: {width_choice}"}), 400

    try:
        quality = int(quality_raw)
    except ValueError:
        return jsonify({"error": f"품질 값이 올바르지 않습니다: {quality_raw}"}), 400

    if not (MIN_IMAGE_QUALITY <= quality <= MAX_IMAGE_QUALITY):
        return jsonify({"error": f"품질은 {MIN_IMAGE_QUALITY}~{MAX_IMAGE_QUALITY} 사이여야 합니다."}), 400

    if position not in WATERMARK_POSITION_CHOICES:
        return jsonify({"error": f"지원하지 않는 워터마크 위치입니다: {position}"}), 400

    try:
        opacity = int(opacity_raw)
    except ValueError:
        return jsonify({"error": f"투명도 값이 올바르지 않습니다: {opacity_raw}"}), 400

    if not (MIN_WATERMARK_OPACITY <= opacity <= MAX_WATERMARK_OPACITY):
        return jsonify({"error": f"투명도는 {MIN_WATERMARK_OPACITY}~{MAX_WATERMARK_OPACITY} 사이여야 합니다."}), 400

    if watermark_file is not None and watermark_file.filename:
        watermark_extension = _extension_of(secure_filename(watermark_file.filename))
        if watermark_extension not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"error": f"워터마크 이미지 형식을 지원하지 않습니다: .{watermark_extension}"}), 400

    target_width = None if width_choice == "original" else int(width_choice)

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "image"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    watermark_path = None
    if watermark_file is not None and watermark_file.filename:
        watermark_name = secure_filename(watermark_file.filename)
        watermark_path = UPLOAD_FOLDER / f"{job_id}_wm_{watermark_name}"
        watermark_file.save(watermark_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_가공.{extension}"
        process_image(
            str(input_path),
            str(output_path),
            target_width,
            quality,
            str(watermark_path) if watermark_path else None,
            position,
            opacity,
        )
        add_record(original_name, extension, extension)
    except Exception as error:
        return jsonify({"error": f"가공에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)
        if watermark_path:
            watermark_path.unlink(missing_ok=True)

    download_name = f"{stem}_가공.{extension}"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/convert/gif-from-video")
def gif_from_video_route():
    uploaded_file = request.files.get("file")
    start_raw = request.form.get("start", "0").strip()
    duration_raw = request.form.get("duration", "3").strip()
    width_choice = request.form.get("width", str(DEFAULT_GIF_WIDTH)).strip()
    fps_choice = request.form.get("fps", str(DEFAULT_GIF_FPS)).strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 영상 형식입니다: .{extension}"}), 400

    try:
        start_seconds = float(start_raw)
        duration_seconds = float(duration_raw)
    except ValueError:
        return jsonify({"error": "시작 시간/길이 값이 올바르지 않습니다."}), 400

    if start_seconds < 0:
        return jsonify({"error": "시작 시간은 0 이상이어야 합니다."}), 400

    if not (0 < duration_seconds <= MAX_GIF_DURATION_SECONDS):
        return jsonify({"error": f"길이는 0보다 크고 {MAX_GIF_DURATION_SECONDS}초 이하여야 합니다."}), 400

    if width_choice not in GIF_WIDTH_CHOICES:
        return jsonify({"error": f"지원하지 않는 크기 옵션입니다: {width_choice}"}), 400

    if fps_choice not in GIF_FPS_CHOICES:
        return jsonify({"error": f"지원하지 않는 프레임 옵션입니다: {fps_choice}"}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "video"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}.gif"
        convert_video_segment_to_gif(
            str(input_path), str(output_path), start_seconds, duration_seconds, int(width_choice), int(fps_choice)
        )
        add_record(original_name, extension, "gif")
    except Exception as error:
        return jsonify({"error": f"변환에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}.gif"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/convert/video-from-gif")
def video_from_gif_route():
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension != "gif":
        return jsonify({"error": f"GIF 파일만 지원합니다: .{extension}"}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "gif"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}.mp4"
        convert_gif_to_video(str(input_path), str(output_path))
        add_record(original_name, "gif", "mp4")
    except Exception as error:
        return jsonify({"error": f"변환에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}.mp4"
    return send_file(output_path, as_attachment=True, download_name=download_name)
