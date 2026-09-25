import os
from flask import Flask, request, jsonify, render_template

from src.review_engine import ReviewEngine
from src.security_checker import SecurityChecker
from src.debugging_engine import DebuggingEngine
from src.execution_engine import ExecutionEngine
from src.verification_engine import VerificationEngine

from utils.file_handler import (
    validate_code,
    save_uploaded_file,
    read_uploaded_file
)


app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


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
        "security": security.check(code)
    }


# =========================================================
# DEBUGGING + AUTO FIX
# =========================================================

def debug_code(code, filename):

    # -----------------------------------------------------
    # ORIGINAL ANALYSIS
    # -----------------------------------------------------

    original = analyze(code, filename)

    current = code
    fixes = []

    # -----------------------------------------------------
    # AUTO-FIX LOOP
    # -----------------------------------------------------

    for _ in range(10):

        result = analyze(current, filename)

        # Combine normal bugs + security vulnerabilities
        bugs = (
            result["review"]["bugs"]["bugs"]
            + result["security"]["vulnerabilities"]
        )

        # Nothing left to fix
        if not bugs:
            break

        fixed = debugger.fix(
            current,
            bugs
        )

        new_code = fixed["fixed_code"]

        fixes.extend(
            fixed["fixes"]
        )

        # Prevent infinite loop
        if new_code == current:
            break

        current = new_code

    # -----------------------------------------------------
    # FINAL ANALYSIS
    # -----------------------------------------------------

    final = analyze(
        current,
        filename
    )

    # Combine remaining normal bugs + security issues
    remaining = (
        final["review"]["bugs"]["bugs"]
        + final["security"]["vulnerabilities"]
    )

    # -----------------------------------------------------
    # EXECUTE FIXED CODE
    # -----------------------------------------------------

    execution = executor.run(
        current
    )

    # -----------------------------------------------------
    # ORIGINAL ISSUES
    # -----------------------------------------------------

    original_bugs = (
        original["review"]["bugs"]["bugs"]
        + original["security"]["vulnerabilities"]
    )

    # -----------------------------------------------------
    # VERIFY FIX
    # -----------------------------------------------------

    verification = verifier.verify(
        original_bugs,
        remaining,
        execution
    )

    # -----------------------------------------------------
    # FINAL RESPONSE
    # -----------------------------------------------------

    return {
        "filename": filename,

        "original_code": code,

        "fixed_code": current,

        "original_analysis": original,

        "fixed_analysis": final,

        "fixes": fixes,

        "execution": execution,

        "verification": verification
    }


# =========================================================
# WEB PAGES
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route("/review")
def review_page():

    return render_template(
        "review.html"
    )


@app.route("/dashboard")
def dashboard():

    return render_template(
        "dashboard.html"
    )


# =========================================================
# CODE ANALYSIS API
# =========================================================

@app.route(
    "/analyze",
    methods=["POST"]
)
def analyze_api():

    data = request.get_json()

    if not data or "code" not in data:

        return jsonify({
            "success": False,
            "error": "Code required"
        }), 400

    code = data["code"]

    filename = data.get(
        "filename",
        "code.py"
    )

    try:

        validate_code(
            code,
            filename
        )

        return jsonify({
            "success": True,
            **analyze(
                code,
                filename
            )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


# =========================================================
# DEBUG API
# =========================================================

@app.route(
    "/debug",
    methods=["POST"]
)
def debug_api():

    data = request.get_json()

    if not data or "code" not in data:

        return jsonify({
            "success": False,
            "error": "Code required"
        }), 400

    code = data["code"]

    filename = data.get(
        "filename",
        "code.py"
    )

    try:

        validate_code(
            code,
            filename
        )

        return jsonify({
            "success": True,
            **debug_code(
                code,
                filename
            )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


# =========================================================
# FILE UPLOAD + DEBUG
# =========================================================

@app.route(
    "/upload-debug",
    methods=["POST"]
)
def upload_debug():

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "error": "No file uploaded"
        }), 400

    try:

        file = request.files["file"]

        path = save_uploaded_file(
            file
        )

        code = read_uploaded_file(
            path
        )

        filename = os.path.basename(
            path
        )

        return jsonify({
            "success": True,
            **debug_code(
                code,
                filename
            )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/api/health")
def health():

    return jsonify({
        "status": "healthy",
        "service": (
            "AI Code Review and "
            "Debugging System"
        )
    })


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    print(
        "AI CODE REVIEW & DEBUGGING SYSTEM"
    )

    print(
        "Maximum source lines: 10,000"
    )

    print(
        "Debugging: ENABLED"
    )

    print(
        "Execution: ENABLED"
    )

    print(
        "Auto-Fix: ENABLED"
    )

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )