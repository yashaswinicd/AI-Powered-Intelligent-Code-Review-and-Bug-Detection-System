"""
helpers.py
Common utility/helper functions used across the
AI-Powered Code Review and Bug Detection System.
"""

import re
import hashlib
from datetime import datetime


def generate_file_hash(content):
    """Generates a unique SHA-256 hash for given code content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_timestamp():
    """Returns current timestamp as a formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def count_lines_of_code(content):
    """
    Returns total lines, blank lines, comment lines, and code lines
    for a given Python source string.
    """
    lines = content.splitlines()
    total = len(lines)
    blank = sum(1 for line in lines if line.strip() == "")
    comments = sum(1 for line in lines if line.strip().startswith("#"))
    code = total - blank - comments

    return {
        "total_lines": total,
        "blank_lines": blank,
        "comment_lines": comments,
        "code_lines": code
    }


def calculate_quality_score(bug_count, total_lines, security_issues=0):
    """
    Calculates a simple 0-100 code quality score based on bug density
    and security issues. Lower bugs/security issues -> higher score.
    """
    if total_lines == 0:
        return 0

    bug_density = bug_count / total_lines
    penalty = (bug_density * 100) + (security_issues * 5)
    score = max(0, 100 - penalty)
    return round(score, 2)


def clean_code_snippet(line, max_length=100):
    """Trims and formats a code line for display in reports."""
    line = line.strip()
    if len(line) > max_length:
        line = line[:max_length] + "..."
    return line


def extract_function_names(content):
    """Extracts Python function names using regex (quick, non-AST method)."""
    pattern = r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
    return re.findall(pattern, content)


def format_bug_report(bugs):
    """
    Formats a list of bug dicts into a readable summary string.
    Each bug dict is expected to have: line, type, message, severity.
    """
    if not bugs:
        return "No issues found. Code looks clean!"

    report_lines = []
    for bug in bugs:
        report_lines.append(
            f"[Line {bug.get('line', '?')}] "
            f"{bug.get('severity', 'INFO').upper()} - "
            f"{bug.get('type', 'Issue')}: {bug.get('message', '')}"
        )
    return "\n".join(report_lines)


def severity_to_color(severity):
    """Maps severity level to a color code for dashboard display."""
    mapping = {
        "critical": "#FF4C4C",
        "high": "#FF8C42",
        "medium": "#FFD93D",
        "low": "#6BCB77",
        "info": "#4D96FF"
    }
    return mapping.get(severity.lower(), "#CCCCCC")