import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.preprocessing import Preprocessor

def test_clean_code():
    preprocessor = Preprocessor()
    code = 'def hello():   \n\n\n\n    pass'
    result = preprocessor.preprocess(code)
    assert result['cleaned_code'] is not None
    print("✅ test_clean_code passed!")

def test_normalize_indentation():
    preprocessor = Preprocessor()
    code = 'def hello():\n\tpass'
    result = preprocessor.preprocess(code)
    assert '\t' not in result['cleaned_code']
    print("✅ test_normalize_indentation passed!")

def test_token_extraction():
    preprocessor = Preprocessor()
    code = 'def add(a, b):\n    return a + b'
    result = preprocessor.preprocess(code)
    assert result['token_count'] > 0
    print(f"✅ test_token_extraction passed! Tokens: {result['token_count']}")

if __name__ == "__main__":
    print("🧪 Running Preprocessing Tests...\n")
    test_clean_code()
    test_normalize_indentation()
    test_token_extraction()
    print("\n🎉 All preprocessing tests passed!")