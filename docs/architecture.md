# Architecture

The system is a Flask web app. Every request goes through one pipeline
(`src/pipeline.py`, function `process_code`).

## Flow

1. **Input**: code is pasted or uploaded in the browser (`templates/`, `static/`).
2. **Language detection**: `language_support.py` picks Python, Java, C, C++ or
   JavaScript from the file extension or from code signatures.
3. **Scanning**: `lexer.py` masks strings and comments so that rules do not
   fire on text inside them.
4. **Analysis**
   - Python: `python_analyzer.py` uses the AST (scope resolver, syntax repair).
   - Other languages: `universal_analyzer.py` (brackets, semicolons, secrets,
     catch blocks, assignment in conditions).
   - All languages: `security_checker.py` (SQL injection, XSS, weak hashes,
     dangerous calls). `compiler_check.py` uses gcc, g++, node or javac when
     they are installed.
5. **Fix and verify**: `universal_fixer.py` applies one repair at a time and
   analyses the code again. A repair that does not help, or that creates a new
   problem, is discarded.
6. **Execution**: only Python is run, in a separate process with time and
   memory limits (`execution_engine.py`). This is a safety net, not a security
   boundary.
7. **Scoring and ML**: a quality score before and after, plus a small ML risk
   estimate (`ml_model.py`). The rule engine is the main detector.
8. **Output**: issues with line numbers, fixes, diff, corrected code and
   TXT / JSON / PDF reports (`report_generator.py`). Dashboard numbers are kept
   by `utils/stats_store.py`.

## Testing

- `tests/test_core.py`: unit tests.
- `tests/run_benchmark.py`: labelled benchmark programs in 5 languages,
  including correct programs that must not be flagged.