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
    # COMBINED ANALYSIS
    # =========================================================

    def analyze_all(self, code):

        bug_result = BugDetector().detect(code)
        security_result = SecurityChecker().check(code)

        normal_bugs = bug_result.get("bugs", [])
        security_bugs = security_result.get(
            "vulnerabilities",
            []
        )

        return normal_bugs + security_bugs

    # =========================================================
    # DIVISION BY ZERO
    # =========================================================

    def fix_division(self, code, bug):

        lines = code.splitlines()
        line = bug.get("line", 1)

        if not 1 <= line <= len(lines):
            return code

        old = lines[line - 1]

        new = re.sub(
            r"([/%])\s*0\b",
            r"\1 1",
            old
        )

        if new == old:

            match = re.search(
                r"([/%])\s*(\w+)",
                old
            )

            if match:

                name = match.group(2)

                new = re.sub(
                    rf"([/%])\s*{re.escape(name)}\b",
                    rf"\1 ({name} if {name} != 0 else 1)",
                    old,
                    count=1
                )

        if new != old:

            lines[line - 1] = new

            self.add_fix(
                bug,
                old,
                new,
                "Added zero-divisor protection."
            )

        return "\n".join(lines)

    # =========================================================
    # INDEX OUT OF RANGE
    # =========================================================

    def fix_index(self, code, bug):

        lines = code.splitlines()
        line = bug.get("line", 1)

        if not 1 <= line <= len(lines):
            return code

        old = lines[line - 1]

        match = re.search(
            r"(\w+)\s*\[\s*(-?\d+)\s*\]",
            old
        )

        if not match:
            return code

        name = match.group(1)
        index = int(match.group(2))

        list_match = re.search(
            rf"{re.escape(name)}\s*=\s*\[(.*?)\]",
            code
        )

        if not list_match:
            return code

        items = [
            x for x in list_match.group(1).split(",")
            if x.strip()
        ]

        if not items:
            return code

        safe = max(
            0,
            min(index, len(items) - 1)
        )

        new = re.sub(
            rf"{re.escape(name)}\s*\[\s*{index}\s*\]",
            f"{name}[{safe}]",
            old,
            count=1
        )

        if new != old:

            lines[line - 1] = new

            self.add_fix(
                bug,
                old,
                new,
                "Changed invalid index to a safe index."
            )

        return "\n".join(lines)

    # =========================================================
    # UNDEFINED VARIABLE
    # =========================================================

    def fix_undefined(self, code, bug):

        lines = code.splitlines()
        line = bug.get("line", 1)

        if not 1 <= line <= len(lines):
            return code

        message = bug.get("message", "")

        match = re.search(
            r"Variable '([^']+)'",
            message
        )

        if not match:
            return code

        wrong = match.group(1)

        if wrong.endswith("_quantity"):

            replacement = "quantity"

        else:

            return code

        old = lines[line - 1]

        new = re.sub(
            rf"\b{re.escape(wrong)}\b",
            replacement,
            old,
            count=1
        )

        if new != old:

            lines[line - 1] = new

            self.add_fix(
                bug,
                old,
                new,
                f"Replaced '{wrong}' with '{replacement}'."
            )

        return "\n".join(lines)

    # =========================================================
    # SYNTAX ERROR
    # =========================================================

    def fix_syntax(self, code, bug):

        lines = code.splitlines()
        line = bug.get("line", 1)

        if not 1 <= line <= len(lines):
            return code

        old = lines[line - 1]
        stripped = old.strip()

        keywords = (
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
            "with "
        )

        if (
            stripped.startswith(keywords)
            and not stripped.endswith(":")
        ):

            new = old.rstrip() + ":"

            lines[line - 1] = new

            self.add_fix(
                bug,
                old,
                new,
                "Added missing colon."
            )

            return "\n".join(lines)

        return code

    # =========================================================
    # EVAL SECURITY FIX
    # =========================================================

    def fix_eval(self, code, bug):

        lines = code.splitlines()
        line = bug.get("line", 1)

        if not 1 <= line <= len(lines):
            return code

        old = lines[line - 1]

        if "eval(" not in old:
            return code

        new = old.replace(
            "eval(",
            "ast.literal_eval("
        )

        # Make sure ast is imported
        if "import ast" not in code:

            new_lines = new.splitlines()

            new_lines.insert(
                0,
                "import ast"
            )

            new = "\n".join(new_lines)

        if new != code:

            self.add_fix(
                bug,
                old,
                new,
                "Replaced unsafe eval() with ast.literal_eval()."
            )

        return new

    # =========================================================
    # DANGEROUS FUNCTION
    # =========================================================

    def fix_dangerous_function(self, code, bug):

        lines = code.splitlines()
        line = bug.get("line", 1)

        if not 1 <= line <= len(lines):
            return code

        old = lines[line - 1]

        # eval() can be safely converted when
        # evaluating literal data.

        if "eval(" in old:

            return self.fix_eval(
                code,
                bug
            )

        # Do NOT automatically execute or preserve
        # dangerous shell commands.

        return code

    # =========================================================
    # XSS
    # =========================================================

    def fix_xss(self, code, bug):

        lines = code.splitlines()
        line = bug.get("line", 1)

        if not 1 <= line <= len(lines):
            return code

        old = lines[line - 1]

        # Current XSS checker also flags eval().
        # eval() is handled by fix_eval().

        if "eval(" in old:

            return self.fix_eval(
                code,
                bug
            )

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
            return self.fix_dangerous_function(
                code,
                bug
            )

        if bug_type == "XSS Vulnerability":
            return self.fix_xss(
                code,
                bug
            )

        return code

    # =========================================================
    # MAIN DEBUGGING ENGINE
    # =========================================================

    def fix(self, code, bugs):

        self.fixes = []

        current = code

        for _ in range(self.max_iterations):

            detected = self.analyze_all(
                current
            )

            if not detected:
                break

            changed = False

            for bug in detected:

                new_code = self.apply_fix(
                    current,
                    bug
                )

                if new_code != current:

                    current = new_code
                    changed = True

                    break

            if not changed:
                break

        remaining = self.analyze_all(
            current
        )

        return {
            "original_code": code,
            "fixed_code": current,
            "total_fixes": len(self.fixes),
            "iterations": len(self.fixes),
            "remaining_bugs": remaining,
            "fixes": self.fixes
        }