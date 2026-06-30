import ast
import re

class FeatureExtractor:
    def extract(self, code):
        features = {}
        lines = code.splitlines()

        # Basic features
        features['total_lines'] = len(lines)
        features['blank_lines'] = sum(1 for l in lines if not l.strip())
        features['comment_lines'] = sum(1 for l in lines if l.strip().startswith('#'))
        features['avg_line_length'] = (
            sum(len(l) for l in lines) / len(lines) if lines else 0
        )

        # Code patterns
        features['has_docstring'] = '"""' in code or "'''" in code
        features['has_try_except'] = 'try:' in code
        features['has_print'] = bool(re.search(r'\bprint\s*\(', code))
        features['has_password'] = bool(re.search(
            r'password\s*=\s*["\']', code, re.IGNORECASE
        ))
        features['has_eval'] = 'eval(' in code
        features['has_exec'] = 'exec(' in code

        # AST features
        try:
            tree = ast.parse(code)
            features['num_functions'] = sum(
                1 for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
            )
            features['num_classes'] = sum(
                1 for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef)
            )
            features['num_imports'] = sum(
                1 for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom))
            )
        except:
            features['num_functions'] = 0
            features['num_classes'] = 0
            features['num_imports'] = 0

        return features

if __name__ == "__main__":
    extractor = FeatureExtractor()
    sample = '''
def greet(name):
    """Greet user."""
    print(f"Hello {name}")
'''
    result = extractor.extract(sample)
    print("✅ Features extracted:")
    for k, v in result.items():
        print(f"  {k}: {v}")