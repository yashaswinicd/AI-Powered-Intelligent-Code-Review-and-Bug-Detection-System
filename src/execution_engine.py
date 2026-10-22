
import os
import re
import subprocess
import tempfile
import sys


class ExecutionEngine:

    DANGEROUS_PATTERNS = [
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bos\.system\s*\(",
        r"\bsubprocess\.call\s*\(",
        r"\bpickle\.loads\s*\("
    ]

    def is_dangerous(self, code):
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                return pattern
        return None

    def run(self, code, timeout=5, stdin_input=None):

        if not isinstance(code, str):
            return {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": "Code must be a string",
                "error_type": "TypeError",
                "error_line": None
            }

        dangerous = self.is_dangerous(code)

        if dangerous:
            return {
                "success": False,
                "return_code": -2,
                "output": "",
                "error": "Execution blocked: dangerous function detected",
                "error_type": "Security Block",
                "error_line": None
            }

        file_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8"
            ) as f:
                f.write(code)
                file_path = f.name

            result = subprocess.run(
                [sys.executable, file_path],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            stderr = result.stderr.strip()
            stdout = result.stdout.strip()

            if result.returncode == 0:
                return {
                    "success": True,
                    "return_code": result.returncode,
                    "output": stdout,
                    "error": "",
                    "error_type": None,
                    "error_line": None
                }

            error_type = None
            error_line = None
            error_message = stderr

            traceback_matches = re.findall(
                r'File ".*?", line (\d+)',
                stderr
            )

            if traceback_matches:
                error_line = int(traceback_matches[-1])

            if stderr:
                last_line = stderr.splitlines()[-1]
                match = re.match(
                    r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning)):\s*(.*)",
                    last_line
                )

                if match:
                    error_type = match.group(1)
                    error_message = match.group(2)

            return {
                "success": False,
                "return_code": result.returncode,
                "output": stdout,
                "error": error_message,
                "error_type": error_type,
                "error_line": error_line
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": "Execution timeout",
                "error_type": "TimeoutError",
                "error_line": None
            }

        except Exception as e:
            return {
                "success": False,
                "return_code": -1,
                "output": "",
                "error": str(e),
                "error_type": type(e).__name__,
                "error_line": None
            }

        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
