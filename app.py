import webbrowser
from threading import Timer

from flask import Flask, jsonify, render_template

from config import APP_PORT, MAX_CONTENT_LENGTH, OUTPUT_FOLDER, SHARE_FOLDER, UPLOAD_FOLDER
from converters.history import init_db as init_history_db
from converters.hotfolder import init_db as init_hotfolder_db
from converters.presets import init_db as init_presets_db
from converters.share import cleanup_stale_share_files, start_cleanup_thread as start_share_cleanup_thread
from routes.convert import convert_bp
from routes.hotfolder import hotfolder_bp
from routes.presets import presets_bp
from routes.share import share_bp
from routes.style_transfer import style_transfer_bp
from routes.youtube import youtube_bp

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)
SHARE_FOLDER.mkdir(exist_ok=True)
init_history_db()
init_presets_db()
init_hotfolder_db()
cleanup_stale_share_files()
start_share_cleanup_thread()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.register_blueprint(convert_bp)
app.register_blueprint(presets_bp)
app.register_blueprint(hotfolder_bp)
app.register_blueprint(share_bp)
app.register_blueprint(youtube_bp)
app.register_blueprint(style_transfer_bp)


@app.get("/")
def index():
    return render_template("index.html")


@app.errorhandler(413)
def file_too_large(error):
    max_gb = MAX_CONTENT_LENGTH / (1024**3)
    return jsonify({"error": f"파일이 너무 큽니다. 한 번에 최대 {max_gb:.0f}GB까지 업로드할 수 있어요."}), 413


def open_browser():
    webbrowser.open(f"http://127.0.0.1:{APP_PORT}")


if __name__ == "__main__":
    Timer(1, open_browser).start()
    # host를 0.0.0.0으로 열어야 같은 와이파이의 다른 기기가 QR 공유 링크로 접속할 수 있다.
    app.run(host="0.0.0.0", port=APP_PORT, debug=False, threaded=True)
