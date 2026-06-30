import re
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class SecurityChecker:
    def __init__(self):
        self.vulnerabilities = []

    # =============================
    # Check SQL Injection
    # =============================
    def check_sql_injection(self, code):
        issues = []
        patterns = [
            r'execute\s*\(\s*["\'].*%s',
            r'execute\s*\(\s*f["\']',
            r'cursor\.execute\s*\(.*\+',
        ]
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'type': 'SQL Injection Risk',
                        'line': i,
                        'severity': 'CRITICAL',
                        'message': 'Possible SQL injection vulnerability detected',
                        'suggestion': 'Use parameterized queries instead of string formatting'
                    })
        return issues

    # =============================
    # Check XSS Vulnerability
    # =============================
    def check_xss(self, code):
        issues = []
        patterns = [
            r'innerHTML\s*=',
            r'document\.write\s*\(',
            r'eval\s*\(',
        ]
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'type': 'XSS Vulnerability',
                        'line': i,
                        'severity': 'HIGH',
                        'message': 'Possible Cross-Site Scripting (XSS) vulnerability',
                        'suggestion': 'Sanitize user input before rendering in HTML'
                    })
        return issues

    # =============================
    # Check Weak Cryptography
    # =============================
    def check_weak_crypto(self, code):
        issues = []
        weak_algos = ['md5', 'sha1', 'des', 'rc4']
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            for algo in weak_algos:
                if algo in line.lower():
                    issues.append({
                        'type': 'Weak Cryptography',
                        'line': i,
                        'severity': 'HIGH',
                        'message': f'Weak algorithm "{algo.upper()}" detected',
                        'suggestion': 'Use SHA-256 or stronger algorithms'
                    })
        return issues

    # =============================
    # Check Hardcoded IPs
    # =============================
    def check_hardcoded_ips(self, code):
        issues = []
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if re.search(ip_pattern, line):
                if '127.0.0.1' not in line and '0.0.0.0' not in line:
                    issues.append({
                        'type': 'Hardcoded IP Address',
                        'line': i,
                        'severity': 'MEDIUM',
                        'message': 'Hardcoded IP address found',
                        'suggestion': 'Use config file or environment variables'
                    })
        return issues

    # =============================
    # Check Dangerous Functions
    # =============================
    def check_dangerous_functions(self, code):
        issues = []
        dangerous = {
            'eval(': 'Code injection risk via eval()',
            'exec(': 'Code injection risk via exec()',
            'os.system(': 'Shell injection risk via os.system()',
            'subprocess.call(': 'Shell injection via subprocess',
            'pickle.loads(': 'Unsafe deserialization via pickle',
        }
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            for func, message in dangerous.items():
                if func in line:
                    issues.append({
                        'type': 'Dangerous Function',
                        'line': i,
                        'severity': 'HIGH',
                        'message': message,
                        'suggestion': f'Avoid using {func} with untrusted input'
                    })
        return issues

    # =============================
    # Check Open Redirects
    # =============================
    def check_open_redirects(self, code):
        issues = []
        patterns = [
            r'redirect\s*\(\s*request\.',
            r'redirect\s*\(\s*url_for.*request\.',
        ]
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'type': 'Open Redirect',
                        'line': i,
                        'severity': 'MEDIUM',
                        'message': 'Possible open redirect vulnerability',
                        'suggestion': 'Validate redirect URLs before redirecting'
                    })
        return issues

    # =============================
    # Main Security Check Function
    # =============================
    def check(self, code):
        self.vulnerabilities = []

        self.vulnerabilities += self.check_sql_injection(code)
        self.vulnerabilities += self.check_xss(code)
        self.vulnerabilities += self.check_weak_crypto(code)
        self.vulnerabilities += self.check_hardcoded_ips(code)
        self.vulnerabilities += self.check_dangerous_functions(code)
        self.vulnerabilities += self.check_open_redirects(code)

        summary = {
            'total_vulnerabilities': len(self.vulnerabilities),
            'critical': sum(1 for v in self.vulnerabilities if v['severity'] == 'CRITICAL'),
            'high': sum(1 for v in self.vulnerabilities if v['severity'] == 'HIGH'),
            'medium': sum(1 for v in self.vulnerabilities if v['severity'] == 'MEDIUM'),
            'vulnerabilities': self.vulnerabilities
        }
        return summary


# =============================
# Test maadalu
# =============================
if __name__ == "__main__":
    checker = SecurityChecker()

    sample_code = '''
import hashlib
import pickle
import os

def login(user_input):
    query = "SELECT * FROM users WHERE id = %s" % user_input
    cursor.execute(query)
    hash = hashlib.md5(password.encode())
    eval(user_input)
    os.system("ls " + user_input)
'''
    result = checker.check(sample_code)
    print(f"✅ Security Check Complete!")
    print(f"🔒 Total Vulnerabilities: {result['total_vulnerabilities']}")
    for v in result['vulnerabilities']:
        print(f"  [{v['severity']}] Line {v['line']}: {v['type']}")