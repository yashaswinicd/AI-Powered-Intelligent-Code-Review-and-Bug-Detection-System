import ast
import re

class PerformanceAnalyzer:
    def __init__(self):
        self.issues = []

    def check_loop_complexity(self, code):
        issues = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('for') or stripped.startswith('while'):
                depth = (len(line) - len(line.lstrip())) // 4
                if depth >= 2:
                    issues.append({
                        'type': 'Nested Loop',
                        'line': i,
                        'severity': 'MEDIUM',
                        'message': f'Nested loop detected at depth {depth}',
                        'suggestion': 'Consider optimizing nested loops'
                    })
        return issues

    def check_string_concatenation(self, code):
        issues = []
        pattern = r'(\w+\s*\+=\s*["\']|\w+\s*=\s*\w+\s*\+\s*["\'])'
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                issues.append({
                    'type': 'String Concatenation',
                    'line': i,
                    'severity': 'LOW',
                    'message': 'String concatenation in loop is slow',
                    'suggestion': 'Use join() or f-strings instead'
                })
        return issues

    def check_global_variables(self, code):
        issues = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('global '):
                issues.append({
                    'type': 'Global Variable',
                    'line': i,
                    'severity': 'LOW',
                    'message': 'Global variable usage detected',
                    'suggestion': 'Avoid globals — pass as parameters instead'
                })
        return issues

    def check_large_functions(self, code):
        issues = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    size = node.end_lineno - node.lineno
                    if size > 30:
                        issues.append({
                            'type': 'Large Function',
                            'line': node.lineno,
                            'severity': 'MEDIUM',
                            'message': f'"{node.name}" has {size} lines',
                            'suggestion': 'Break into smaller functions'
                        })
        except:
            pass
        return issues

    def analyze(self, code):
        self.issues = []
        self.issues += self.check_loop_complexity(code)
        self.issues += self.check_string_concatenation(code)
        self.issues += self.check_global_variables(code)
        self.issues += self.check_large_functions(code)

        return {
            'total_issues': len(self.issues),
            'issues': self.issues
        }

if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    sample = '''
global counter
def big_func():
    for i in range(10):
        for j in range(10):
            result = "hello" + str(i)
'''
    result = analyzer.analyze(sample)
    print(f"✅ Performance issues: {result['total_issues']}")
    for issue in result['issues']:
        print(f"  [{issue['severity']}] {issue['type']} - Line {issue['line']}")