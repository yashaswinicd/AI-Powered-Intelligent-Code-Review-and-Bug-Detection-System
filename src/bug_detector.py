import re
import ast
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import BUG_THRESHOLD, SEVERITY_LEVELS

class BugDetector:
    def __init__(self):
        self.bugs_found = []

    # =============================
    # Check Empty Except Blocks
    # =============================
    def check_empty_except(self, code):
        bugs = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if 'except:' in line or 'except Exception:' in line:
                next_line = lines[i] if i < len(lines) else ''
                if 'pass' in next_line:
                    bugs.append({
                        'type': 'Empty Except Block',
                        'line': i,
                        'severity': 'MEDIUM',
                        'message': 'Empty except block found — errors are being silently ignored',
                        'suggestion': 'Add proper error handling or logging'
                    })
        return bugs

    # =============================
    # Check Syntax Errors
    # =============================
    def check_syntax_errors(self, code):
        bugs = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            bugs.append({
                'type': 'Syntax Error',
                'line': e.lineno,
                'severity': 'CRITICAL',
                'message': f'Syntax error: {e.msg}',
                'suggestion': 'Fix the syntax error before running the code'
            })
        return bugs

    # =============================
    # Check Long Functions
    # =============================
    def check_long_functions(self, code, max_lines=50):
        bugs = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_lines = node.end_lineno - node.lineno
                    if func_lines > max_lines:
                        bugs.append({
                            'type': 'Long Function',
                            'line': node.lineno,
                            'severity': 'LOW',
                            'message': f'Function "{node.name}" is too long ({func_lines} lines)',
                            'suggestion': 'Break into smaller functions'
                        })
        except:
            pass
        return bugs

    # =============================
    # Check Hardcoded Passwords
    # =============================
    def check_hardcoded_secrets(self, code):
        bugs = []
        patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded Password'),
            (r'api_key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API Key'),
            (r'secret\s*=\s*["\'][^"\']+["\']', 'Hardcoded Secret'),
        ]
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            for pattern, bug_type in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    bugs.append({
                        'type': bug_type,
                        'line': i,
                        'severity': 'HIGH',
                        'message': f'{bug_type} detected in code',
                        'suggestion': 'Use environment variables instead'
                    })
        return bugs

    # =============================
    # Check Print Statements
    # =============================
    def check_print_statements(self, code):
        bugs = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*print\s*\(', line):
                bugs.append({
                    'type': 'Debug Print Statement',
                    'line': i,
                    'severity': 'LOW',
                    'message': 'Print statement found in code',
                    'suggestion': 'Use logging module instead of print'
                })
        return bugs

    # =============================
    # Check Division by Zero
    # =============================
    def check_division_by_zero(self, code):
        bugs = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                    if isinstance(node.right, ast.Constant) and node.right.value == 0:
                        bugs.append({
                            'type': 'Division by Zero',
                            'line': node.lineno,
                            'severity': 'CRITICAL',
                            'message': 'Division by zero detected — this will crash the program',
                            'suggestion': 'Add a check to ensure the denominator is not zero before dividing'
                        })
        except:
            pass
        return bugs

    # =============================
    # Check Undefined Variables
    # =============================
    def check_undefined_variables(self, code):
        bugs = []
        try:
            tree = ast.parse(code)
        except:
            return bugs

        builtins_set = set(dir(__builtins__)) if not isinstance(__builtins__, dict) else set(__builtins__.keys())

        defined_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    defined_names.add(node.target.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_names.add(node.name)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg in node.args.args:
                        defined_names.add(arg.arg)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    defined_names.add(alias.asname or alias.name.split('.')[0])
            elif isinstance(node, ast.For):
                if isinstance(node.target, ast.Name):
                    defined_names.add(node.target.id)
            elif isinstance(node, ast.With):
                for item in node.items:
                    if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                        defined_names.add(item.optional_vars.id)

        seen = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in defined_names and node.id not in builtins_set:
                    key = (node.id, node.lineno)
                    if key not in seen:
                        seen.add(key)
                        bugs.append({
                            'type': 'Undefined Variable',
                            'line': node.lineno,
                            'severity': 'CRITICAL',
                            'message': f'Variable "{node.id}" is used but never defined',
                            'suggestion': f'Make sure "{node.id}" is defined/assigned before use'
                        })
        return bugs

    # =============================
    # Main Detect Function
    # =============================
    def detect(self, code):
        self.bugs_found = []

        # Run all checks
        self.bugs_found += self.check_syntax_errors(code)
        self.bugs_found += self.check_empty_except(code)
        self.bugs_found += self.check_long_functions(code)
        self.bugs_found += self.check_hardcoded_secrets(code)
        self.bugs_found += self.check_print_statements(code)
        self.bugs_found += self.check_division_by_zero(code)
        self.bugs_found += self.check_undefined_variables(code)

        # Summary
        summary = {
            'total_bugs': len(self.bugs_found),
            'critical': sum(1 for b in self.bugs_found if b['severity'] == 'CRITICAL'),
            'high': sum(1 for b in self.bugs_found if b['severity'] == 'HIGH'),
            'medium': sum(1 for b in self.bugs_found if b['severity'] == 'MEDIUM'),
            'low': sum(1 for b in self.bugs_found if b['severity'] == 'LOW'),
            'bugs': self.bugs_found
        }
        return summary


# =============================
# Test maadalu
# =============================
if __name__ == "__main__":
    detector = BugDetector()

    sample_code = '''
def test():
    password = "admin123"
    try:
        x = 1/0
    except:
        pass
    print("debug")
'''
    result = detector.detect(sample_code)
    print(f"✅ Total bugs found: {result['total_bugs']}")
    for bug in result['bugs']:
        print(f"  [{bug['severity']}] Line {bug['line']}: {bug['type']}")