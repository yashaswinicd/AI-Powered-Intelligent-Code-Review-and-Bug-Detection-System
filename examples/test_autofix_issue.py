from src.debugging_engine import DebuggingEngine

engine = DebuggingEngine()
bug = {
    "type": "Potential Division By Zero",
    "line": 2,
    "severity": "medium",
    "message": "Variable b may be zero when used as a divisor."
}
code = "def divide(a, b):\n    return a / b\n"

result = engine.apply_fix(code, bug)

print("Code unchanged:", result == code)
print("Manual review required:", bug.get("manual_review_required"))
print("Suggestion:", bug.get("suggestion"))
