import uuid
import zipfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_AUDIO_BITRATES,
    ALLOWED_AUDIO_INPUT_EXTENSIONS,
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_OFFICE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    DEFAULT_AUDIO_BITRATE,
    DEFAULT_GIF_FPS,
    DEFAULT_GIF_WIDTH,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_OFFICE_COMPRESSION_PRESET,
    DEFAULT_PDF_COMPRESSION_PRESET,
    DEFAULT_PDF_TO_IMAGE_DPI,
    DEFAULT_TARGET_SIZE_MB,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_CRF,
    DEFAULT_WATERMARK_OPACITY,
    DEFAULT_WATERMARK_POSITION,
    GIF_FPS_CHOICES,
    GIF_WIDTH_CHOICES,
    IMAGE_MAX_DIMENSION_CHOICES,
    MAX_GIF_DURATION_SECONDS,
    MAX_IMAGE_QUALITY,
    MAX_TARGET_SIZE_MB,
    MAX_VIDEO_CRF,
    MAX_WATERMARK_OPACITY,
    MIN_IMAGE_QUALITY,
    MIN_TARGET_SIZE_MB,
    MIN_VIDEO_CRF,
    MIN_WATERMARK_OPACITY,
    OFFICE_COMPRESSION_PRESET_CHOICES,
    OUTPUT_FOLDER,
    PDF_COMPRESSION_PRESET_CHOICES,
    PDF_TO_IMAGE_DPI_CHOICES,
    PROCESS_WIDTH_CHOICES,
    UNIVERSAL_COMPRESS_EXTENSIONS,
    UPLOAD_FOLDER,
    VIDEO_CODEC_CHOICES,
    VIDEO_MAX_WIDTH_CHOICES,
    WATERMARK_POSITION_CHOICES,
)
from converters.audio_converter import convert_audio
from converters.background_remover import remove_background
from converters.document_converter import (
    extract_images_zip,
    images_to_pdf,
    merge_pdfs,
    pdf_to_images_zip,
    split_pdf_to_zip,
)
from converters.ffmpeg_setup import install_ffmpeg, is_ffmpeg_available
from converters.file_type import detect_file_type
from converters.gif_converter import convert_gif_to_video, convert_video_segment_to_gif
from converters.history import add_record, get_recent_records, get_stats
from converters.image_converter import convert_image
from converters.image_processor import process_image
from converters.office_compressor import compress_office_document
from converters.pdf_compressor import compress_pdf
from converters.subtitle_extractor import extract_subtitles
from converters.universal_compressor import compress_image_to_target_size, compress_video_to_target_size
from converters.video_converter import convert_video, extract_thumbnail

convert_bp = Blueprint("convert", __name__)


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _parse_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in ("false", "0", "no")


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
    strip_metadata = _parse_bool(request.form.get("strip_metadata"), True)

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
        convert_image(str(input_path), target_format, str(output_path), max_dimension, quality, strip_metadata)
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
    strip_metadata = _parse_bool(request.form.get("strip_metadata"), True)

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
        convert_video(str(input_path), target_format, str(output_path), max_width, codec, crf, strip_metadata)
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


@convert_bp.get("/api/stats")
def stats_route():
    return jsonify(get_stats())


@convert_bp.post("/api/process/image")
def process_image_route():
    uploaded_file = request.files.get("file")
    watermark_file = request.files.get("watermark")
    width_choice = request.form.get("width", "original").strip().lower()
    quality_raw = request.form.get("quality", str(DEFAULT_IMAGE_QUALITY)).strip()
    position = request.form.get("position", DEFAULT_WATERMARK_POSITION).strip().lower()
    opacity_raw = request.form.get("opacity", str(DEFAULT_WATERMARK_OPACITY)).strip()
    strip_metadata = _parse_bool(request.form.get("strip_metadata"), True)

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
            strip_metadata,
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


