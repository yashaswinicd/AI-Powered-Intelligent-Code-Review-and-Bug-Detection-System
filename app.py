
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
# CODE ANALYSIS
# =========================================================

def analyze(code, filename):
    return {
        "review": review.review(code, filename),
        "security": security.check(code),
    }


def collect_issues(analysis):
    """Combine review bugs and security vulnerabilities safely."""
    review_data = analysis.get("review", {})
    bug_data = review_data.get("bugs", {})
    bugs = bug_data.get("bugs", []) if isinstance(bug_data, dict) else []

    security_data = analysis.get("security", {})
    vulnerabilities = security_data.get("vulnerabilities", [])

    if not isinstance(bugs, list):
        bugs = []

    if not isinstance(vulnerabilities, list):
        vulnerabilities = []

    return bugs + vulnerabilities


# =========================================================
# DEBUGGING + AUTO FIX
# =========================================================

def debug_code(code, filename, stdin_input=None):
    original_analysis = analyze(code, filename)

    current_code = code
    all_fixes = []
    max_iterations = 10

    for _ in range(max_iterations):
        current_analysis = analyze(current_code, filename)
        current_issues = collect_issues(current_analysis)

        if not current_issues:
            break

        # DebuggingEngine performs its own detailed analysis.
        fixed_result = debugger.fix(current_code)

        if not isinstance(fixed_result, dict):
            break

        candidate_code = fixed_result.get("fixed_code", current_code)
        iteration_fixes = fixed_result.get("fixes", [])

        if not isinstance(candidate_code, str):
            break

        if not isinstance(iteration_fixes, list):
            iteration_fixes = []

        # Stop if no code change was produced.
        if candidate_code == current_code:
            break

        # Accept only syntactically valid Python changes.
        if filename.lower().endswith(".py"):
            if not debugger.is_valid_python(candidate_code):
                app.logger.warning(
                    "Rejected auto-fix because Python syntax validation failed."
                )
                break

        all_fixes.extend(iteration_fixes)
        current_code = candidate_code

    # Analyze the final code again after all accepted changes.
    final_analysis = analyze(current_code, filename)
    remaining_issues = collect_issues(final_analysis)

    # Run code only through the configured execution engine.
    execution_result = executor.run(current_code, stdin_input=stdin_input)

    original_issues = collect_issues(original_analysis)

    verification_result = verifier.verify(
        original_issues,
        remaining_issues,
        execution_result,
    )

    return {
        "filename": filename,
        "original_code": code,
        "fixed_code": current_code,
        "original_analysis": original_analysis,
        "fixed_analysis": final_analysis,
        "fixes": all_fixes,
        "total_fixes": len(all_fixes),
        "remaining_bugs": remaining_issues,
        "execution": execution_result,
        "verification": verification_result,
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
    stdin_input = data.get("stdin_input")

    if stdin_input is not None and not isinstance(stdin_input, str):
        return jsonify({
            "success": False,
            "error": "Test input must be a string",
        }), 400

    if stdin_input is not None and len(stdin_input) > 10000:
        return jsonify({
            "success": False,
            "error": "Test input cannot exceed 10000 characters",
        }), 400

    if not isinstance(code, str):
        return jsonify({
            "success": False,
            "error": "Code must be a string",
        }), 400

    try:
        validate_code(code, filename)
        result = analyze(code, filename)

        return jsonify({
            "success": True,
            **result,
        })

    except Exception:
        app.logger.exception("Code analysis failed")
        return jsonify({
            "success": False,
            "error": "Code analysis failed. Check the server terminal for details.",
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
    stdin_input = data.get("stdin_input")

    if stdin_input is not None and not isinstance(stdin_input, str):
        return jsonify({
            "success": False,
            "error": "Test input must be a string",
        }), 400

    if stdin_input is not None and len(stdin_input) > 10000:
        return jsonify({
            "success": False,
            "error": "Test input cannot exceed 10000 characters",
        }), 400

    if not isinstance(code, str):
        return jsonify({
            "success": False,
            "error": "Code must be a string",
        }), 400

    try:
        validate_code(code, filename)
        result = debug_code(code, filename, stdin_input=stdin_input)

        return jsonify({
            "success": True,
            **result,
        })

    except Exception:
        app.logger.exception("Debugging request failed")
        return jsonify({
            "success": False,
            "error": "Debugging failed. Check the server terminal for details.",
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

    uploaded_file = request.files["file"]

    if not uploaded_file.filename:
        return jsonify({
            "success": False,
            "error": "Choose a file first",
        }), 400

    path = None

    try:
        path = save_uploaded_file(uploaded_file)
        code = read_uploaded_file(path)
        filename = os.path.basename(uploaded_file.filename)

        validate_code(code, filename)
        result = debug_code(code, filename)

        return jsonify({
            "success": True,
            **result,
        })

    except Exception:
        app.logger.exception("File upload/debugging failed")
        return jsonify({
            "success": False,
            "error": "File debugging failed. Check the server terminal for details.",
        }), 400

    finally:
        # Do not delete the file here until the file handler's
        # temporary-file storage contract is confirmed.
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
# START SERVER
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




