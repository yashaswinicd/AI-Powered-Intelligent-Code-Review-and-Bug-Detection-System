"""Measure detection and repair quality on the labelled test programs.

Run from the project root:   python -m tests.run_benchmark

The benchmark uses the built-in rule engine only (compilers are switched
off), so the numbers are the same on every machine. The result is written
to outputs/benchmark.json and shown on the dashboard.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import BENCHMARK_PATH  # noqa: E402
from src.pipeline import process_code  # noqa: E402
from tests.benchmark_cases import CASES  # noqa: E402

# Style suggestions are reported to the user but are not "bugs", so they are
# left out of the accuracy numbers.
STYLE_TYPES = {
    "Loose Equality", "Missing Docstring", "Naming Convention",
    "Unused Import", "Comparison With None", "High Complexity", "Long Line",
    "Pending Task Comment", "Long Function", "Too Many Parameters",
}


def run(verbose=True):
    tp = fp = fn = 0
    clean_files = false_positive_files = 0
    fixable_cases = fix_ok = 0
    failures = []
    started = time.time()

    for name, lang, code, expected in CASES:
        result = process_code(code, language=lang, use_compilers=False,
                              store=False)
        found = {i["type"] for i in result["original_issues"]
                 if i["type"] not in STYLE_TYPES}
        want = set(expected)
        tp += len(found & want)
        fp += len(found - want)
        fn += len(want - found)

        if not want:
            clean_files += 1
            if found:
                false_positive_files += 1
        if found != want:
            failures.append((name, sorted(want), sorted(found)))

        if want and want & found:
            fixable_cases += 1
            syntax_expected = "Syntax Error" in want
            repaired = result["verification"]["syntax_errors_left"] == 0
            if not syntax_expected or repaired:
                fix_ok += 1
            else:
                failures.append((name + " (fix)", ["syntax repaired"],
                                 ["syntax errors left"]))

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    report = {
        "mode": "rule engine only (no compiler)",
        "cases": len(CASES),
        "languages": sorted({c[1] for c in CASES}),
        "clean_files": clean_files,
        "false_positive_files": false_positive_files,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fix_success_rate": round(fix_ok / fixable_cases, 4)
        if fixable_cases else 1.0,
        "seconds": round(time.time() - started, 2),
    }
    os.makedirs(os.path.dirname(BENCHMARK_PATH), exist_ok=True)
    with open(BENCHMARK_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    if verbose:
        print(json.dumps(report, indent=2))
        for name, want, found in failures:
            print(f"MISMATCH {name}: expected {want}, got {found}")
    return report, failures


if __name__ == "__main__":
    run()
