from flask import Blueprint, jsonify, request

from converters.hotfolder import get_status, start_watching, stop_watching

hotfolder_bp = Blueprint("hotfolder", __name__)


@hotfolder_bp.get("/api/hotfolder/status")
def hotfolder_status_route():
    return jsonify(get_status())


@hotfolder_bp.post("/api/hotfolder/start")
def hotfolder_start_route():
    data = request.get_json(silent=True) or {}
    watch_dir = (data.get("watch_dir") or "").strip()
    output_dir = (data.get("output_dir") or "").strip()

    if not watch_dir or not output_dir:
        return jsonify({"success": False, "message": "감시 폴더와 완료 폴더를 모두 입력해주세요."}), 400

    result = start_watching(watch_dir, output_dir)
    return jsonify(result), (200 if result["success"] else 400)


@hotfolder_bp.post("/api/hotfolder/stop")
def hotfolder_stop_route():
    result = stop_watching()
    return jsonify(result), (200 if result["success"] else 400)
