import shutil
import threading
import zipfile
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from config import OUTPUT_FOLDER, UPLOAD_FOLDER
from converters.history import add_record
from converters.job_store import create_job, delete_job, get_job, update_job
from converters.sns_downloader import download_instagram_media, download_x_media

sns_bp = Blueprint("sns", __name__)


def _run_download_job(job_id: str, url: str, download_fn, zip_name: str, source_label: str):
    job_dir = Path(UPLOAD_FOLDER) / job_id

    try:
        def on_progress(percent):
            update_job(job_id, percent=percent)

        files = download_fn(url, str(UPLOAD_FOLDER), job_id, on_progress=on_progress)

        zip_path = OUTPUT_FOLDER / f"{job_id}_{zip_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in files:
                archive.write(file_path, arcname=Path(file_path).name)

        add_record(source_label, source_label, "zip")
        update_job(
            job_id,
            status="done",
            percent=100,
            result_path=str(zip_path),
            download_name=f"{zip_name}.zip",
        )
    except Exception as error:
        update_job(job_id, status="error", error=f"다운로드에 실패했습니다: {error}")
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@sns_bp.post("/api/sns/x/start")
def x_download_start_route():
    url = (request.form.get("url") or "").strip()
    if not url:
        return jsonify({"error": "X(트위터) 링크를 입력해주세요."}), 400

    job_id = create_job()
    threading.Thread(
        target=_run_download_job, args=(job_id, url, download_x_media, "x_영상", "x"), daemon=True
    ).start()

    return jsonify({"job_id": job_id}), 202


@sns_bp.get("/api/sns/x/status/<job_id>")
def x_download_status_route(job_id):
    job = get_job(job_id)
    if job is None:
        return jsonify({"error": "작업을 찾을 수 없습니다."}), 404

    return jsonify({"status": job["status"], "percent": job["percent"], "error": job.get("error")})


@sns_bp.get("/api/sns/x/result/<job_id>")
def x_download_result_route(job_id):
    job = get_job(job_id)
    if job is None or job["status"] != "done":
        return jsonify({"error": "아직 완료되지 않았습니다."}), 400

    response = send_file(job["result_path"], as_attachment=True, download_name=job["download_name"])
    delete_job(job_id)
    return response


@sns_bp.post("/api/sns/instagram/start")
def instagram_download_start_route():
    url = (request.form.get("url") or "").strip()
    if not url:
        return jsonify({"error": "인스타그램 링크를 입력해주세요."}), 400

    job_id = create_job()
    threading.Thread(
        target=_run_download_job,
        args=(job_id, url, download_instagram_media, "인스타_다운로드", "instagram"),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id}), 202


@sns_bp.get("/api/sns/instagram/status/<job_id>")
def instagram_download_status_route(job_id):
    job = get_job(job_id)
    if job is None:
        return jsonify({"error": "작업을 찾을 수 없습니다."}), 404

    return jsonify({"status": job["status"], "percent": job["percent"], "error": job.get("error")})


@sns_bp.get("/api/sns/instagram/result/<job_id>")
def instagram_download_result_route(job_id):
    job = get_job(job_id)
    if job is None or job["status"] != "done":
        return jsonify({"error": "아직 완료되지 않았습니다."}), 400

    response = send_file(job["result_path"], as_attachment=True, download_name=job["download_name"])
    delete_job(job_id)
    return response
