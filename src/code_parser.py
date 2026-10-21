import ast
import os
import tokenize
from io import BytesIO


class CodeParser:

    LANGUAGE_MAP = {
        ".py": "Python",
        ".js": "JavaScript",
        ".java": "Java",
        ".cpp": "C++",
        ".cc": "C++",
        ".cxx": "C++",
        ".c": "C",
        ".h": "C/C++",
        ".hpp": "C++",
    }

    def detect_language(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        return self.LANGUAGE_MAP.get(ext, "Unknown")

    def get_code_stats(self, code):
        lines = code.splitlines()

        return {
            "total_lines": len(lines),
            "code_lines": sum(
                1 for line in lines if line.strip()
            ),
            "blank_lines": sum(
                1 for line in lines if not line.strip()
            ),
            "characters": len(code),
            "bytes": len(code.encode("utf-8")),
        }

    def parse_python(self, code):
        if not isinstance(code, str):
            return {
                "success": False,
                "error": "Code must be provided as text.",
                "line": None,
                "column": None,
                "error_type": "InputError",
            }

        try:
            tree = ast.parse(code)

            return {
                "success": True,
                "tree": tree,
                "error": None,
                "line": None,
                "column": None,
                "error_type": None,
            }

        except SyntaxError as e:
            return {
                "success": False,
                "tree": None,
                "error": e.msg,
                "line": e.lineno,
                "column": e.offset,
                "error_type": "SyntaxError",
            }

        except (ValueError, TypeError, RecursionError) as e:
            return {
                "success": False,
                "tree": None,
                "error": str(e),
                "line": None,
                "column": None,
                "error_type": type(e).__name__,
            }

    def check_python_tokenization(self, code):
        try:
            list(tokenize.tokenize(
                BytesIO(code.encode("utf-8")).readline
            ))
            return {
                "success": True,
                "error": None,
                "line": None,
                "column": None,
            }

        except (tokenize.TokenError, IndentationError, SyntaxError) as e:
            message = e.args[0] if e.args else str(e)
            location = (
                e.args[1]
                if len(e.args) > 1
                and isinstance(e.args[1], tuple)
                else (None, None)
            )

            return {
                "success": False,
                "error": str(message),
                "line": location[0],
                "column": location[1],
            }