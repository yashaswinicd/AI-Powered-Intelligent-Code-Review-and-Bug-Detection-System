import ast
import re

from src.bug_detector import BugDetector
from src.security_checker import SecurityChecker


class DebuggingEngine:

    def __init__(self):
        self.fixes = []
        self.max_iterations = 20

    # =========================================================
    # RECORD FIX
    # =========================================================

    def add_fix(self, bug, old, new, description):
        self.fixes.append({
            "type": bug.get("type"),
            "line": bug.get("line"),
            "description": description,
            "original": old,
            "fixed": new
        })

    # =========================================================
    # ANALYZE CODE
    # =========================================================

    def analyze_all(self, code):
        try:
            bug_result = BugDetector().detect(code)
        except Exception as exc:
            return [{
                "type": "Analysis Error",
                "line": 1,
                "severity": "high",
                "message": str(exc)
            }]

        normal_bugs = bug_result.get("bugs", [])

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

    # =========================================================
    # VALIDATE PYTHON SYNTAX
    # =========================================================

    @staticmethod
    def is_valid_python(code):
        try:
            ast.parse(code)
            return True
        except (SyntaxError, ValueError, TypeError):
            return False

    # =========================================================
    # DIVISION BY ZERO
    # =========================================================

    def fix_division(self, code, bug):
        # Do not replace 0 with 1 or invent a different result.
        # A correct fix depends on the intended program behavior.
        return code

    # =========================================================
    # INDEX OUT OF RANGE
    # =========================================================

    def fix_index(self, code, bug):
        # Do not silently change the requested index to another
        # element. That could return the wrong result.
        return code

    # =========================================================
    # UNDEFINED VARIABLE
    # =========================================================

    def fix_undefined(self, code, bug):
        # Variable-name guessing can change program semantics.
        # Leave unresolved until the intended name is known.
        return code

    # =========================================================
    # SYNTAX ERROR
    # =========================================================

    def fix_syntax(self, code, bug):
        lines = code.splitlines()
        line_number = bug.get("line", 1)

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]
        stripped = old_line.strip()

        block_keywords = (
            "if ",
            "elif ",
            "else",
            "for ",
            "while ",
            "def ",
            "class ",
            "try",
            "except",
            "finally",
            "with ",
        )

        if not stripped.startswith(block_keywords):
            return code

        if stripped.endswith(":"):
            return code

        candidate_lines = lines[:]
        candidate_lines[line_number - 1] = (
            old_line.rstrip() + ":"
        )
        candidate = "\n".join(candidate_lines)

        # Apply the fix only if the entire file parses afterward.
        if not self.is_valid_python(candidate):
            return code

        self.add_fix(
            bug,
            old_line,
            candidate_lines[line_number - 1],
            "Added a missing colon and validated Python syntax."
        )

        return candidate

    # =========================================================
    # EVAL / DANGEROUS FUNCTION
    # =========================================================

    def fix_eval(self, code, bug):
        # Replacing eval() indiscriminately with literal_eval()
        # can break legitimate expressions. Do not guess.
        return code

    def fix_dangerous_function(self, code, bug):
        return self.fix_eval(code, bug)

    # =========================================================
    # XSS
    # =========================================================

    def fix_xss(self, code, bug):
        # XSS remediation depends on the web framework and
        # whether data is used in HTML, attributes, URLs, etc.
        return code

    # =========================================================
    # APPLY FIX
    # =========================================================

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

    # =========================================================
    # MAIN DEBUGGING ENGINE
    # =========================================================

    def fix(self, code, bugs=None):
        self.fixes = []
        original_code = code
        current_code = code

        # Do not attempt source-code fixes on invalid input
        # until a syntax repair can be safely identified.
        if not self.is_valid_python(current_code):
            syntax_bugs = self.analyze_all(current_code)

            for bug in syntax_bugs:
                if bug.get("type") == "Syntax Error":
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

        # "verified" means the available checks found no remaining
        # issues; it is not proof of full program correctness.
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