import ast
import os


class CodeParser:

    def detect_language(self, filename):
        ext = os.path.splitext(filename)[1].lower()

        languages = {
            ".py": "Python",
            ".js": "JavaScript",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C"
        }

        return languages.get(ext, "Unknown")

    def get_code_stats(self, code):
        lines = code.splitlines()

        return {
            "total_lines": len(lines),
            "code_lines": len([
                x for x in lines
                if x.strip()
            ]),
            "characters": len(code)
        }

    def parse_python(self, code):
        try:
            tree = ast.parse(code)

            return {
                "success": True,
                "tree": tree
            }

        except SyntaxError as e:
            return {
                "success": False,
                "error": e.msg,
                "line": e.lineno,
                "column": e.offset
            }