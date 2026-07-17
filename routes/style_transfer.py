import threading
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from config import ALLOWED_IMAGE_EXTENSIONS, OUTPUT_FOLDER, STYLE_TRANSFER_CHOICES, UPLOAD_FOLDER
from converters.history import add_record
from converters.job_store import create_job, delete_job, get_job, update_job
from converters.style_transfer import convert_photo_to_style

style_transfer_bp = Blueprint("style_transfer", __name__)


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@style_transfer_bp.post("/api/process/style-transfer/start")
def style_transfer_start_route():
    uploaded_file = request.files.get("file")
    style = (request.form.get("style") or "").strip().lower()

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    original_name = secure_filename(uploaded_file.filename)
    extension = _extension_of(original_name)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"지원하지 않는 이미지 형식입니다: .{extension}"}), 400

    if style not in STYLE_TRANSFER_CHOICES:
        return jsonify({"error": f"지원하지 않는 스타일입니다: {style}"}), 400

    job_id = create_job()
    stem = Path(original_name).stem or "image"

    input_path = UPLOAD_FOLDER / f"{job_id}_{original_name}"
    uploaded_file.save(input_path)

    def _run():
        try:
            output_path = OUTPUT_FOLDER / f"{job_id}_{stem}_그림.png"

            def on_progress(percent):
                update_job(job_id, percent=percent)

            convert_photo_to_style(str(input_path), str(output_path), style, on_progress=on_progress)
            add_record(original_name, extension, f"그림({style})")
            update_job(
                job_id,
                status="done",
                percent=100,
                result_path=str(output_path),
                download_name=f"{stem}_그림.png",
            )
        except Exception as error:
            update_job(job_id, status="error", error=f"그림 변환에 실패했습니다: {error}")
        finally:
            input_path.unlink(missing_ok=True)

    threading.Thread(target=_run, daemon=True).start()

    return jsonify({"job_id": job_id}), 202


@style_transfer_bp.get("/api/process/style-transfer/status/<job_id>")
def style_transfer_status_route(job_id):
    job = get_job(job_id)
    if job is None:
        return jsonify({"error": "작업을 찾을 수 없습니다."}), 404

    return jsonify({"status": job["status"], "percent": job["percent"], "error": job.get("error")})


@style_transfer_bp.get("/api/process/style-transfer/result/<job_id>")
def style_transfer_result_route(job_id):
    job = get_job(job_id)
    if job is None or job["status"] != "done":
        return jsonify({"error": "아직 완료되지 않았습니다."}), 400

    response = send_file(job["result_path"], as_attachment=True, download_name=job["download_name"])
    delete_job(job_id)
    return response
