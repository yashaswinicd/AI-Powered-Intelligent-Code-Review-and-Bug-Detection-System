"""Application settings for the AI Code Review & Auto-Fix System."""

import os

from src.language_support import ALLOWED_EXTENSIONS as _EXTENSIONS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Flask ---------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
HOST = os.getenv("FLASK_HOST", "127.0.0.1")
PORT = int(os.getenv("FLASK_PORT", "5000"))

# --- Input limits ---------------------------------------------------------
ALLOWED_EXTENSIONS = {ext.lstrip(".") for ext in _EXTENSIONS}
MAX_CODE_LINES = int(os.getenv("MAX_CODE_LINES", "50000"))
MAX_FILE_SIZE = 5 * 1024 * 1024

# --- Output folders (absolute, so the app works from any directory) ------
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "reports")
STATS_PATH = os.path.join(OUTPUT_DIR, "stats.json")
BENCHMARK_PATH = os.path.join(OUTPUT_DIR, "benchmark.json")

# --- Machine learning -----------------------------------------------------
MODEL_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "code_review_model.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "model_metrics.json")
RANDOM_STATE = 42

# --- Scoring ----------------------------------------------------------------
SEVERITY_LEVELS = {"critical": 4, "high": 3, "medium": 2, "low": 1}
