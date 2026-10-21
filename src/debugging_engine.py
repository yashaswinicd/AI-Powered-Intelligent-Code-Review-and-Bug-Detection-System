import ast
import re

from src.bug_detector import BugDetector
from src.security_checker import SecurityChecker


class DebuggingEngine:

    def __init__(self):
        self.fixes = []
        self.max_iterations = 20

    def add_fix(self, bug, old, new, description):
        self.fixes.append({
            "type": bug.get("type"),
            "line": bug.get("line"),
            "description": description,
            "original": old,
            "fixed": new
        })

    # ---------------------------------------------------------
    # ANALYZE CODE
    # ---------------------------------------------------------

    def analyze_all(self, code):
        try:
            bug_result = BugDetector().detect(code)
            normal_bugs = bug_result.get("bugs", [])
        except Exception as exc:
            return [{
                "type": "Analysis Error",
                "line": 1,
                "severity": "high",
                "message": str(exc)
            }]

        try:
            security_result = SecurityChecker().check(code)
            security_bugs = security_result.get(
                "vulnerabilities", []
            )
        except Exception as exc:
            security_bugs = [{
                "type": "Security Analysis Error",
                "line": 1,
                "severity": "high",
                "message": str(exc)
            }]

        combined = []
        seen = set()

        for bug in normal_bugs + security_bugs:
            key = (
                bug.get("type"),
                bug.get("line"),
                bug.get("column"),
                bug.get("message")
            )

            if key not in seen:
                seen.add(key)
                combined.append(bug)

        return combined

    # ---------------------------------------------------------
    # VALIDATE PYTHON
    # ---------------------------------------------------------

    @staticmethod
    def is_valid_python(code):
        try:
            ast.parse(code)
            return True
        except (SyntaxError, ValueError, TypeError):
            return False

    # ---------------------------------------------------------
    # DIVISION BY ZERO
    # ---------------------------------------------------------

    def fix_division(self, code, bug):
        lines = code.splitlines()
        line_number = bug.get("line", 0)

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]

        # Case 1: Literal zero, e.g. return a / 0.
        literal_match = re.fullmatch(
            r"(\s*)return\s+([A-Za-z_]\w*)\s*/\s*0\s*",
            old_line
        )

        if literal_match:
            indentation, numerator = literal_match.groups()

            # Find the enclosing function definition.
            function_line = None

            for i in range(line_number - 2, -1, -1):
                if re.match(r"\s*def\s+\w+\s*\(", lines[i]):
                    function_line = lines[i]
                    break

            if function_line:
                params_match = re.search(
                    r"def\s+\w+\s*\((.*?)\)\s*:",
                    function_line
                )

                if params_match:
                    params = []

                    for param in params_match.group(1).split(","):
                        param = param.strip().split("=")[0].strip()

                        if re.fullmatch(r"[A-Za-z_]\w*", param):
                            params.append(param)

                    # This is a heuristic, not proof of intent.
                    candidates = [
                        param for param in params
                        if param != numerator
                    ]

                    if candidates:
                        divisor = candidates[-1]
                        new_line = (
                            f"{indentation}return "
                            f"{numerator} / {divisor}"
                        )

                        candidate_lines = lines[:]
                        candidate_lines[line_number - 1] = new_line
                        candidate = "\n".join(candidate_lines)

                        if self.is_valid_python(candidate):
                            self.add_fix(
                                bug,
                                old_line,
                                new_line,
                                "Replaced literal zero with the last "
                                "eligible function parameter. "
                                "Review the assumption."
                            )
                            return candidate

            # Cannot safely infer intended divisor.
            return code

        # Case 2: Variable divisor, e.g. return a / b.
        variable_match = re.fullmatch(
            r"(\s*)return\s+(.+?)\s*/\s*([A-Za-z_]\w*)\s*",
            old_line
        )

        if not variable_match:
            return code

        indentation, numerator, divisor = variable_match.groups()

        if line_number >= 2:
            previous = lines[line_number - 2].strip()

            if previous == f"if {divisor} == 0:":
                return code

        replacement = (
            f"{indentation}if {divisor} == 0:\n"
            f"{indentation}    raise ZeroDivisionError("
            '"Cannot divide by zero")\n'
            f"{old_line}"
        )

        candidate_lines = lines[:]
        candidate_lines[line_number - 1] = replacement
        candidate = "\n".join(candidate_lines)

        if not self.is_valid_python(candidate):
            return code

        self.add_fix(
            bug,
            old_line,
            replacement,
            "Added a zero-divisor guard. Review the result."
        )

        return candidate

    # ---------------------------------------------------------
    # OTHER FIXES
    # ---------------------------------------------------------

    def fix_index(self, code, bug):
        return code

    def fix_undefined(self, code, bug):
        return code

    def fix_syntax(self, code, bug):
        lines = code.splitlines()
        line_number = bug.get("line", 1)

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]
        stripped = old_line.strip()

        block_keywords = (
            "if ", "elif ", "else", "for ", "while ",
            "def ", "class ", "try", "except", "finally", "with "
        )

        if not stripped.startswith(block_keywords):
            return code

        if stripped.endswith(":"):
            return code

        candidate_lines = lines[:]
        candidate_lines[line_number - 1] = old_line.rstrip() + ":"
        candidate = "\n".join(candidate_lines)

        if not self.is_valid_python(candidate):
            return code

        self.add_fix(
            bug,
            old_line,
            candidate_lines[line_number - 1],
            "Added a missing colon and validated syntax."
        )

        return candidate

    def fix_eval(self, code, bug):
        return code

    def fix_dangerous_function(self, code, bug):
        return self.fix_eval(code, bug)

    def fix_xss(self, code, bug):
        return code

    # ---------------------------------------------------------
    # APPLY FIX
    # ---------------------------------------------------------

    def apply_fix(self, code, bug):
        bug_type = bug.get("type", "")

        if bug_type == "Division By Zero":
            return self.fix_division(code, bug)

        if bug_type == "Index Out Of Range":
            return self.fix_index(code, bug)

        if bug_type == "Undefined Variable":
            return self.fix_undefined(code, bug)

        if bug_type == "Syntax Error":
            return self.fix_syntax(code, bug)

        if bug_type == "Dangerous Function":
            return self.fix_dangerous_function(code, bug)

        if bug_type == "XSS Vulnerability":
            return self.fix_xss(code, bug)

        return code

    # ---------------------------------------------------------
    # MAIN DEBUGGING ENGINE
    # ---------------------------------------------------------

    def fix(self, code, bugs=None):
        self.fixes = []
        original_code = code

        if not isinstance(code, str):
            return {
                "original_code": code,
                "fixed_code": code,
                "total_fixes": 0,
                "iterations": 0,
                "remaining_bugs": [{
                    "type": "Invalid Input",
                    "line": 1,
                    "severity": "high",
                    "message": "Expected Python source code as a string."
                }],
                "fixes": [],
                "syntax_valid": False,
                "verified": False
            }

        current_code = code

        # Try one conservative syntax repair first.
        if not self.is_valid_python(current_code):
            syntax_bugs = self.analyze_all(current_code)

            for bug in syntax_bugs:
                if bug.get("type") != "Syntax Error":
                    continue

                candidate = self.apply_fix(current_code, bug)

                if (
                    candidate != current_code
                    and self.is_valid_python(candidate)
                ):
                    current_code = candidate
                    break

        # Re-analyze after every accepted change.
        for _ in range(self.max_iterations):
            if not self.is_valid_python(current_code):
                break

            detected_bugs = self.analyze_all(current_code)

            if not detected_bugs:
                break

            changed = False

            for bug in detected_bugs:
                candidate = self.apply_fix(current_code, bug)

                if candidate == current_code:
                    continue

                if not self.is_valid_python(candidate):
                    continue

                current_code = candidate
                changed = True
                break

            if not changed:
                break

        remaining_bugs = self.analyze_all(current_code)
        syntax_valid = self.is_valid_python(current_code)

        # Static verification does not guarantee runtime correctness.
        verified = syntax_valid and len(remaining_bugs) == 0

        return {
            "original_code": original_code,
            "fixed_code": current_code,
            "total_fixes": len(self.fixes),
            "iterations": len(self.fixes),
            "remaining_bugs": remaining_bugs,
            "fixes": self.fixes,
            "syntax_valid": syntax_valid,
            "verified": verified
        }