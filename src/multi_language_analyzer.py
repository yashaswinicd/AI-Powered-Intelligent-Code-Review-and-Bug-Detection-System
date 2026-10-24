"""Language-aware syntax diagnostics without executing submitted source code.

Supported syntax checks use the language's own parser/compiler when installed.
This module intentionally reports unavailable tooling instead of claiming code is clean.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class MultiLanguageAnalyzer:
    LANGUAGE_BY_EXTENSION = {
        ".py": "Python",
        ".js": "JavaScript",
        ".mjs": "JavaScript",
        ".cjs": "JavaScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".c": "C",
        ".h": "C",
        ".cc": "C++",
        ".cpp": "C++",
        ".cxx": "C++",
        ".hpp": "C++",
        ".hh": "C++",
    }

    def detect_language(self, filename: str, code: str = "") -> str:
        ext = Path(filename or "").suffix.lower()
        # The default API filename is generic; allow obvious pasted snippets to override it.
        if ext == ".py" and Path(filename or "").name.lower() == "code.py":
            guessed = self._guess_from_content(code)
            if guessed:
                return guessed
        return self.LANGUAGE_BY_EXTENSION.get(ext, self._guess_from_content(code) or "Unknown")

    @staticmethod
    def _guess_from_content(code: str) -> str | None:
        sample = code[:12000]
        if re.search(r"\b(public\s+)?class\s+\w+\s*\{|\bSystem\.out\.println\s*\(", sample):
            return "Java"
        if re.search(r"#include\s*[<\"]|\bint\s+main\s*\(", sample):
            if re.search(r"#include\s*[<\"](?:iostream|string|vector)\b|\bstd::", sample):
                return "C++"
            return "C"
        if re.search(r"\b(const|let|var)\s+\w+\s*=|\bconsole\.log\s*\(", sample):
            return "JavaScript"
        if re.search(r"^\s*(def|import|from|class)\s+\w+", sample, re.MULTILINE):
            return "Python"
        return None

    @staticmethod
    def _diagnostic(message: str, language: str) -> dict:
        line = column = None
        severity = "error" if re.search(r"\berror\b|SyntaxError|expected|illegal start", message, re.I) else "warning"
        patterns = [
            r":(?P<line>\d+):(?P<column>\d+):\s*(?:fatal )?(?:error|warning):",
            r":(?P<line>\d+):\s*(?:error|warning):",
            r"\.java:(?P<line>\d+):\s*(?:error|warning):",
            r"\.js:(?P<line>\d+)",
            r"line (?P<line>\d+)(?:, column (?P<column>\d+))?",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.I)
            if match:
                line = int(match.group("line"))
                if match.groupdict().get("column"):
                    column = int(match.group("column"))
                break
        return {
            "type": "Syntax Error" if severity == "error" else "Compiler Warning",
            "line": line,
            "column": column,
            "severity": "high" if severity == "error" else "medium",
            "message": message.strip()[:1200],
            "root_cause": f"The {language} parser/compiler reported this diagnostic.",
            "suggestion": "Review the reported line and the surrounding syntax. The analyzer does not guess an automatic fix for this diagnostic.",
            "source": "language_toolchain",
        }

    def analyze(self, code: str, filename: str = "code.py") -> dict:
        if not isinstance(code, str):
            return {"language": "Unknown", "available": False, "success": False, "diagnostics": [], "error": "Code must be text."}
        language = self.detect_language(filename, code)
        stats = {
            "total_lines": len(code.splitlines()),
            "code_lines": sum(bool(line.strip()) for line in code.splitlines()),
            "blank_lines": sum(not line.strip() for line in code.splitlines()),
            "characters": len(code),
            "bytes": len(code.encode("utf-8")),
        }
        if language == "Unknown":
            return {"language": language, "available": False, "success": False, "diagnostics": [], "stats": stats, "error": "Could not determine language. Choose a supported file extension."}

        if language == "Python":
            try:
                compile(code, filename or "<code>", "exec")
                return {"language": language, "available": True, "success": True, "diagnostics": [], "stats": stats, "tool": "Python compile()", "message": "No Python syntax errors detected."}
            except (SyntaxError, ValueError, TypeError, OverflowError) as exc:
                line = getattr(exc, "lineno", None)
                column = getattr(exc, "offset", None)
                issue = {
                    "type": type(exc).__name__, "line": line, "column": column,
                    "severity": "high", "message": getattr(exc, "msg", str(exc)),
                    "root_cause": "Python could not parse the source code.",
                    "suggestion": "Correct the syntax at the reported line, then analyze again.",
                    "source": "python_parser",
                }
                return {"language": language, "available": True, "success": False, "diagnostics": [issue], "stats": stats, "tool": "Python compile()"}

        tool_map = {
            "JavaScript": ("node", ["--check"]),
            "Java": ("javac", ["-Xlint:all"]),
            "C": (shutil.which("gcc") and "gcc" or "clang", ["-fsyntax-only", "-Wall", "-Wextra"]),
            "C++": (shutil.which("g++") and "g++" or "clang++", ["-fsyntax-only", "-Wall", "-Wextra"]),
        }
        executable, flags = tool_map[language]
        if not shutil.which(executable):
            return {"language": language, "available": False, "success": False, "diagnostics": [], "stats": stats, "tool": executable, "error": f"{executable} is not installed or not on PATH. No syntax-check result can be claimed."}

        suffix = {"JavaScript": ".js", "Java": ".java", "C": ".c", "C++": ".cpp"}[language]
        temp_dir = tempfile.TemporaryDirectory(prefix="code_review_")
        try:
            original_name = Path(filename or "").name
            if language == "Java":
                class_match = re.search(r"\bpublic\s+class\s+([A-Za-z_$][\w$]*)", code)
                source_name = (class_match.group(1) if class_match else "Main") + ".java"
            else:
                source_name = original_name if Path(original_name).suffix.lower() == suffix else "source" + suffix
            source_path = Path(temp_dir.name) / source_name
            source_path.write_text(code, encoding="utf-8")
            command = [executable, *flags]
            if language == "Java":
                command += [str(source_path)]
            elif language == "JavaScript":
                command += [str(source_path)]
            else:
                command += [str(source_path)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, cwd=temp_dir.name)
            raw = "\n".join(part for part in (result.stderr, result.stdout) if part.strip()).strip()
            diagnostics = []
            if raw:
                if language == "JavaScript":
                    # Node prints the source location on the line before SyntaxError.
                    diagnostics = [self._diagnostic(raw, language)]
                else:
                    chunks = [line for line in raw.splitlines() if re.search(r"error:|warning:|SyntaxError|Error:|expected|illegal start", line, re.I)]
                    if not chunks:
                        chunks = raw.splitlines()[-8:]
                    diagnostics = [self._diagnostic(line, language) for line in chunks[:50]]
                # Preserve compiler exit status as an issue even if diagnostic wording differs.
                if result.returncode != 0 and not any(item["severity"] == "high" for item in diagnostics):
                    diagnostics.insert(0, {"type": "Syntax/Compile Error", "line": None, "column": None, "severity": "high", "message": raw[:1200], "root_cause": f"{executable} rejected the source code.", "suggestion": "Read the compiler output and correct the reported issue.", "source": "language_toolchain"})
            success = result.returncode == 0
            return {"language": language, "available": True, "success": success, "diagnostics": diagnostics, "stats": stats, "tool": executable, "message": "No syntax/compile errors detected." if success else "The language toolchain reported errors."}
        except subprocess.TimeoutExpired:
            return {"language": language, "available": True, "success": False, "diagnostics": [], "stats": stats, "tool": executable, "error": "Syntax check timed out after 10 seconds."}
        except OSError as exc:
            return {"language": language, "available": False, "success": False, "diagnostics": [], "stats": stats, "tool": executable, "error": f"Could not run {executable}: {exc}"}
        finally:
            temp_dir.cleanup()
