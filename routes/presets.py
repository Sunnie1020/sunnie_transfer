from flask import Blueprint, jsonify, request

from converters.presets import delete_preset, get_presets, save_preset

presets_bp = Blueprint("presets", __name__)


@presets_bp.get("/api/presets")
def list_presets_route():
    preset_key = request.args.get("key", "").strip()
    if not preset_key:
        return jsonify({"error": "key가 필요합니다."}), 400
    return jsonify({"presets": get_presets(preset_key)})


@presets_bp.post("/api/presets")
def save_preset_route():
    data = request.get_json(silent=True) or {}
    preset_key = (data.get("key") or "").strip()
    name = (data.get("name") or "").strip()
    options = data.get("options") or {}

    if not preset_key or not name:
        return jsonify({"error": "key와 name이 필요합니다."}), 400

    save_preset(preset_key, name, options)
    return jsonify({"success": True})


@presets_bp.delete("/api/presets/<int:preset_id>")
def delete_preset_route(preset_id):
    delete_preset(preset_id)
    return jsonify({"success": True})
