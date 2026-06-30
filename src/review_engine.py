import os
import sys
import joblib
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bug_detector import BugDetector
from src.code_parser import CodeParser

MODEL_PATH = 'saved_models/code_review_model.pkl'
VECTORIZER_PATH = 'saved_models/vectorizer.pkl'

class ReviewEngine:
    def __init__(self):
        self.bug_detector = BugDetector()
        self.code_parser = CodeParser()
        try:
            self.ml_model = joblib.load(MODEL_PATH)
            self.vectorizer = joblib.load(VECTORIZER_PATH)
            self.ml_available = True
            print("✅ ML Model loaded successfully!")
        except:
            self.ml_available = False
            print("⚠️ ML Model not found, using rule-based analysis")

    # =============================
    # ML Prediction
    # =============================
    def ml_predict(self, code):
        if not self.ml_available:
            return None
        try:
            features = self.vectorizer.transform([code])
            prediction = self.ml_model.predict(features)[0]
            probability = self.ml_model.predict_proba(features)[0]
            return {
                'prediction': 'Bug Detected' if prediction == 1 else 'Code Looks Clean',
                'confidence': round(max(probability) * 100, 2),
                'has_bug': bool(prediction == 1)
            }
        except:
            return None

    # =============================
    # Check Naming Conventions
    # =============================
    def check_naming_conventions(self, code):
        issues = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if '=' in line and not line.strip().startswith('#'):
                words = line.split('=')[0].strip().split()
                if words:
                    var_name = words[-1]
                    if any(c.isupper() for c in var_name[1:]) and '_' not in var_name:
                        issues.append({
                            'type': 'Naming Convention',
                            'line': i,
                            'severity': 'LOW',
                            'message': f'Use snake_case instead of camelCase: "{var_name}"',
                            'suggestion': 'Python convention: use snake_case for variables'
                        })
        return issues

    # =============================
    # Check Missing Docstrings
    # =============================
    def check_missing_docstrings(self, code):
        issues = []
        import ast
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not (node.body and isinstance(node.body[0], ast.Expr)
                            and isinstance(node.body[0].value, ast.Constant)):
                        issues.append({
                            'type': 'Missing Docstring',
                            'line': node.lineno,
                            'severity': 'LOW',
                            'message': f'"{node.name}" has no docstring',
                            'suggestion': 'Add docstring to explain what it does'
                        })
        except:
            pass
        return issues

    # =============================
    # Check Code Complexity
    # =============================
    def check_complexity(self, code):
        issues = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            depth = indent // 4
            if depth > 4:
                issues.append({
                    'type': 'High Complexity',
                    'line': i,
                    'severity': 'MEDIUM',
                    'message': f'Code is too deeply nested (depth: {depth})',
                    'suggestion': 'Refactor to reduce nesting level'
                })
        return issues

    # =============================
    # Check Unused Imports
    # =============================
    def check_unused_imports(self, code):
        issues = []
        import ast
        try:
            tree = ast.parse(code)
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.append((alias.name, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported.append((alias.name, node.lineno))
            for name, lineno in imported:
                if code.count(name) <= 1:
                    issues.append({
                        'type': 'Unused Import',
                        'line': lineno,
                        'severity': 'LOW',
                        'message': f'Import "{name}" may be unused',
                        'suggestion': f'Remove unused import: {name}'
                    })
        except:
            pass
        return issues

    # =============================
    # Generate Review Score
    # =============================
    def calculate_score(self, all_issues):
        score = 100
        for issue in all_issues:
            if issue['severity'] == 'CRITICAL':
                score -= 20
            elif issue['severity'] == 'HIGH':
                score -= 10
            elif issue['severity'] == 'MEDIUM':
                score -= 5
            elif issue['severity'] == 'LOW':
                score -= 2
        return max(0, score)

    # =============================
    # Main Review Function
    # =============================
    def review(self, code, filename="code.py"):
        stats = self.code_parser.get_code_stats(code)
        bug_result = self.bug_detector.detect(code)
        review_issues = []
        review_issues += self.check_naming_conventions(code)
        review_issues += self.check_missing_docstrings(code)
        review_issues += self.check_complexity(code)
        review_issues += self.check_unused_imports(code)
        all_issues = bug_result['bugs'] + review_issues
        score = self.calculate_score(all_issues)

        # ML Prediction
        ml_result = self.ml_predict(code)

        if score >= 90:
            grade = "A - Excellent"
        elif score >= 75:
            grade = "B - Good"
        elif score >= 60:
            grade = "C - Average"
        elif score >= 40:
            grade = "D - Needs Work"
        else:
            grade = "F - Poor"

        return {
            'filename': filename,
            'stats': stats,
            'score': score,
            'grade': grade,
            'total_issues': len(all_issues),
            'bugs': bug_result,
            'review_issues': review_issues,
            'all_issues': all_issues,
            'ml_prediction': ml_result
        }

if __name__ == "__main__":
    engine = ReviewEngine()
    sample_code = '''
import os
import sys

def myFunction():
    password = "secret123"
    try:
        result = 10/0
    except:
        pass
    print("done")
'''
    result = engine.review(sample_code, "test.py")
    print(f"✅ Review Score: {result['score']}/100")
    print(f"📊 Grade: {result['grade']}")
    print(f"🐛 Total Issues: {result['total_issues']}")
    if result['ml_prediction']:
        print(f"🤖 ML Prediction: {result['ml_prediction']['prediction']}")
        print(f"🎯 Confidence: {result['ml_prediction']['confidence']}%")