@convert_bp.post("/api/document/images-to-pdf")
def images_to_pdf_route():
    uploaded_files = [f for f in request.files.getlist("files") if f and f.filename]

    if not uploaded_files:
        return jsonify({"error": "이미지가 전달되지 않았습니다."}), 400

    original_names = [secure_filename(f.filename) for f in uploaded_files]
    extensions = [_extension_of(name) for name in original_names]

    for extension in extensions:
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"error": f"지원하지 않는 이미지 형식입니다: .{extension}"}), 400

    job_id = uuid.uuid4().hex
    saved_paths = []

    for index, (uploaded_file, name) in enumerate(zip(uploaded_files, original_names)):
        input_path = UPLOAD_FOLDER / f"{job_id}_{index:03d}_{name}"
        uploaded_file.save(input_path)
        saved_paths.append(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_images.pdf"
        images_to_pdf([str(p) for p in saved_paths], str(output_path))
        add_record(f"이미지 {len(uploaded_files)}장", "image", "pdf")
    except Exception as error:
        return jsonify({"error": f"PDF로 묶는 데 실패했습니다: {error}"}), 500
    finally:
        for path in saved_paths:
            path.unlink(missing_ok=True)

    return send_file(output_path, as_attachment=True, download_name="images.pdf")


@convert_bp.post("/api/document/merge-pdfs")
def merge_pdfs_route():
    uploaded_files = [f for f in request.files.getlist("files") if f and f.filename]

    if not uploaded_files:
        return jsonify({"error": "PDF가 전달되지 않았습니다."}), 400

    original_names = [secure_filename(f.filename) for f in uploaded_files]
    extensions = [_extension_of(name) for name in original_names]

    for extension in extensions:
        if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            return jsonify({"error": f"PDF 파일만 지원합니다: .{extension}"}), 400

    job_id = uuid.uuid4().hex
    saved_paths = []

    for index, (uploaded_file, name) in enumerate(zip(uploaded_files, original_names)):
        input_path = UPLOAD_FOLDER / f"{job_id}_{index:03d}_{name}"
        uploaded_file.save(input_path)
        saved_paths.append(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_merged.pdf"
        merge_pdfs([str(p) for p in saved_paths], str(output_path))
        add_record(f"PDF {len(uploaded_files)}개", "pdf", "pdf(병합)")
    except Exception as error:
        return jsonify({"error": f"PDF 병합에 실패했습니다: {error}"}), 500
    finally:
        for path in saved_paths:
            path.unlink(missing_ok=True)

    return send_file(output_path, as_attachment=True, download_name="merged.pdf")


@convert_bp.post("/api/document/pdf-to-images")
def pdf_to_images_route():
    uploaded_file = request.files.get("file")
    dpi_choice = request.form.get("dpi", DEFAULT_PDF_TO_IMAGE_DPI).strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        return jsonify({"error": f"PDF 파일만 지원합니다: .{extension}"}), 400

    if dpi_choice not in PDF_TO_IMAGE_DPI_CHOICES:
        return jsonify({"error": f"지원하지 않는 화질 옵션입니다: {dpi_choice}"}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "document"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_pages.zip"
        pdf_to_images_zip(str(input_path), str(output_path), int(dpi_choice))
        add_record(original_name, "pdf", "jpg(zip)")
    except Exception as error:
        return jsonify({"error": f"이미지 추출에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_pages.zip"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/document/split-pdf")
def split_pdf_route():
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        return jsonify({"error": f"PDF 파일만 지원합니다: .{extension}"}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "document"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_pages.zip"
        split_pdf_to_zip(str(input_path), str(output_path))
        add_record(original_name, "pdf", "pdf(zip)")
    except Exception as error:
        return jsonify({"error": f"PDF 분할에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_pages.zip"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/document/extract-images")
def extract_images_route():
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        return jsonify({"error": f"PDF 파일만 지원합니다: .{extension}"}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "document"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_images.zip"
        extract_images_zip(str(input_path), str(output_path))
        add_record(original_name, "pdf", "img(zip)")
    except Exception as error:
        return jsonify({"error": f"이미지 추출에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_images.zip"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/document/video-thumbnail")
def video_thumbnail_route():
    uploaded_file = request.files.get("file")
    timestamp_raw = request.form.get("timestamp", "0").strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 영상 형식입니다: .{extension}"}), 400

    try:
        timestamp_seconds = float(timestamp_raw)
    except ValueError:
        return jsonify({"error": "시점 값이 올바르지 않습니다."}), 400

    if timestamp_seconds < 0:
        return jsonify({"error": "시점은 0 이상이어야 합니다."}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "video"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_thumb.jpg"
        extract_thumbnail(str(input_path), str(output_path), timestamp_seconds)
        add_record(original_name, extension, "jpg")
    except Exception as error:
        return jsonify({"error": f"썸네일 추출에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_thumb.jpg"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/compress/pdf")
def compress_pdf_route():
    uploaded_file = request.files.get("file")
    preset = request.form.get("preset", DEFAULT_PDF_COMPRESSION_PRESET).strip().lower()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        return jsonify({"error": f"PDF 파일만 지원합니다: .{extension}"}), 400

    if preset not in PDF_COMPRESSION_PRESET_CHOICES:
        return jsonify({"error": f"지원하지 않는 압축 강도입니다: {preset}"}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "document"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)
    original_size = input_path.stat().st_size

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_압축.pdf"
        compress_pdf(str(input_path), str(output_path), preset)
        compressed_size = output_path.stat().st_size
        add_record(original_name, "pdf", "pdf(압축)", original_size, compressed_size)
    except Exception as error:
        return jsonify({"error": f"압축에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_압축.pdf"
    response = send_file(output_path, as_attachment=True, download_name=download_name)
    response.headers["X-Original-Size"] = str(original_size)
    response.headers["X-Compressed-Size"] = str(compressed_size)
    return response


@convert_bp.post("/api/compress/office")
def compress_office_route():
    uploaded_file = request.files.get("file")
    preset = request.form.get("preset", DEFAULT_OFFICE_COMPRESSION_PRESET).strip().lower()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_OFFICE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 오피스 문서 형식입니다: .{extension}"}), 400

    if preset not in OFFICE_COMPRESSION_PRESET_CHOICES:
        return jsonify({"error": f"지원하지 않는 압축 강도입니다: {preset}"}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "document"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)
    original_size = input_path.stat().st_size

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_압축.{extension}"
        compress_office_document(str(input_path), str(output_path), preset)
        compressed_size = output_path.stat().st_size
        add_record(original_name, extension, f"{extension}(압축)", original_size, compressed_size)
    except Exception as error:
        return jsonify({"error": f"압축에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_압축.{extension}"
    response = send_file(output_path, as_attachment=True, download_name=download_name)
    response.headers["X-Original-Size"] = str(original_size)
    response.headers["X-Compressed-Size"] = str(compressed_size)
    return response


@convert_bp.post("/api/compress/universal")
def compress_universal_route():
    uploaded_file = request.files.get("file")
    target_mb_raw = request.form.get("target_mb", str(DEFAULT_TARGET_SIZE_MB)).strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in UNIVERSAL_COMPRESS_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 파일 형식입니다: .{extension}"}), 400

    try:
        target_mb = float(target_mb_raw)
    except ValueError:
        return jsonify({"error": f"목표 용량 값이 올바르지 않습니다: {target_mb_raw}"}), 400

    if not (MIN_TARGET_SIZE_MB <= target_mb <= MAX_TARGET_SIZE_MB):
        return jsonify({"error": f"목표 용량은 {MIN_TARGET_SIZE_MB}~{MAX_TARGET_SIZE_MB}MB 사이여야 합니다."}), 400

    is_video = extension in ALLOWED_VIDEO_EXTENSIONS
    if is_video and not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    target_bytes = round(target_mb * 1024 * 1024)

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "file"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)
    original_size = input_path.stat().st_size

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_압축.{extension}"
        if is_video:
            _, compressed_size, achieved = compress_video_to_target_size(
                str(input_path), str(output_path), target_bytes
            )
        else:
            _, compressed_size, achieved = compress_image_to_target_size(
                str(input_path), str(output_path), target_bytes
            )
        add_record(original_name, extension, f"{extension}({target_mb}MB 압축)", original_size, compressed_size)
    except Exception as error:
        return jsonify({"error": f"압축에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_압축.{extension}"
    response = send_file(output_path, as_attachment=True, download_name=download_name)
    response.headers["X-Original-Size"] = str(original_size)
    response.headers["X-Compressed-Size"] = str(compressed_size)
    response.headers["X-Target-Achieved"] = "true" if achieved else "false"
    return response


@convert_bp.post("/api/process/remove-background")
def remove_background_route():
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 이미지 형식입니다: .{extension}"}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "image"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    try:
        output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_누끼.png"
        remove_background(str(input_path), str(output_path))
        add_record(original_name, extension, "png(배경제거)")
    except Exception as error:
        return jsonify({"error": f"배경 제거에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)

    download_name = f"{stem}_누끼.png"
    return send_file(output_path, as_attachment=True, download_name=download_name)


@convert_bp.post("/api/extract/subtitles")
def extract_subtitles_route():
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_AUDIO_INPUT_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 형식입니다: .{extension}"}), 400

    if not is_ffmpeg_available():
        return jsonify({"error": "FFmpeg가 설치되어 있지 않습니다. 먼저 설치해주세요."}), 400

    job_id = uuid.uuid4().hex
    stem = Path(original_name).stem or "subtitle"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    srt_path = OUTPUT_FOLDER / f"{job_id}_{stem}.srt"
    txt_path = OUTPUT_FOLDER / f"{job_id}_{stem}.txt"
    zip_path = OUTPUT_FOLDER / f"{job_id}_{stem}_자막.zip"

    try:
        result = extract_subtitles(str(input_path), str(srt_path), str(txt_path))

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(srt_path, arcname=f"{stem}.srt")
            archive.write(txt_path, arcname=f"{stem}.txt")

        add_record(original_name, extension, "srt+txt(자막)")
    except Exception as error:
        return jsonify({"error": f"자막 추출에 실패했습니다: {error}"}), 500
    finally:
        input_path.unlink(missing_ok=True)
        srt_path.unlink(missing_ok=True)
        txt_path.unlink(missing_ok=True)

    download_name = f"{stem}_자막.zip"
    response = send_file(zip_path, as_attachment=True, download_name=download_name)
    response.headers["X-Detected-Language"] = result["language"]
    return response
