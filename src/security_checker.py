"""Rule-based security checks that work on any language.

The checks read the source with comments removed (so a comment such as
"# do not use md5" is not reported) and report precise line numbers.
Where a safe mechanical correction exists the issue carries an ``edit``.
"""

import re

from src.lexer import scan
from src.language_support import LANGUAGES
from src.universal_analyzer import make_issue

_SQL_STATEMENT = re.compile(
    r"\b(?:SELECT\b[^;\"']*\bFROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|"
    r"DELETE\s+FROM|DROP\s+(?:TABLE|DATABASE)|ALTER\s+TABLE|"
    r"CREATE\s+TABLE|UNION\s+(?:ALL\s+)?SELECT)\b", re.IGNORECASE)

_SQL_DYNAMIC = [
    re.compile(r"""\bf\s*["']"""),                      # Python f-string
    re.compile(r"""["'][^"']*["']\s*\+\s*[A-Za-z_(]"""),  # "..." + var
    re.compile(r"""\+\s*[A-Za-z_]\w*\s*\+\s*["']"""),   # + var + "..."
    re.compile(r"""["'][^"']*["']\s*%\s*[A-Za-z_(]"""),  # "..." % var
    re.compile(r"\.format\s*\("),
    re.compile(r"\$\{"),                                # JS template
    re.compile(r"%[sd]\b"),                             # printf style
    re.compile(r"\bString\s*\.\s*format\s*\(|\bSprintf\s*\("),
]


