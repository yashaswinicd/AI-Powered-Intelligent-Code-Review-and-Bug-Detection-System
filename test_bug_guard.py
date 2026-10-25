
from src.bug_detector import BugDetector

detector = BugDetector()

unguarded = """def divide(a, b):
    return a / b
"""

guarded = """def divide(a, b):
    if b == 0:
        raise ValueError("b must not be zero")
    return a / b
"""

print("=== UNGUARDED CODE ===")
print(detector.detect(unguarded))

print("\n=== GUARDED CODE ===")
print(detector.detect(guarded))
