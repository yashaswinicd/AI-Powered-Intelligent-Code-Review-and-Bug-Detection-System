import os
import threading
import webbrowser

from flask import Flask, request, jsonify, render_template

from src.review_engine import ReviewEngine
from src.security_checker import SecurityChecker
from src.debugging_engine import DebuggingEngine
from src.execution_engine import ExecutionEngine
from src.verification_engine import VerificationEngine

from utils.file_handler import (
    validate_code,
    save_uploaded_file,
    read_uploaded_file,
)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

URL = "http://127.0.0.1:5000"


# =========================================================
# ENGINE INITIALIZATION
# =========================================================

review = ReviewEngine()
security = SecurityChecker()
debugger = DebuggingEngine()
executor = ExecutionEngine()
verifier = VerificationEngine()


# =========================================================
# ANALYSIS
# =========================================================

def analyze(code, filename):
    return {
        "review": review.review(code, filename),
        "security": security.check(code),
    }


# =========================================================
# DEBUGGING + AUTO FIX
# =========================================================

def debug_code(code, filename):
    original = analyze(code, filename)

    current = code
    fixes = []

    for _ in range(10):
        result = analyze(current, filename)

        bugs = (
            result["review"]["bugs"]["bugs"]
            + result["security"]["vulnerabilities"]
        )

        if not bugs:
            break

        fixed = debugger.fix(current, bugs)
        new_code = fixed["fixed_code"]

        fixes.extend(fixed.get("fixes", []))

        # Prevent infinite loops and repeated unchanged code.
        if new_code == current:
            break

        # Accept only syntactically valid Python changes.
        if filename.lower().endswith(".py"):
            if not debugger.is_valid_python(new_code):
                break

        current = new_code

    final = analyze(current, filename)

    remaining = (
        final["review"]["bugs"]["bugs"]
        + final["security"]["vulnerabilities"]
    )

    # Execute only through the configured execution engine.
    execution = executor.run(current)

    original_bugs = (
        original["review"]["bugs"]["bugs"]
        + original["security"]["vulnerabilities"]
    )

    verification = verifier.verify(
        original_bugs,
        remaining,
        execution,
    )

    return {
        "filename": filename,
        "original_code": code,
        "fixed_code": current,
        "original_analysis": original,
        "fixed_analysis": final,
        "fixes": fixes,
        "execution": execution,
        "verification": verification,
    }


# =========================================================
# WEB PAGES
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/review")
def review_page():
    return render_template("review.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# =========================================================
# CODE ANALYSIS API
# =========================================================

@app.route("/analyze", methods=["POST"])
def analyze_api():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or "code" not in data:
        return jsonify({
            "success": False,
            "error": "Code required",
        }), 400

    code = data["code"]
    filename = data.get("filename", "code.py")

    if not isinstance(code, str):
        return jsonify({
            "success": False,
            "error": "Code must be a string",
        }), 400

    try:
        validate_code(code, filename)

        return jsonify({
            "success": True,
            **analyze(code, filename),
        })

    except Exception as exc:
        app.logger.exception("Code analysis failed")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400


# =========================================================
# DEBUG API
# =========================================================

@app.route("/debug", methods=["POST"])
def debug_api():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or "code" not in data:
        return jsonify({
            "success": False,
            "error": "Code required",
        }), 400

    code = data["code"]
    filename = data.get("filename", "code.py")

    if not isinstance(code, str):
        return jsonify({
            "success": False,
            "error": "Code must be a string",
        }), 400

    try:
        validate_code(code, filename)

        return jsonify({
            "success": True,
            **debug_code(code, filename),
        })

    except Exception as exc:
        app.logger.exception("Debugging request failed")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400


# =========================================================
# FILE UPLOAD + DEBUG
# =========================================================

@app.route("/upload-debug", methods=["POST"])
def upload_debug():
    if "file" not in request.files:
        return jsonify({
            "success": False,
            "error": "No file uploaded",
        }), 400

    path = None

    try:
        uploaded_file = request.files["file"]

        if not uploaded_file.filename:
            return jsonify({
                "success": False,
                "error": "Choose a file first",
            }), 400

        path = save_uploaded_file(uploaded_file)
        code = read_uploaded_file(path)
        filename = os.path.basename(uploaded_file.filename)

        validate_code(code, filename)

        return jsonify({
            "success": True,
            **debug_code(code, filename),
        })

    except Exception as exc:
        app.logger.exception("File upload/debugging failed")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400

    finally:
        # Temporary-file cleanup depends on the file handler's
        # storage contract; do not delete files here blindly.
        pass


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "AI Code Review and Debugging System",
    })


# =========================================================
# START SERVER + OPEN BROWSER
# =========================================================

if __name__ == "__main__":
    print("=" * 55)
    print("AI CODE REVIEW & DEBUGGING SYSTEM")
    print("=" * 55)
    print("Source size limit: 5 MB")
    print("Debugging: ENABLED")
    print("Execution: ENABLED")
    print("Auto-fix: ENABLED")
    print(f"Website: {URL}")
    print("Opening browser automatically...")
    print("=" * 55)

    threading.Timer(
        1.5,
        lambda: webbrowser.open(URL),
    ).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
    )