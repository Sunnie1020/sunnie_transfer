from flask import Blueprint, abort, jsonify, request, send_file
from werkzeug.utils import secure_filename

from converters.share import create_share, get_share

share_bp = Blueprint("share", __name__)


@share_bp.post("/api/share")
def create_share_route():
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "파일이 전달되지 않았습니다."}), 400

    filename = secure_filename(request.form.get("filename") or uploaded_file.filename)
    file_bytes = uploaded_file.read()

    result = create_share(file_bytes, filename)
    return jsonify(result)


@share_bp.get("/share/<share_id>")
def download_share_route(share_id):
    entry = get_share(share_id)
    if entry is None:
        abort(404, description="이 링크는 만료됐거나 존재하지 않습니다.")

    return send_file(entry["path"], as_attachment=True, download_name=entry["filename"])
