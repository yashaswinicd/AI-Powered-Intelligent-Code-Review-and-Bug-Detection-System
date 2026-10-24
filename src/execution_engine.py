
import os
import re
import subprocess
import tempfile
import sys
from pathlib import Path


class ExecutionEngine:
    """Execute Python and Java code with a timeout.

    WARNING: A subprocess timeout is not a security sandbox.
    Run only trusted code unless externally isolated.
    """

    DANGEROUS_PATTERNS = [
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bos\s*\.\s*system\s*\(",
        r"\bsubprocess\s*\.\s*(?:call|run|Popen)\s*\(",
        r"\bpickle\s*\.\s*loads?\s*\(",
    ]

    @staticmethod
    def _result(
        success,
        return_code,
        output="",
        error="",
        error_type=None,
        error_line=None,
    ):
        return {
            "success": success,
            "return_code": return_code,
            "output": output,
            "error": error,
            "error_type": error_type,
            "error_line": error_line,
        }

    def is_dangerous(self, code):
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                return pattern
        return None

    def _run_python(self, code, timeout, stdin_input):
        file_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as file:
                file.write(code)
                file_path = file.name

            result = subprocess.run(
                [sys.executable, file_path],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0:
                return self._result(
                    True,
                    result.returncode,
                    output=stdout,
                )

            line_matches = re.findall(
                r'File ".*?", line (\d+)',
                stderr,
            )
            error_line = (
                int(line_matches[-1]) if line_matches else None
            )

            error_type = None
            error_message = stderr

            if stderr:
                last_line = stderr.splitlines()[-1]
                match = re.match(
                    r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning)):\s*(.*)",
                    last_line,
                )
                if match:
                    error_type = match.group(1)
                    error_message = match.group(2)

            return self._result(
                False,
                result.returncode,
                output=stdout,
                error=error_message,
                error_type=error_type,
                error_line=error_line,
            )

        except subprocess.TimeoutExpired:
            return self._result(
                False,
                -1,
                error="Execution timeout.",
                error_type="TimeoutError",
            )

        except Exception as exc:
            return self._result(
                False,
                -1,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

    def _run_java(self, code, timeout, stdin_input, filename):
        class_name = Path(filename).stem

        if not re.fullmatch(
            r"[A-Za-z_$][A-Za-z0-9_$]*",
            class_name,
        ):
            return self._result(
                False,
                -1,
                error="Invalid Java filename/class name.",
                error_type="InvalidFilename",
            )

        try:
            with tempfile.TemporaryDirectory(
                prefix="java_runner_"
            ) as temp_dir:
                java_file = os.path.join(
                    temp_dir,
                    class_name + ".java",
                )

                with open(
                    java_file,
                    "w",
                    encoding="utf-8",
                ) as file:
                    file.write(code)

                compile_result = subprocess.run(
                    ["javac", java_file],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )

                if compile_result.returncode != 0:
                    compiler_error = compile_result.stderr.strip()
                    line_match = re.search(
                        rf"{re.escape(class_name)}\.java:(\d+):\s*error:",
                        compiler_error,
                    )

                    return self._result(
                        False,
                        compile_result.returncode,
                        error=(
                            compiler_error
                            or "Java compilation failed."
                        ),
                        error_type="CompilationError",
                        error_line=(
                            int(line_match.group(1))
                            if line_match
                            else None
                        ),
                    )

                run_result = subprocess.run(
                    ["java", "-cp", temp_dir, class_name],
                    cwd=temp_dir,
                    input=stdin_input,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )

                stdout = run_result.stdout.strip()
                stderr = run_result.stderr.strip()

                if run_result.returncode == 0:
                    return self._result(
                        True,
                        0,
                        output=stdout,
                    )

                line_match = re.search(
                    rf"{re.escape(class_name)}\.main\("
                    rf"{re.escape(class_name)}\.java:(\d+)\)",
                    stderr,
                )

                error_type = (
                    "RuntimeError"
                    if "Exception" in stderr
                    or "Error" in stderr
                    else "ExecutionError"
                )

                return self._result(
                    False,
                    run_result.returncode,
                    output=stdout,
                    error=stderr or "Java program failed.",
                    error_type=error_type,
                    error_line=(
                        int(line_match.group(1))
                        if line_match
                        else None
                    ),
                )

        except subprocess.TimeoutExpired:
            return self._result(
                False,
                -1,
                error="Java compilation or execution timeout.",
                error_type="TimeoutError",
            )

        except FileNotFoundError:
            return self._result(
                False,
                -1,
                error="Java compiler/runtime not found. Check JDK PATH.",
                error_type="JavaNotFound",
            )

        except Exception as exc:
            return self._result(
                False,
                -1,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    def run(
        self,
        code,
        timeout=5,
        stdin_input=None,
        filename="code.py",
    ):
        if not isinstance(code, str):
            return self._result(
                False,
                -1,
                error="Code must be a string.",
                error_type="TypeError",
            )

        if stdin_input is not None and not isinstance(
            stdin_input, str
        ):
            return self._result(
                False,
                -1,
                error="Test input must be a string.",
                error_type="TypeError",
            )

        if len(code) > 1_000_000:
            return self._result(
                False,
                -1,
                error="Code exceeds execution size limit.",
                error_type="InputTooLarge",
            )

        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not 0 < timeout <= 10
        ):
            return self._result(
                False,
                -1,
                error="Timeout must be greater than 0 and at most 10 seconds.",
                error_type="InvalidTimeout",
            )

        if not isinstance(filename, str) or not filename.strip():
            return self._result(
                False,
                -1,
                error="A valid filename is required.",
                error_type="InvalidFilename",
            )

        filename = os.path.basename(filename)
        extension = Path(filename).suffix.lower()

        if extension == ".py":
            dangerous = self.is_dangerous(code)

            if dangerous:
                return self._result(
                    False,
                    -2,
                    error=(
                        "Execution blocked by a basic "
                        "dangerous-pattern check."
                    ),
                    error_type="SecurityBlock",
                )

            return self._run_python(
                code,
                timeout,
                stdin_input,
            )

        if extension == ".java":
            return self._run_java(
                code,
                timeout,
                stdin_input,
                filename,
            )

        return self._result(
            False,
            -1,
            error=(
                f"Execution is not supported for "
                f"{extension or 'this file type'}."
            ),
            error_type="Unsupported",
        )
