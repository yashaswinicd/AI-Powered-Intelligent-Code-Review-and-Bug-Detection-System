"""Persistent usage statistics for the dashboard (a small JSON file)."""

import json
import os
import threading
from datetime import datetime

from config.settings import STATS_PATH

_LOCK = threading.Lock()

_EMPTY = {
    "total_analyses": 0, "total_lines": 0, "total_issues": 0,
    "total_fixes": 0, "verified": 0, "total_ms": 0,
    "languages": {}, "issue_types": {}, "severities": {}, "recent": [],
}


def _load():
    try:
        with open(STATS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        for key, value in _EMPTY.items():
            data.setdefault(key, type(value)() if not isinstance(
                value, (int, float)) else 0)
        return data
    except (OSError, ValueError):
        return json.loads(json.dumps(_EMPTY))


def record(language, lines, issues, fixes, verified, elapsed_ms):
    """Add one analysis to the statistics."""
    with _LOCK:
        data = _load()
        data["total_analyses"] += 1
        data["total_lines"] += lines
        data["total_issues"] += len(issues)
        data["total_fixes"] += fixes
        data["verified"] += 1 if verified else 0
        data["total_ms"] += elapsed_ms
        data["languages"][language] = data["languages"].get(language, 0) + 1
        for issue in issues:
            kind = issue["type"]
            data["issue_types"][kind] = data["issue_types"].get(kind, 0) + 1
            sev = issue["severity"]
            data["severities"][sev] = data["severities"].get(sev, 0) + 1
        data["recent"].insert(0, {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "language": language, "lines": lines, "issues": len(issues),
            "fixes": fixes, "verified": bool(verified),
        })
        data["recent"] = data["recent"][:10]
        os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
        tmp = STATS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, STATS_PATH)


def summary():
    with _LOCK:
        data = _load()
    n = data["total_analyses"]
    data["average_ms"] = round(data["total_ms"] / n) if n else 0
    data["verified_rate"] = round(100 * data["verified"] / n) if n else 0
    return data
