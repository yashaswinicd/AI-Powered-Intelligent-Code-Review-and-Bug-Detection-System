
import ast
import re


class SecurityChecker:
    """Rule-based security checks for source code."""

    def __init__(self):
        self.vulnerabilities = []

    @staticmethod
    def _add_issue(issues, issue_type, line, severity, message, suggestion):
        issues.append({
            "type": issue_type,
            "line": line,
            "severity": severity,
            "message": message,
            "suggestion": suggestion,
        })

    # ---------------------------------------------------------
    # SQL INJECTION
    # ---------------------------------------------------------
    def check_sql_injection(self, code):
        issues = []
        sql_keywords = re.compile(
            r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|UNION)\b",
            re.IGNORECASE,
        )

        dynamic_patterns = [
            re.compile(r"""f\s*["']""", re.IGNORECASE),
            re.compile(r"""["'][^"']*["']\s*\+\s*[A-Za-z_]"""),
            re.compile(r"""\+\s*[A-Za-z_]\w*\s*\+\s*["']"""),
            re.compile(r"""["'][^"']*["']\s*%\s*[A-Za-z_(]"""),
            re.compile(r"""\.format\s*\("""),
        ]

        for line_number, line in enumerate(code.splitlines(), 1):
            if not sql_keywords.search(line):
                continue

            if any(pattern.search(line) for pattern in dynamic_patterns):
                self._add_issue(
                    issues,
                    "SQL Injection Risk",
                    line_number,
                    "CRITICAL",
                    "SQL statement may include dynamically concatenated "
                    "or formatted input.",
                    "Use parameterized queries instead of building SQL "
                    "with string concatenation or formatting.",
                )

        return issues

    # ---------------------------------------------------------
    # CROSS-SITE SCRIPTING (XSS)
    # ---------------------------------------------------------
    def check_xss(self, code):
        issues = []
        patterns = [
            r"\binnerHTML\s*=",
            r"\bdocument\.write\s*\(",
            r"\binsertAdjacentHTML\s*\(",
        ]

        for line_number, line in enumerate(code.splitlines(), 1):
            if any(re.search(p, line, re.IGNORECASE) for p in patterns):
                self._add_issue(
                    issues,
                    "XSS Vulnerability",
                    line_number,
                    "HIGH",
                    "Potential unsafe HTML insertion sink detected.",
                    "Avoid inserting untrusted data as HTML. Prefer "
                    "textContent or use a suitable HTML sanitizer.",
                )

        return issues

    # ---------------------------------------------------------
    # WEAK CRYPTOGRAPHY
    # ---------------------------------------------------------
    def check_weak_crypto(self, code):
        issues = []
        patterns = [
            (r"\bmd5\b", "MD5"),
            (r"\bsha1\b", "SHA1"),
            (r"\bdes\b", "DES"),
            (r"\brc4\b", "RC4"),
        ]

        for line_number, line in enumerate(code.splitlines(), 1):
            for pattern, algorithm in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self._add_issue(
                        issues,
                        "Weak Cryptography",
                        line_number,
                        "HIGH",
                        f'Potential use of weak algorithm "{algorithm}".',
                        "Choose a modern cryptographic algorithm suitable "
                        "for the task. Passwords should use a password "
                        "hashing algorithm such as Argon2id or bcrypt.",
                    )
                    break

        return issues

    # ---------------------------------------------------------
    # HARDCODED IP ADDRESSES
    # ---------------------------------------------------------
    def check_hardcoded_ips(self, code):
        issues = []
        ip_pattern = (
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        )

        for line_number, line in enumerate(code.splitlines(), 1):
            for match in re.finditer(ip_pattern, line):
                ip = match.group(0)

                if ip in {"127.0.0.1", "0.0.0.0"}:
                    continue

                octets = ip.split(".")
                if not all(0 <= int(part) <= 255 for part in octets):
                    continue

                self._add_issue(
                    issues,
                    "Hardcoded IP Address",
                    line_number,
                    "MEDIUM",
                    f"Hardcoded IP address detected: {ip}.",
                    "Move environment-specific addresses into configuration "
                    "or environment variables when appropriate.",
                )
                break

        return issues

    # ---------------------------------------------------------
    # DANGEROUS FUNCTIONS
    # ---------------------------------------------------------
    def check_dangerous_functions(self, code):
        issues = []

        patterns = [
            (
                r"\beval\s*\(",
                "Code injection risk via eval().",
                "Avoid eval() on untrusted input. Prefer explicit parsing "
                "or a restricted data format.",
            ),
            (
                r"\bexec\s*\(",
                "Dynamic code execution risk via exec().",
                "Avoid executing dynamically constructed code, especially "
                "when it contains untrusted input.",
            ),
            (
                r"\bos\.system\s*\(",
                "Potential shell command injection via os.system().",
                "Prefer subprocess APIs with argument lists and avoid "
                "passing untrusted input to a shell.",
            ),
            (
                r"\bsubprocess\.(?:call|run|Popen)\s*\(",
                "Subprocess execution requires security review.",
                "Avoid shell=True with untrusted input and validate "
                "arguments carefully.",
            ),
            (
                r"\bpickle\.loads?\s*\(",
                "Unsafe deserialization risk via pickle.",
                "Never unpickle data from untrusted sources. Use a safer "
                "data format when possible.",
            ),
        ]

        for line_number, line in enumerate(code.splitlines(), 1):
            for pattern, message, suggestion in patterns:
                if re.search(pattern, line):
                    self._add_issue(
                        issues,
                        "Dangerous Function",
                        line_number,
                        "HIGH",
                        message,
                        suggestion,
                    )

        return issues

    # ---------------------------------------------------------
    # OPEN REDIRECTS
    # ---------------------------------------------------------
    def check_open_redirects(self, code):
        issues = []
        patterns = [
            r"\bredirect\s*\(\s*request\.",
            r"\bredirect\s*\(\s*url_for\s*\([^)]*request\.",
        ]

        for line_number, line in enumerate(code.splitlines(), 1):
            if any(re.search(p, line, re.IGNORECASE) for p in patterns):
                self._add_issue(
                    issues,
                    "Open Redirect",
                    line_number,
                    "MEDIUM",
                    "Possible redirect using request-controlled data.",
                    "Validate redirect destinations against trusted local "
                    "URLs or an allowlist.",
                )

        return issues

    # ---------------------------------------------------------
    # MAIN CHECK
    # ---------------------------------------------------------
    def check(self, code):
        if not isinstance(code, str):
            code = ""

        issues = []
        checks = [
            self.check_sql_injection,
            self.check_xss,
            self.check_weak_crypto,
            self.check_hardcoded_ips,
            self.check_dangerous_functions,
            self.check_open_redirects,
        ]

        for check_function in checks:
            issues.extend(check_function(code))

        self.vulnerabilities = issues

        return {
            "total_vulnerabilities": len(issues),
            "critical": sum(
                issue["severity"] == "CRITICAL" for issue in issues
            ),
            "high": sum(
                issue["severity"] == "HIGH" for issue in issues
            ),
            "medium": sum(
                issue["severity"] == "MEDIUM" for issue in issues
            ),
            "vulnerabilities": issues,
        }


if __name__ == "__main__":
    checker = SecurityChecker()

    sample_code = '''
username = input("Username: ")
query = "SELECT * FROM users WHERE username = '" + username + "'"
eval(username)
element.innerHTML = username
'''

    result = checker.check(sample_code)

    print("Security Check Complete!")
    print("Total vulnerabilities:", result["total_vulnerabilities"])

    for issue in result["vulnerabilities"]:
        print(
            f"[{issue['severity']}] "
            f"Line {issue['line']}: {issue['type']} - "
            f"{issue['message']}"
        )
