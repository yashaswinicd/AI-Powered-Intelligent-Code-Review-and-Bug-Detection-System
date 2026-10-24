import ast
import os
import sys

import joblib

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from src.bug_detector import BugDetector
from src.code_parser import CodeParser
from src.language_analyzer import LanguageAnalyzer


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

MODEL_PATH = os.path.join(
    BASE_DIR, "saved_models", "code_review_model.pkl"
)

VECTORIZER_PATH = os.path.join(
    BASE_DIR, "saved_models", "vectorizer.pkl"
)


class ReviewEngine:

    def __init__(self):
        self.bug_detector = BugDetector()
        self.code_parser = CodeParser()
        self.language_analyzer = LanguageAnalyzer()

        try:
            self.ml_model = joblib.load(MODEL_PATH)
            self.vectorizer = joblib.load(VECTORIZER_PATH)
            self.ml_available = True
            print("ML model loaded successfully.")
        except Exception:
            self.ml_model = None
            self.vectorizer = None
            self.ml_available = False
            print("ML model unavailable; using rule-based analysis.")

    # ---------------------------------------------------------
    # ML PREDICTION
    # ---------------------------------------------------------

    def ml_predict(self, code):
        if not self.ml_available:
            return None

        try:
            features = self.vectorizer.transform([code])
            prediction = self.ml_model.predict(features)[0]

            confidence = None
            if hasattr(self.ml_model, "predict_proba"):
                probabilities = self.ml_model.predict_proba(features)[0]
                confidence = round(float(max(probabilities)) * 100, 2)

            return {
                "prediction": (
                    "Bug Detected"
                    if prediction == 1
                    else "Code Looks Clean"
                ),
                "confidence": confidence,
                "has_bug": bool(prediction == 1)
            }

        except Exception:
            return None

    # ---------------------------------------------------------
    # NAMING CONVENTIONS
    # ---------------------------------------------------------

    def check_naming_conventions(self, code):
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if (
                    any(char.isupper() for char in name)
                    and "_" not in name
                ):
                    issues.append({
                        "type": "Naming Convention",
                        "line": node.lineno,
                        "severity": "low",
                        "message": (
                            f'Use snake_case instead of camelCase: "{name}"'
                        ),
                        "suggestion": (
                            "Python convention: use snake_case "
                            "for function names."
                        )
                    })

            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                name = node.id
                if (
                    any(char.isupper() for char in name[1:])
                    and "_" not in name
                ):
                    issues.append({
                        "type": "Naming Convention",
                        "line": node.lineno,
                        "severity": "low",
                        "message": (
                            f'Use snake_case instead of camelCase: "{name}"'
                        ),
                        "suggestion": (
                            "Python convention: use snake_case "
                            "for variable names."
                        )
                    })

        # Remove duplicates from repeated AST appearances.
        unique = {}
        for issue in issues:
            key = (issue["type"], issue["line"], issue["message"])
            unique[key] = issue

        return list(unique.values())

    # ---------------------------------------------------------
    # MISSING DOCSTRINGS
    # ---------------------------------------------------------

    def check_missing_docstrings(self, code):
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                if ast.get_docstring(node) is None:
                    issues.append({
                        "type": "Missing Docstring",
                        "line": node.lineno,
                        "severity": "low",
                        "message": f'"{node.name}" has no docstring.',
                        "suggestion": (
                            "Add a docstring explaining its purpose."
                        )
                    })

        return issues

    # ---------------------------------------------------------
    # NESTING / COMPLEXITY
    # ---------------------------------------------------------

    def check_complexity(self, code):
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        nested_types = (
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.Try,
            ast.With,
            ast.AsyncWith
        )

        def walk_body(statements, depth=0):
            for node in statements:
                current_depth = depth

                if isinstance(node, nested_types):
                    current_depth = depth + 1

                    if current_depth > 4:
                        issues.append({
                            "type": "High Complexity",
                            "line": node.lineno,
                            "severity": "medium",
                            "message": (
                                "Code is deeply nested "
                                f"(depth: {current_depth})."
                            ),
                            "suggestion": (
                                "Refactor nested blocks into "
                                "smaller functions."
                            )
                        })

                for field_name in (
                    "body",
                    "orelse",
                    "finalbody"
                ):
                    child = getattr(node, field_name, None)
                    if isinstance(child, list):
                        walk_body(child, current_depth)

                handlers = getattr(node, "handlers", [])
                for handler in handlers:
                    walk_body(handler.body, current_depth)

        walk_body(tree.body)
        return issues

    # ---------------------------------------------------------
    # UNUSED IMPORTS
    # ---------------------------------------------------------

    def check_unused_imports(self, code):
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound_name = alias.asname or alias.name.split(".")[0]
                    imports.append((bound_name, node.lineno))

            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue

                    bound_name = alias.asname or alias.name
                    imports.append((bound_name, node.lineno))

        loaded_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
        }

        for name, line_number in imports:
            if name not in loaded_names:
                issues.append({
                    "type": "Unused Import",
                    "line": line_number,
                    "severity": "low",
                    "message": f'Import "{name}" may be unused.',
                    "suggestion": f"Remove the unused import: {name}."
                })

        return issues

    # ---------------------------------------------------------
    # SEVERITY NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def normalize_severity(issue):
        severity = str(issue.get("severity", "low")).strip().lower()

        aliases = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "moderate": "medium",
            "low": "low",
            "info": "low",
            "informational": "low"
        }

        return aliases.get(severity, "low")

    # ---------------------------------------------------------
    # QUALITY SCORE
    # ---------------------------------------------------------

    def calculate_score(self, all_issues):
        score = 100

        penalties = {
            "critical": 40,
            "high": 20,
            "medium": 8,
            "low": 2
        }

        for issue in all_issues:
            severity = self.normalize_severity(issue)
            score -= penalties[severity]

        return max(0, min(100, score))

    @staticmethod
    def calculate_grade(score):
        if score >= 90:
            return "A - Excellent"
        if score >= 75:
            return "B - Good"
        if score >= 60:
            return "C - Average"
        if score >= 40:
            return "D - Needs Work"
        return "F - Poor"

    # ---------------------------------------------------------
    # MAIN REVIEW
    # ---------------------------------------------------------

    def review(self, code, filename="code.py"):
        stats = self.code_parser.get_code_stats(code)

        is_python = filename.lower().endswith(".py")

        if is_python:
            bug_result = self.bug_detector.detect(code)
        else:
            bug_result = self.language_analyzer.detect(code, filename)
        detected_bugs = bug_result.get("bugs", [])

        review_issues = []
        if is_python:
            review_issues.extend(self.check_naming_conventions(code))
            review_issues.extend(self.check_missing_docstrings(code))
            review_issues.extend(self.check_complexity(code))
            review_issues.extend(self.check_unused_imports(code))

        all_issues = detected_bugs + review_issues

        score = self.calculate_score(all_issues)
        grade = self.calculate_grade(score)
        ml_result = self.ml_predict(code)

        return {
            "filename": filename,
            "stats": stats,
            "score": score,
            "grade": grade,
            "total_issues": len(all_issues),
            "bugs": bug_result,
            "review_issues": review_issues,
            "all_issues": all_issues,
            "ml_prediction": ml_result
        }


if __name__ == "__main__":
    engine = ReviewEngine()

    sample_code = """\
def divide(a, b):
    return a / 0

print(divide(10, 2))
"""

    result = engine.review(sample_code, "test.py")

    print(f"Review Score: {result['score']}/100")
    print(f"Grade: {result['grade']}")
    print(f"Total Issues: {result['total_issues']}")

    for issue in result["all_issues"]:
        print(
            f"{issue.get('severity', 'low')} | "
            f"{issue.get('type')} | "
            f"Line {issue.get('line')}"
        )

    if result["ml_prediction"]:
        print(
            "ML Prediction:",
            result["ml_prediction"]["prediction"]
        )