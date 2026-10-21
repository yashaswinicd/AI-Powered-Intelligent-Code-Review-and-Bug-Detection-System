import ast
import re

from src.bug_detector import BugDetector
from src.security_checker import SecurityChecker


class DebuggingEngine:
    """Conservative Python debugging and source-preserving fix engine."""

    def __init__(self):
        self.fixes = []
        self.max_iterations = 20

    def add_fix(self, bug, old, new, description):
        self.fixes.append({
            "type": bug.get("type"),
            "line": bug.get("line"),
            "description": description,
            "original": old,
            "fixed": new,
        })

    # ---------------------------------------------------------
    # ANALYSIS
    # ---------------------------------------------------------

    def analyze_all(self, code):
        try:
            bug_result = BugDetector().detect(code)
            normal_bugs = bug_result.get("bugs", [])
        except Exception as exc:
            return [{
                "type": "Analysis Error",
                "line": 1,
                "column": 1,
                "severity": "high",
                "message": str(exc),
            }]

        try:
            security_result = SecurityChecker().check(code)
            security_bugs = security_result.get("vulnerabilities", [])
        except Exception as exc:
            security_bugs = [{
                "type": "Security Analysis Error",
                "line": 1,
                "column": 1,
                "severity": "high",
                "message": str(exc),
            }]

        combined = []
        seen = set()

        for bug in normal_bugs + security_bugs:
            key = (
                bug.get("type"),
                bug.get("line"),
                bug.get("column"),
                bug.get("message"),
            )
            if key not in seen:
                seen.add(key)
                combined.append(bug)

        return combined

    @staticmethod
    def is_valid_python(code):
        try:
            ast.parse(code)
            return True
        except (SyntaxError, ValueError, TypeError, RecursionError):
            return False

    # ---------------------------------------------------------
    # SOURCE-PRESERVING LINE REPLACEMENT
    # ---------------------------------------------------------

    @staticmethod
    def replace_line(code, line_number, replacement):
        """Replace one line without discarding the remaining source."""
        lines = code.splitlines(keepends=True)

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]
        newline = "\r\n" if old_line.endswith("\r\n") else (
            "\n" if old_line.endswith("\n") else ""
        )

        lines[line_number - 1] = replacement.rstrip("\r\n") + newline
        return "".join(lines)

    # ---------------------------------------------------------
    # DIVISION BY ZERO
    # ---------------------------------------------------------

    def fix_division(self, code, bug):
        line_number = bug.get("line", 0)
        lines = code.splitlines()

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]

        # A literal zero does not reveal the intended divisor.
        # Never silently replace it with an arbitrary value.
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError, TypeError, RecursionError):
            return code

        target_nodes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Div)
            and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, (int, float))
            and not isinstance(node.right.value, bool)
            and node.right.value == 0
            and getattr(node, "lineno", None) == line_number
        ]

        if target_nodes:
            # Report honestly that human intent is needed.
            bug["manual_review_required"] = True
            bug["suggestion"] = (
                "The divisor is literal zero. Choose the intended non-zero "
                "divisor or add explicit error handling; no value was guessed."
            )
            return code

        # For a variable divisor, a guard may prevent the crash,
        # but it does not infer the application's intended behavior.
        return code

    # ---------------------------------------------------------
    # OTHER FIXES
    # ---------------------------------------------------------

    def fix_index(self, code, bug):
        # Automatic index correction can change intended program behavior.
        return code

    def fix_undefined(self, code, bug):
        # The correct variable name cannot reliably be inferred.
        return code

    def fix_syntax(self, code, bug):
        line_number = bug.get("line", 1)
        lines = code.splitlines()

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]
        stripped = old_line.strip()

        block_keywords = (
            "if ", "elif ", "else", "for ", "while ",
            "def ", "class ", "try", "except", "finally", "with ",
        )

        if not stripped.startswith(block_keywords):
            return code

        if stripped.endswith(":"):
            return code

        candidate = self.replace_line(
            code, line_number, old_line.rstrip() + ":"
        )

        if candidate == code or not self.is_valid_python(candidate):
            return code

        self.add_fix(
            bug,
            old_line,
            candidate.splitlines()[line_number - 1],
            "Added a missing colon and validated Python syntax.",
        )
        return candidate

    def fix_eval(self, code, bug):
        # Replacing eval safely requires knowing the intended data format.
        return code

    def fix_dangerous_function(self, code, bug):
        return self.fix_eval(code, bug)

    def fix_xss(self, code, bug):
        # Correct escaping depends on the output context.
        return code

    # ---------------------------------------------------------
    # APPLY ONE FIX
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
                    "message": "Expected Python source code as a string.",
                }],
                "fixes": [],
                "syntax_valid": False,
                "verified": False,
            }

        original_code = code
        current_code = code

        # One conservative syntax repair attempt.
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

        # Re-analyze after each accepted fix.
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

        # Static analysis alone cannot prove runtime correctness.
        verified = syntax_valid and len(remaining_bugs) == 0

        return {
            "original_code": original_code,
            "fixed_code": current_code,
            "total_fixes": len(self.fixes),
            "iterations": len(self.fixes),
            "remaining_bugs": remaining_bugs,
            "fixes": self.fixes,
            "syntax_valid": syntax_valid,
            "verified": verified,
        }