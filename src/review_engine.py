
import ast
import os
import sys
from pathlib import Path

import joblib

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings
from src.bug_detector import BugDetector
from src.code_parser import CodeParser
from src.language_analyzer import LanguageAnalyzer


def resolve_project_path(path_value):
    """Resolve configured paths relative to the project root."""
    path = Path(path_value)

    if not path.is_absolute():
        path = BASE_DIR / path

    return path.resolve()


# Use the paths configured in config/settings.py
MODEL_PATH = resolve_project_path(settings.MODEL_PATH)
VECTORIZER_PATH = resolve_project_path(settings.VECTORIZER_PATH)


class ReviewEngine:
    def __init__(self):
        self.bug_detector = BugDetector()
        self.code_parser = CodeParser()
        self.language_analyzer = LanguageAnalyzer()

        self.ml_model = None
        self.vectorizer = None
        self.ml_available = False

        self._load_ml_model()

    # ---------------------------------------------------------
    # LOAD ML MODEL
    # ---------------------------------------------------------

    def _load_ml_model(self):
        """Load the configured model and vectorizer safely."""
        if not MODEL_PATH.is_file():
            print(f"ML model file not found: {MODEL_PATH}")
            print("Using rule-based analysis.")
            return

        if not VECTORIZER_PATH.is_file():
            print(f"Vectorizer file not found: {VECTORIZER_PATH}")
            print("Using rule-based analysis.")
            return

        try:
            model = joblib.load(MODEL_PATH)
            vectorizer = joblib.load(VECTORIZER_PATH)

            if not callable(getattr(vectorizer, "transform", None)):
                raise TypeError(
                    "The loaded vectorizer has no transform() method."
                )

            if not callable(getattr(model, "predict", None)):
                raise TypeError(
                    "The loaded ML model has no predict() method."
                )

            self.ml_model = model
            self.vectorizer = vectorizer
            self.ml_available = True

            print(f"ML model loaded: {MODEL_PATH}")
            print(f"Vectorizer loaded: {VECTORIZER_PATH}")

        except Exception as exc:
            self.ml_model = None
            self.vectorizer = None
            self.ml_available = False

            print(f"ML model could not be loaded: {exc}")
            print("Using rule-based analysis.")

    # ---------------------------------------------------------
    # ML PREDICTION
    # ---------------------------------------------------------

    def ml_predict(self, code):
        """Return the model prediction, or None if unavailable."""
        if not self.ml_available:
            return None

        try:
            features = self.vectorizer.transform([code])
            prediction = self.ml_model.predict(features)[0]

            confidence = None

            if callable(
                getattr(self.ml_model, "predict_proba", None)
            ):
                probabilities = self.ml_model.predict_proba(features)[0]
                confidence = round(
                    float(max(probabilities)) * 100,
                    2,
                )

            # Support common numeric and string class labels.
            normalized_prediction = str(prediction).strip().lower()

            bug_labels = {
                "1",
                "true",
                "bug",
                "bug detected",
                "defective",
            }

            clean_labels = {
                "0",
                "false",
                "clean",
                "code looks clean",
                "no bug",
                "no bugs",
            }

            if normalized_prediction in bug_labels:
                has_bug = True
            elif normalized_prediction in clean_labels:
                has_bug = False
            else:
                # Do not guess when the model uses unknown labels.
                return {
                    "prediction": str(prediction),
                    "confidence": confidence,
                    "has_bug": None,
                }

            return {
                "prediction": (
                    "Bug Detected" if has_bug else "Code Looks Clean"
                ),
                "confidence": confidence,
                "has_bug": has_bug,
            }

        except Exception as exc:
            print(f"ML prediction failed: {exc}")
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
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
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
                        ),
                    })

            elif (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Store)
            ):
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
                        ),
                    })

        unique = {}

        for issue in issues:
            key = (
                issue["type"],
                issue["line"],
                issue["message"],
            )
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
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                if ast.get_docstring(node) is None:
                    issues.append({
                        "type": "Missing Docstring",
                        "line": node.lineno,
                        "severity": "low",
                        "message": f'"{node.name}" has no docstring.',
                        "suggestion": (
                            "Add a docstring explaining its purpose."
                        ),
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
            ast.AsyncWith,
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
                            ),
                        })

                for field_name in (
                    "body",
                    "orelse",
                    "finalbody",
                ):
                    child = getattr(node, field_name, None)

                    if isinstance(child, list):
                        walk_body(child, current_depth)

                for handler in getattr(node, "handlers", []):
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
                    "suggestion": f"Remove the unused import: {name}.",
                })

        return issues

    # ---------------------------------------------------------
    # SEVERITY NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def normalize_severity(issue):
        severity = str(
            issue.get("severity", "low")
        ).strip().lower()

        aliases = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "moderate": "medium",
            "low": "low",
            "info": "low",
            "informational": "low",
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
            "low": 2,
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
            review_issues.extend(
                self.check_naming_conventions(code)
            )
            review_issues.extend(
                self.check_missing_docstrings(code)
            )
            review_issues.extend(
                self.check_complexity(code)
            )
            review_issues.extend(
                self.check_unused_imports(code)
            )

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
            "ml_prediction": ml_result,
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

    print("ML available:", engine.ml_available)

    if result["ml_prediction"]:
        print(
            "ML Prediction:",
            result["ml_prediction"]["prediction"],
        )
