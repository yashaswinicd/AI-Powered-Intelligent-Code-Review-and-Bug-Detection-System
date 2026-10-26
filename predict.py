"""Command line helper: python predict.py path/to/file.py"""

import sys

from src.ml_model import RiskModel

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python predict.py <python-file>")
    with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
        print(RiskModel().predict(fh.read()))
