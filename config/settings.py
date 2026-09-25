"""
Application configuration settings
for the AI-Powered Intelligent Code Review,
Bug Detection, Debugging and Auto-Fix System.
"""

import os


# =============================
# Flask Configuration
# =============================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-secret-key-change-in-production"
)

DEBUG = os.getenv(
    "FLASK_DEBUG",
    "True"
).lower() == "true"

HOST = os.getenv(
    "FLASK_HOST",
    "127.0.0.1"
)

PORT = int(
    os.getenv(
        "FLASK_PORT",
        "5000"
    )
)


# =============================
# File Upload Configuration
# =============================

UPLOAD_DIR = os.getenv(
    "UPLOAD_FOLDER",
    os.path.join(
        "uploads",
        "code_files"
    )
)

ALLOWED_EXTENSIONS = {
    "py",
    "js",
    "java",
    "cpp",
    "c",
    "ts",
    "jsx",
    "tsx"
}


# =============================
# Code Input Limits
# =============================

MAX_CODE_LINES = 10000

MAX_FILE_SIZE = 5 * 1024 * 1024


# =============================
# Output Configuration
# =============================

OUTPUT_FOLDER = os.getenv(
    "OUTPUT_FOLDER",
    os.path.join(
        "outputs",
        "reports"
    )
)

# Used by report_generator.py
REPORTS_DIR = OUTPUT_FOLDER


# =============================
# Model Configuration
# =============================

MODEL_DIR = "models"

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "code_review_model.pkl"
)

VECTORIZER_PATH = os.path.join(
    MODEL_DIR,
    "vectorizer.pkl"
)

METRICS_PATH = os.path.join(
    MODEL_DIR,
    "model_metrics.json"
)


# =============================
# Machine Learning Configuration
# =============================

TEST_SIZE = 0.2

RANDOM_STATE = 42

MAX_FEATURES = 5000


# =============================
# Supported Languages
# =============================

SUPPORTED_LANGUAGES = {
    "python": [".py"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "java": [".java"],
    "cpp": [".cpp"],
    "c": [".c"]
}


# =============================
# Analysis Configuration
# =============================

BUG_THRESHOLD = 0.5

SEVERITY_LEVELS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1
}