class SecurityChecker:
    """Detect common vulnerabilities in source code."""

    def __init__(self):
        self.vulnerabilities = []

    @staticmethod
    def _issue(issues, type_, line, severity, message, suggestion,
               column=1, edit=None, rule=None):
        issues.append(make_issue(
            type_, line, severity, message, suggestion, column=column,
            category="security", edit=edit, rule=rule,
            root_cause=message))

    # SQL injection ---------------------------------------------------
    def check_sql_injection(self, lines, **_):
        issues = []
        for n, line in enumerate(lines, 1):
            if not _SQL_STATEMENT.search(line):
                continue
            if any(p.search(line) for p in _SQL_DYNAMIC):
                self._issue(
                    issues, "SQL Injection Risk", n, "critical",
                    "SQL statement is built from concatenated or "
                    "formatted input.",
                    "Use parameterized queries (placeholders) instead of "
                    "building SQL with strings.", rule="sql_injection")
        return issues

    # XSS -------------------------------------------------------------
    def check_xss(self, lines, starts, **_):
        issues = []
        for n, line in enumerate(lines, 1):
            m = re.search(r"\.innerHTML\s*=(?!=)", line)
            if m:
                s = starts[n - 1] + m.start()
                self._issue(
                    issues, "XSS Vulnerability", n, "high",
                    "Assigning to innerHTML inserts text as HTML.",
                    "Use textContent for plain text, or sanitize the "
                    "HTML first.", column=m.start() + 1,
                    edit={"start": s, "end": m.end() + starts[n - 1] - 1,
                          "text": ".textContent ="},
                    rule="xss_innerhtml")
            elif re.search(r"\bdocument\.write\s*\(|\binsertAdjacentHTML\s*\(",
                           line):
                self._issue(
                    issues, "XSS Vulnerability", n, "high",
                    "Writing raw HTML into the page can run attacker "
                    "scripts.",
                    "Create elements and set textContent instead.",
                    rule="xss_write")
        return issues

    # weak hashes -----------------------------------------------------
    def check_weak_crypto(self, lines, starts, **_):
        issues = []
        for n, line in enumerate(lines, 1):
            edit = None
            algorithm = None
            m = re.search(r"\bhashlib\s*\.\s*(md5|sha1)\s*\(", line)
            if m:
                algorithm = m.group(1).upper()
                a = starts[n - 1] + m.start(1)
                edit = {"start": a, "end": a + len(m.group(1)),
                        "text": "sha256"}
            if not algorithm:
                m = re.search(r"getInstance\(\s*[\"'](MD5|SHA-?1|MD2|DES|"
                              r"DESede|RC4)[\"']", line)
                if m:
                    algorithm = m.group(1)
                    if algorithm.upper() in ("MD5", "SHA1", "SHA-1"):
                        a = starts[n - 1] + m.start(1)
                        edit = {"start": a, "end": a + len(algorithm),
                                "text": "SHA-256"}
            if not algorithm:
                m = re.search(r"createHash\(\s*['\"](md5|sha1)['\"]", line)
                if m:
                    algorithm = m.group(1).upper()
                    a = starts[n - 1] + m.start(1)
                    edit = {"start": a, "end": a + len(m.group(1)),
                            "text": "sha256"}
            if not algorithm:
                m = re.search(r"\b(MD5|SHA1|RC4)\s*(?:\(|::|\.)|\bDES(?:ede)?\b"
                              r"(?=\s*[(.:\"'])", line)
                if m:
                    algorithm = (m.group(1) or "DES")
            if algorithm:
                self._issue(
                    issues, "Weak Cryptography", n, "high",
                    f'Weak algorithm "{algorithm}" is used.',
                    "Use SHA-256 or stronger. Passwords need a password "
                    "hashing function such as bcrypt or Argon2id.",
                    column=m.start() + 1, edit=edit, rule="weak_crypto")
        return issues

    # hard-coded IP ---------------------------------------------------
    def check_hardcoded_ips(self, lines, **_):
        issues = []
        pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        for n, line in enumerate(lines, 1):
            if re.search(r"version|v\d|\.\d+\.\d+\.\d+\.\d+\s*[a-z]", line,
                         re.IGNORECASE):
                continue
            for m in pattern.finditer(line):
                ip = m.group(0)
                if ip in ("127.0.0.1", "0.0.0.0", "255.255.255.255"):
                    continue
                if not all(0 <= int(p) <= 255 for p in ip.split(".")):
                    continue
                self._issue(
                    issues, "Hardcoded IP Address", n, "medium",
                    f"Hard-coded IP address {ip}.",
                    "Move addresses into configuration or environment "
                    "variables.", column=m.start() + 1, rule="hardcoded_ip")
                break
        return issues

    # dangerous calls -------------------------------------------------
    def check_dangerous_functions(self, lines, lang, **_):
        issues = []
        patterns = [
            (r"(?<![\w.])exec\s*\(", "Dynamic code execution via exec().",
             "Avoid executing dynamically built code.", "high",
             {"python"}),
            (r"(?<![\w.])eval\s*\(", "Code injection risk via eval().",
             "Avoid eval(); parse the data explicitly.", "high",
             {"javascript", "c", "cpp", "java"}),
            (r"\bos\s*\.\s*system\s*\(", "Shell command injection via "
             "os.system().", "Use subprocess with an argument list.",
             "high", {"python"}),
            (r"\bsubprocess\s*\.\s*(?:call|run|Popen|check_output)\s*\([^)]*"
             r"shell\s*=\s*True", "subprocess with shell=True allows "
             "command injection.", "Pass an argument list and omit "
             "shell=True.", "high", {"python"}),
            (r"\bpickle\s*\.\s*loads?\s*\(", "Unsafe deserialization via "
             "pickle.", "Never unpickle untrusted data; use JSON.",
             "high", {"python"}),
            (r"\byaml\s*\.\s*load\s*\((?![^)]*Loader\s*=\s*(?:yaml\.)?"
             r"SafeLoader)", "yaml.load() can construct arbitrary objects.",
             "Use yaml.safe_load().", "high", {"python"}),
        ]
        for n, line in enumerate(lines, 1):
            for pattern, message, suggestion, severity, langs in patterns:
                if lang in langs and re.search(pattern, line):
                    self._issue(issues, "Dangerous Function", n, severity,
                                message, suggestion, rule="dangerous_call")
        return issues

    # open redirects --------------------------------------------------
    def check_open_redirects(self, lines, **_):
        issues = []
        pattern = re.compile(r"\bredirect\s*\(\s*request\.|"
                             r"\bredirect\s*\(\s*url_for\s*\([^)]*request\.",
                             re.IGNORECASE)
        for n, line in enumerate(lines, 1):
            if pattern.search(line):
                self._issue(
                    issues, "Open Redirect", n, "medium",
                    "Redirect target comes from the request.",
                    "Validate the destination against an allow-list.",
                    rule="open_redirect")
        return issues

    # entry point -----------------------------------------------------
    def check(self, code, lang="python"):
        if not isinstance(code, str):
            code = ""
        if lang not in LANGUAGES:
            lang = "python"
        sc = scan(code, lang)
        text = sc.no_comments
        lines = text.split("\n")
        starts = [0]
        for l in lines[:-1]:
            starts.append(starts[-1] + len(l) + 1)

        issues = []
        for check in (self.check_sql_injection, self.check_xss,
                      self.check_weak_crypto, self.check_hardcoded_ips,
                      self.check_dangerous_functions,
                      self.check_open_redirects):
            issues.extend(check(lines=lines, starts=starts, lang=lang))

        self.vulnerabilities = issues
        count = lambda sev: sum(i["severity"] == sev for i in issues)
        return {
            "total_vulnerabilities": len(issues),
            "critical": count("critical"),
            "high": count("high"),
            "medium": count("medium"),
            "vulnerabilities": issues,
        }
