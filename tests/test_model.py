import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_train_model():
    result = subprocess.run(
        [sys.executable, "train.py"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "Model trained and saved." in result.stdout


def test_predict(tmp_path):
    sample_file = tmp_path / "sample.py"
    sample_file.write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "predict.py", str(sample_file)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "Prediction output should not be empty"
