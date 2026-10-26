"""Language table and automatic language detection.

Every language the system understands is described once, here. The lexer,
the analyzer and the web interface all read from this table, so adding a
new language means adding one entry (and, if needed, a few rules).
"""

import os
import re

# Fields
#   name        display name
#   exts        file extensions
#   line        line-comment markers
#   block       (start, end) block-comment markers
#   quotes      characters that open an ordinary string literal
#   triple      True if """ ... """ (or ''' ... ''') multi-line strings exist
#   semicolons  True if statements must end with ';' (used by the
#               missing-semicolon check; languages with optional
#               semicolons are not checked for them)
#   brackets    True if () [] {} balance is checked
LANGUAGES = {
    "python": {
        "name": "Python", "exts": [".py", ".pyw"],
        "line": ["#"], "block": [], "quotes": "\"'", "triple": True,
        "semicolons": False, "brackets": True,
    },
    "java": {
        "name": "Java", "exts": [".java"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": True, "semicolons": True, "brackets": True,
    },
    "c": {
        "name": "C", "exts": [".c", ".h"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": False, "semicolons": True, "brackets": True,
    },
    "cpp": {
        "name": "C++", "exts": [".cpp", ".cc", ".cxx", ".hpp", ".hh"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": False, "semicolons": True, "brackets": True,
    },
    "javascript": {
        "name": "JavaScript", "exts": [".js", ".jsx", ".mjs", ".cjs"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'`",
        "triple": False, "semicolons": False, "brackets": True,
    },
}

C_FAMILY = {"c", "cpp", "java", "javascript"}

EXTENSION_MAP = {
    ext: key for key, cfg in LANGUAGES.items() for ext in cfg["exts"]
}

ALLOWED_EXTENSIONS = set(EXTENSION_MAP)


def language_name(key):
    return LANGUAGES.get(key, {}).get("name", "Unknown")


def supported_languages():
    return [{"key": k, "name": v["name"], "extensions": v["exts"]}
            for k, v in LANGUAGES.items()]


# Content signatures used when the file name gives no hint (for example
# when code is pasted into the text box). Each pattern adds its weight to
# the language score; the highest score wins.
_SIGNATURES = {
    "python": [
        (r"^\s*def\s+\w+\s*\(.*\)\s*(->\s*[\w\[\], .]+)?\s*:", 4),
        (r"^\s*(from\s+[\w.]+\s+)?import\s+[\w., ]+\s*$", 2),
        (r"^\s*elif\b|^\s*except\b.*:|^\s*if\s+__name__", 3),
        (r"\bself\b|\bprint\s*\(", 1),
        (r"^\s*class\s+\w+(\(.*\))?\s*:", 3),
    ],
    "java": [
        (r"\bpublic\s+(static\s+)?(final\s+)?class\b", 4),
        (r"System\.out\.print", 5),
        (r"public\s+static\s+void\s+main\s*\(", 5),
        (r"^\s*import\s+java\.", 5),
        (r"\bString\[\]\s+\w+", 3),
        (r"@Override\b", 2),
    ],
    "c": [
        (r"#include\s*<(stdio|stdlib|string|math|ctype|time)\.h>", 5),
        (r"\bprintf\s*\(|\bscanf\s*\(", 2),
        (r"\bint\s+main\s*\(", 2),
        (r"\bmalloc\s*\(|\bfree\s*\(", 2),
    ],
    "cpp": [
        (r"#include\s*<(iostream|vector|string|map|set|algorithm|"
         r"memory|bits/stdc\+\+\.h)>", 6),
        (r"\bstd::|\busing\s+namespace\s+std\b", 5),
        (r"\bcout\s*<<|\bcin\s*>>", 5),
        (r"\btemplate\s*<|\bnullptr\b", 3),
        (r"\bclass\s+\w+\s*(:\s*public\s+\w+)?\s*\{", 1),
    ],
    "javascript": [
        (r"\bconsole\.(log|error|warn)\s*\(", 4),
        (r"\bfunction\s*\w*\s*\(", 3),
        (r"=>", 2),
        (r"\b(const|let)\s+\w+\s*=", 2),
        (r"\brequire\s*\(|\bmodule\.exports\b|\bdocument\.", 3),
        (r"\bvar\s+\w+\s*=", 1),
    ],
}

_COMPILED = {
    lang: [(re.compile(p, re.MULTILINE), w) for p, w in sigs]
    for lang, sigs in _SIGNATURES.items()
}


def detect_language(code, filename=None, hint=None):
    """Return (language_key, confidence, reason).

    Priority: explicit choice by the user, then the file extension, then
    the content of the code itself.
    """
    if hint and hint != "auto" and hint in LANGUAGES:
        return hint, 1.0, "selected by user"

    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in EXTENSION_MAP:
            return EXTENSION_MAP[ext], 1.0, f"file extension {ext}"

    sample = code[:60000]
    scores = {}
    for lang, patterns in _COMPILED.items():
        total = 0
        for pattern, weight in patterns:
            if pattern.search(sample):
                total += weight
        if total:
            scores[lang] = total

    if not scores:
        return "python", 0.0, "no clear signature, defaulting to Python"

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    # C vs C++: a C++ signature always beats a plain C one.
    if best == "c" and scores.get("cpp", 0) >= 5:
        best, best_score = "cpp", scores["cpp"]

    confidence = round(min(1.0, best_score / (best_score + second_score + 4)
                           + 0.25), 2)
    return best, confidence, "detected from code content"
