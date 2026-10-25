
import ast
import re
import difflib

from src.bug_detector import BugDetector
from src.security_checker import SecurityChecker


class DebuggingEngine:
    """Conservative Python debugging and auto-fix engine."""

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
            result = BugDetector().detect(code)
            normal_bugs = result.get("bugs", [])
        except Exception as exc:
            normal_bugs = [{
                "type": "Analysis Error",
                "line": 1,
                "column": 1,
                "severity": "high",
                "message": str(exc),
            }]

        try:
            result = SecurityChecker().check(code)
            security_bugs = result.get("vulnerabilities", [])
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

    @staticmethod
    def replace_line(code, line_number, replacement):
        lines = code.splitlines(keepends=True)

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]
        newline = (
            "\r\n" if old_line.endswith("\r\n")
            else "\n" if old_line.endswith("\n")
            else ""
        )

        lines[line_number - 1] = replacement.rstrip("\r\n") + newline
        return "".join(lines)

    # ---------------------------------------------------------
    # DIVISION BY ZERO
    # ---------------------------------------------------------

    def fix_division(self, code, bug):
        """Never guess a replacement value for a divisor."""
        bug["manual_review_required"] = True
        bug["suggestion"] = (
            "Check that the divisor is non-zero before division. "
            "Automatic repair was not applied because the intended "
            "error-handling behavior cannot be inferred safely."
        )
        return code

    # ---------------------------------------------------------
    # UNDEFINED VARIABLE AUTO-FIX
    # ---------------------------------------------------------

    def fix_undefined(self, code, bug):
        line_number = bug.get("line", 0)

        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError, TypeError, RecursionError):
            return code

        defined_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                defined_names.add(node.id)
            elif isinstance(node, ast.arg):
                defined_names.add(node.arg)
            elif isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                defined_names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    defined_names.add(
                        alias.asname or alias.name.split(".")[0]
                    )

        message = bug.get("message", "")
        match = re.search(
            r"""Variable ['"]([A-Za-z_]\w*)['"]""",
            message,
        )

        if not match:
            return code

        undefined_name = match.group(1)
        defined_names.discard(undefined_name)

        candidates = difflib.get_close_matches(
            undefined_name,
            sorted(defined_names),
            n=2,
            cutoff=0.85,
        )

        # Avoid guessing when multiple names are plausible.
        if len(candidates) != 1:
            bug["manual_review_required"] = True
            bug["suggestion"] = (
                "Review the undefined variable and select the intended "
                "name manually."
            )
            return code

        replacement_name = candidates[0]
        lines = code.splitlines()

        if not 1 <= line_number <= len(lines):
            return code

        old_line = lines[line_number - 1]

        new_line = re.sub(
            rf"\b{re.escape(undefined_name)}\b",
            replacement_name,
            old_line,
        )

        if new_line == old_line:
            return code

        candidate_code = self.replace_line(
            code, line_number, new_line
        )

        if not self.is_valid_python(candidate_code):
            return code

        self.add_fix(
            bug,
            old_line,
            new_line,
            f"Suggested variable-name correction: "
            f"{undefined_name} -> {replacement_name}.",
        )

        return candidate_code

    # ---------------------------------------------------------
    # SYNTAX FIX
    # ---------------------------------------------------------

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

        new_line = old_line.rstrip() + ":"
        candidate = self.replace_line(code, line_number, new_line)

        if candidate == code or not self.is_valid_python(candidate):
            return code

        self.add_fix(
            bug,
            old_line,
            new_line,
            "Added a missing colon and validated Python syntax.",
        )

        return candidate

    # ---------------------------------------------------------
    # OTHER CONSERVATIVE FIXES
    # ---------------------------------------------------------

    def fix_index(self, code, bug):
        bug["manual_review_required"] = True
        bug["suggestion"] = (
            "Check the collection length and index bounds. "
            "Automatic index changes may alter program behavior."
        )
        return code

    def fix_eval(self, code, bug):
        bug["manual_review_required"] = True
        bug["suggestion"] = (
            "Review the use of eval and consider a safer alternative "
            "appropriate for the expected input."
        )
        return code

    def fix_dangerous_function(self, code, bug):
        return self.fix_eval(code, bug)

    def fix_xss(self, code, bug):
        bug["manual_review_required"] = True
        bug["suggestion"] = (
            "Review how untrusted data reaches the output and apply "
            "context-appropriate escaping or sanitization."
        )
        return code

    def apply_fix(self, code, bug):
        bug_type = bug.get("type", "")

        if bug_type in (
            "Division By Zero",
            "Potential Division By Zero",
        ):
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

        # Attempt a conservative syntax repair.
        if not self.is_valid_python(current_code):
            for bug in self.analyze_all(current_code):
                if bug.get("type") != "Syntax Error":
                    continue

                candidate = self.apply_fix(current_code, bug)

                if (
                    candidate != current_code
                    and self.is_valid_python(candidate)
                ):
                    current_code = candidate
                    break

        # Apply only fixes that change the code and preserve valid syntax.
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

        # This is static verification only, not runtime proof.
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
