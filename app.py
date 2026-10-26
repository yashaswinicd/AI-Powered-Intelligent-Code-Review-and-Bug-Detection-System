"""Flask web application: AI Code Review, Bug Detection and Auto-Fix."""

import json
import logging
import os
import threading
import webbrowser

from flask import (Flask, Response, jsonify, render_template, request)

from config.settings import (ALLOWED_EXTENSIONS, BENCHMARK_PATH, DEBUG, HOST,
                             MAX_CODE_LINES, MAX_FILE_SIZE, PORT, SECRET_KEY)
from src import compiler_check, report_generator
from src.language_support import supported_languages
from src.ml_model import load_metrics
from src.pipeline import get_result, process_code
from utils import stats_store

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("code-review")


def _error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _run(apply_fixes):
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not isinstance(code, str) or not code.strip():
        return _error("Please provide some code.")
    try:
        result = process_code(
            code, filename=data.get("filename") or None,
            language=data.get("language") or None,
            stdin_input=data.get("stdin_input", ""),
            apply_fixes=apply_fixes)
    except ValueError as exc:
        return _error(str(exc))
    except Exception:
        log.exception("Processing failed")
        return _error("The analysis failed unexpectedly. Check the server "
                      "log for details.", 500)
    return jsonify(result)


# ---------------------------------------------------------------- pages
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/review")
def review_page():
    return render_template("review.html",
                           languages=supported_languages(),
                           max_lines=MAX_CODE_LINES)


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


# ------------------------------------------------------------------ API
@app.route("/analyze", methods=["POST"])
def analyze_route():
    """Detect problems only (no changes to the code)."""
    return _run(apply_fixes=False)


@app.route("/debug", methods=["POST"])
def debug_route():
    """Detect, fix, verify and return the corrected code."""
    return _run(apply_fixes=True)


@app.route("/upload-debug", methods=["POST"])
def upload_debug_route():
    file = request.files.get("file")
    if not file or not file.filename:
        return _error("Please choose a file to upload.")
    extension = os.path.splitext(file.filename)[1].lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        return _error("Unsupported file type. Supported: " +
                      ", ".join(sorted("." + e for e in ALLOWED_EXTENSIONS)))
    raw = file.read()
    if b"\x00" in raw[:4096]:
        return _error("This looks like a binary file, not source code.")
    code = raw.decode("utf-8", errors="replace")
    try:
        result = process_code(
            code, filename=file.filename,
            language=request.form.get("language") or None,
            stdin_input=request.form.get("stdin_input", ""))
    except ValueError as exc:
        return _error(str(exc))
    except Exception:
        log.exception("Upload processing failed")
        return _error("The analysis failed unexpectedly.", 500)
    return jsonify(result)


@app.route("/report/<result_id>/<fmt>")
def report_route(result_id, fmt):
    result = get_result(result_id)
    if result is None:
        return _error("This result has expired. Run the analysis again.", 404)
    if fmt == "json":
        body, mime = report_generator.to_json(result), "application/json"
    elif fmt == "txt":
        body, mime = report_generator.to_text(result), "text/plain"
    elif fmt == "pdf":
        body = report_generator.to_pdf(result)
        if body is None:
            return _error("PDF export needs the 'reportlab' package.", 501)
        mime = "application/pdf"
    else:
        return _error("Unknown report format.", 404)
    headers = {"Content-Disposition":
               f"attachment; filename=code_review_report.{fmt}"}
    return Response(body, mimetype=mime, headers=headers)


@app.route("/api/languages")
def languages_route():
    return jsonify({"languages": supported_languages(),
                    "compilers": compiler_check.available_tools()})


@app.route("/api/stats")
def stats_route():
    return jsonify(stats_store.summary())


@app.route("/api/benchmark")
def benchmark_route():
    try:
        with open(BENCHMARK_PATH, encoding="utf-8") as fh:
            benchmark = json.load(fh)
    except (OSError, ValueError):
        benchmark = None
    return jsonify({"benchmark": benchmark, "ml": load_metrics()})


@app.route("/api/health")
def health_route():
    return jsonify({"status": "ok", "languages": len(supported_languages()),
                    "compilers": compiler_check.available_tools()})


@app.errorhandler(413)
def too_large(_):
    return _error(f"The file is larger than {MAX_FILE_SIZE // 2**20} MB.", 413)


@app.errorhandler(404)
def not_found(_):
    return _error("Page not found.", 404)


if __name__ == "__main__":
    # Open the browser one second after the server starts.
    # Skipped in debug mode so it does not open twice on reload.
    if not DEBUG:
        threading.Timer(
            1.0, lambda: webbrowser.open(f"http://{HOST}:{PORT}/")
        ).start()
    app.run(host=HOST, port=PORT, debug=DEBUG)