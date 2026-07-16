import webbrowser
from threading import Timer

from flask import Flask, render_template

from config import MAX_CONTENT_LENGTH, OUTPUT_FOLDER, UPLOAD_FOLDER
from converters.history import init_db as init_history_db
from converters.hotfolder import init_db as init_hotfolder_db
from converters.presets import init_db as init_presets_db
from routes.convert import convert_bp
from routes.hotfolder import hotfolder_bp
from routes.presets import presets_bp

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)
init_history_db()
init_presets_db()
init_hotfolder_db()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.register_blueprint(convert_bp)
app.register_blueprint(presets_bp)
app.register_blueprint(hotfolder_bp)


@app.get("/")
def index():
    return render_template("index.html")


def open_browser():
    webbrowser.open("http://127.0.0.1:5001")


if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
