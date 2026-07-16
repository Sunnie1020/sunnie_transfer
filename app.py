import webbrowser
from threading import Timer

from flask import Flask, render_template

from config import MAX_CONTENT_LENGTH, OUTPUT_FOLDER, UPLOAD_FOLDER
from routes.convert import convert_bp

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.register_blueprint(convert_bp)


@app.get("/")
def index():
    return render_template("index.html")


def open_browser():
    webbrowser.open("http://127.0.0.1:5001")


if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run(host="127.0.0.1", port=5001, debug=False)
