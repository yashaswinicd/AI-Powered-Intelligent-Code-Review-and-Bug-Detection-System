import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_train_model():
    # Run train.py as subprocess
    import subprocess
    result = subprocess.run(
        ['python', 'train.py'],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    assert 'Training Complete' in result.stdout
    print("✅ test_train_model passed!")
    print(result.stdout)

def test_predict():
    # Run predict.py as subprocess
    import subprocess
    result = subprocess.run(
        ['python', 'predict.py'],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    assert result.returncode == 0
    print("✅ test_predict passed!")
    print(result.stdout)

if __name__ == "__main__":
    print("🧪 Running Model Tests...\n")
    test_train_model()
    test_predict()
    print("\n🎉 All model tests passed!")