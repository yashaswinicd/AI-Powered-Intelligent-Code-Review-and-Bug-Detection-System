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
    "csharp": {
        "name": "C#", "exts": [".cs"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": True, "semicolons": True, "brackets": True,
    },
    "javascript": {
        "name": "JavaScript", "exts": [".js", ".jsx", ".mjs", ".cjs"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'`",
        "triple": False, "semicolons": False, "brackets": True,
    },
    "typescript": {
        "name": "TypeScript", "exts": [".ts", ".tsx"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'`",
        "triple": False, "semicolons": False, "brackets": True,
    },
    "go": {
        "name": "Go", "exts": [".go"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'`",
        "triple": False, "semicolons": False, "brackets": True,
    },
    "php": {
        "name": "PHP", "exts": [".php"],
        "line": ["//", "#"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": False, "semicolons": True, "brackets": True,
    },
    "rust": {
        "name": "Rust", "exts": [".rs"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": False, "semicolons": True, "brackets": True,
    },
    "kotlin": {
        "name": "Kotlin", "exts": [".kt", ".kts"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": True, "semicolons": False, "brackets": True,
    },
    "swift": {
        "name": "Swift", "exts": [".swift"],
        "line": ["//"], "block": [("/*", "*/")], "quotes": "\"'",
        "triple": True, "semicolons": False, "brackets": True,
    },
}

C_FAMILY = {"c", "cpp", "java", "csharp", "javascript", "typescript",
            "go", "php", "rust", "kotlin", "swift"}

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
    "csharp": [
        (r"^\s*using\s+System", 6),
        (r"Console\.(WriteLine|ReadLine|Write)\s*\(", 5),
        (r"\bnamespace\s+[\w.]+", 3),
        (r"\bstatic\s+void\s+Main\s*\(", 5),
        (r"\bstring\s+\w+\s*=|\bvar\s+\w+\s*=", 1),
    ],
    "javascript": [
        (r"\bconsole\.(log|error|warn)\s*\(", 4),
        (r"\bfunction\s*\w*\s*\(", 3),
        (r"=>", 2),
        (r"\b(const|let)\s+\w+\s*=", 2),
        (r"\brequire\s*\(|\bmodule\.exports\b|\bdocument\.", 3),
        (r"\bvar\s+\w+\s*=", 1),
    ],
    "typescript": [
        (r":\s*(string|number|boolean|any|void)\b", 4),
        (r"^\s*interface\s+\w+", 4),
        (r"\btype\s+\w+\s*=", 3),
        (r"\bimport\s+.*\bfrom\s+['\"]", 1),
        (r"\bas\s+(string|number|any)\b", 2),
    ],
    "go": [
        (r"^\s*package\s+\w+", 5),
        (r"\bfunc\s+(\(\w+\s+\*?\w+\)\s*)?\w+\s*\(", 4),
        (r"\bfmt\.\w+\(", 5),
        (r":=", 2),
    ],
    "php": [
        (r"<\?php", 8),
        (r"\$\w+\s*=", 2),
        (r"\becho\b", 2),
    ],
    "rust": [
        (r"\bfn\s+\w+\s*(<.*>)?\s*\(", 4),
        (r"\blet\s+mut\b", 5),
        (r"\bprintln!\s*\(|\bvec!\[", 5),
        (r"\buse\s+std::", 5),
        (r"->\s*(i32|u32|i64|u64|f64|bool|String|&str)\b", 2),
    ],
    "kotlin": [
        (r"\bfun\s+\w+\s*\(", 5),
        (r"\b(val|var)\s+\w+\s*(:\s*\w+)?\s*=", 2),
        (r"\bprintln\s*\(", 1),
        (r"\bdata\s+class\b|\bwhen\s*\(", 4),
    ],
    "swift": [
        (r"^\s*import\s+(Foundation|UIKit|SwiftUI)", 6),
        (r"\bfunc\s+\w+\s*\(.*\)\s*(->\s*\w+)?\s*\{", 4),
        (r"\b(let|var)\s+\w+\s*:\s*\w+", 2),
        (r"\bguard\s+let\b|\bif\s+let\b", 4),
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

    # TypeScript is a superset of JavaScript; only choose it when its own
    # signatures clearly win.
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
