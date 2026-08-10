"""
logger.py
Centralized logging configuration for the AI-Powered Code Review
and Bug Detection System.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = "outputs/logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def setup_logger(name="code_review_app", level=logging.INFO):
    """
    Creates and returns a configured logger that logs to both
    console and a rotating log file.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Rotating file handler (max 5MB per file, keep 3 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Default app-wide logger instance
logger = setup_logger()


def log_analysis_start(filename):
    logger.info(f"Started analysis for file: {filename}")


def log_analysis_complete(filename, bugs_found=0, quality_score=None):
    logger.info(
        f"Completed analysis for {filename} | Bugs found: {bugs_found} | "
        f"Quality score: {quality_score}"
    )


def log_error(context, error):
    logger.error(f"Error in {context}: {str(error)}")