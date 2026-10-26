# Changelog

## 2.0.0 — Multi-language auto-fix
- Any of 12 languages, up to 50,000 lines; language auto-detection.
- Exact line/column for every issue; problem lines highlighted in the UI.
- One analyse → fix → verify loop shared by all languages.
- Real compilers (gcc, g++, node, javac) used for verification when installed.
- Scope-aware undefined-variable detection for Python (no false alarms for
  comprehensions, lambdas, imports inside functions, `except ... as e`).
- New fixes: missing colon/semicolon, brackets, strings, typos, missing imports,
  hard-coded secrets, empty/bare except, mutable defaults, `== None`, unused
  imports, `eval`, weak hashes, innerHTML, Java string `==`, guarded division.
- Restricted execution sandbox (policy check, isolated process, limits).
- Dashboard shows real statistics; reports (TXT/JSON/PDF) downloadable.
- Labelled benchmark and 27 unit tests.

### Fixed
- `train.py` crashed because `__init__.py` files were named `_init_.py`.
- The ML model was looked up in `saved_models/` instead of `models/`.
- `eval()` was counted twice; security findings are now part of the score.
- Uploaded files are no longer written to disk.
