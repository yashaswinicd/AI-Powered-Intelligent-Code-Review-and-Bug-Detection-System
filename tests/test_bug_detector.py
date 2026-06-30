import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bug_detector import BugDetector

def test_hardcoded_password():
    detector = BugDetector()
    code = 'password = "admin123"'
    result = detector.detect(code)
    types = [b['type'] for b in result['bugs']]
    assert 'Hardcoded Password' in types
    print("✅ test_hardcoded_password passed!")

def test_empty_except():
    detector = BugDetector()
    code = 'try:\n    pass\nexcept:\n    pass'
    result = detector.detect(code)
    types = [b['type'] for b in result['bugs']]
    assert 'Empty Except Block' in types
    print("✅ test_empty_except passed!")

def test_syntax_error():
    detector = BugDetector()
    code = 'def broken(\n    pass'
    result = detector.detect(code)
    types = [b['type'] for b in result['bugs']]
    assert 'Syntax Error' in types
    print("✅ test_syntax_error passed!")

def test_clean_code():
    detector = BugDetector()
    code = 'def add(a, b):\n    return a + b'
    result = detector.detect(code)
    assert result['total_bugs'] == 0
    print("✅ test_clean_code passed!")

if __name__ == "__main__":
    print("🧪 Running Bug Detector Tests...\n")
    test_hardcoded_password()
    test_empty_except()
    test_syntax_error()
    test_clean_code()
    print("\n🎉 All tests passed!")