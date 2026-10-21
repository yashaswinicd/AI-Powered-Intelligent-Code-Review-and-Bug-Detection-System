from src.bug_detector import BugDetector

tests = {
    "undefined variable": "print(mesage)",
    "used before assignment": 'print(message)\nmessage = "Hello"',
    "valid variable": 'message = "Hello"\nprint(message)',
}

detector = BugDetector()

for name, code in tests.items():
    result = detector.detect(code)
    print("\nTEST:", name)
    print("BUGS:", result["bugs"])
