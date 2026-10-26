"""End-to-end processing: detect -> analyse -> fix -> verify -> report data.

``process_code`` is the single entry point used by the web application,
the benchmark and the tests, so all of them exercise the same code path.
"""

import time
import uuid
from collections import Counter, OrderedDict

from config.settings import MAX_CODE_LINES
from src import compiler_check
from src.execution_engine import ExecutionEngine
from src.language_support import detect_language, language_name
from src.universal_fixer import analyze, fix, unified_diff
from utils import stats_store

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
# (points per issue, maximum total penalty for that severity)
_PENALTY = {"critical": (20, 60), "high": (12, 40), "medium": (5, 20),
            "low": (1.5, 10)}

_RESULTS = OrderedDict()
_MAX_RESULTS = 50


def normalise(code):
    if code.startswith("\ufeff"):
        code = code[1:]
    return code.replace("\r\n", "\n").replace("\r", "\n")


def quality_score(issues):
    """Score from 0 to 100. Each severity has a capped penalty so one
    category cannot push a large file straight to zero."""
    counts = Counter(i["severity"] for i in issues)
    penalty = 0.0
    for severity, (points, cap) in _PENALTY.items():
        penalty += min(cap, counts.get(severity, 0) * points)
    score = max(0, round(100 - penalty))
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    return {"score": score, "grade": grade}


def code_stats(code):
    lines = code.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    blank = sum(1 for l in lines if not l.strip())
    return {"total_lines": len(lines), "code_lines": len(lines) - blank,
            "blank_lines": blank, "characters": len(code)}


def _public(issue, status):
    return {
        "type": issue["type"], "line": issue["line"],
        "column": issue["column"], "severity": issue["severity"],
        "category": issue["category"], "message": issue["message"],
        "root_cause": issue["root_cause"], "suggestion": issue["suggestion"],
        "source": issue.get("confirmed_by") or issue["source"],
        "fixable": bool(issue.get("fixable")), "status": status,
    }


def _mark_statuses(original, remaining):
    """An original issue counts as fixed when the same kind of issue no
    longer appears after the repair (matched by rule and message)."""
    left = Counter((i["rule"], i["message"]) for i in remaining)
    result = []
    for issue in original:
        key = (issue["rule"], issue["message"])
        if left[key] > 0:
            left[key] -= 1
            if issue["category"] == "style" and not issue.get("fixable"):
                status = "suggestion"
            else:
                status = "needs manual fix" if not issue.get("fixable") \
                    else "not fixed"
        else:
            status = "fixed"
        result.append(_public(issue, status))
    return result


def _run_checks(code, lang, stdin_input, engine):
    """Execute Python, or compile-check other languages."""
    if lang == "python":
        result = engine.run(code, stdin_input)
        if (not result["success"] and result.get("error_type") == "EOFError"
                and not stdin_input):
            result["success"] = True
            result["note"] = ("The program is waiting for input. Fill in "
                              "'Test Input' to run it completely.")
        result["mode"] = "executed"
        if result.get("error_type") == "BlockedByPolicy":
            result.update(
                success=True, skipped=True,
                note="Not executed: " + result["error"] +
                     " The syntax and logic checks above still apply.")
            result["output"], result["error"] = "", ""
        elif result.get("error_type") in ("ModuleNotFoundError",
                                          "ImportError"):
            result.update(
                success=True, skipped=True,
                note="Not fully executed: the program imports a module "
                     "that is not installed in the sandbox interpreter.")
        return result
    check = compiler_check.check(code, lang)
    if check["available"] and check["conclusive"]:
        ok = bool(check["ok"])
        first = check["errors"][0] if check["errors"] else None
        return {
            "success": ok, "mode": "compiled", "tool": check["tool"],
            "output": (f"{check['tool']}: no compile errors found."
                       if ok else ""),
            "error": "" if ok else "\n".join(
                f"line {e['line']}: {e['message']}" for e in check["errors"]),
            "error_type": None if ok else (first or {}).get("type",
                                                            "Compile Error"),
            "error_line": None if ok else (first or {}).get("line"),
        }
    return {
        "success": True, "mode": "static", "skipped": True,
        "output": ("No compiler for this language was found on this "
                   "machine, so the corrected code was verified with the "
                   "built-in syntax rules only."),
        "error": "", "error_type": None, "error_line": None,
    }


def process_code(code, filename=None, language=None, stdin_input="",
                 apply_fixes=True, use_compilers=True, store=True):
    started = time.time()
    code = normalise(code or "")
    if not code.strip():
        raise ValueError("No code was provided.")
    line_count = code.count("\n") + 1
    if line_count > MAX_CODE_LINES:
        raise ValueError(f"The code has {line_count} lines; the limit is "
                         f"{MAX_CODE_LINES}.")

    lang, confidence, reason = detect_language(code, filename, language)
    original = analyze(code, lang, use_compilers)
    original_all = original["issues"] + original["review_issues"]

    if apply_fixes:
        repaired = fix(code, lang, use_compilers)
        fixed_code, fixes = repaired["fixed_code"], repaired["fixes"]
        partial = repaired["partial"]
        after = analyze(fixed_code, lang, use_compilers)
    else:
        fixed_code, fixes, partial, after = code, [], False, original
    after_all = after["issues"] + after["review_issues"]

    issues = _mark_statuses(original_all, after_all if apply_fixes
                            else original_all)
    if not apply_fixes:
        for item in issues:
            item["status"] = "found"
    issues.sort(key=lambda i: (i["line"], _SEVERITY_ORDER[i["severity"]]))
    remaining = [_public(i, "suggestion" if i["category"] == "style"
                         and not i.get("fixable") else
                         "needs manual fix" if not i.get("fixable")
                         else "not fixed") for i in after_all]
    remaining.sort(key=lambda i: (i["line"], _SEVERITY_ORDER[i["severity"]]))

    engine = ExecutionEngine()
    execution = _run_checks(fixed_code, lang, stdin_input, engine) \
        if apply_fixes else None
    original_execution = None
    if apply_fixes and lang == "python" and fixed_code != code:
        original_execution = engine.run(code, stdin_input)

    syntax_left = [i for i in after["issues"] if i["category"] == "syntax"]
    blocking = [i for i in remaining
                if i["severity"] in ("critical", "high")
                and i["status"] != "suggestion"]
    if not apply_fixes:
        verification = {"verified": False,
                        "message": "Analysis only. Run Debug to fix."}
    else:
        runs_ok = bool(execution and execution["success"])
        verified = (not syntax_left) and runs_ok
        if verified and not blocking:
            message = "Corrected code passed all checks."
            if execution.get("skipped"):
                message += " (Not executed; verified by static checks.)"
        elif verified:
            message = (f"The corrected code is valid, but {len(blocking)} "
                       "serious issue(s) need a manual fix (see list).")
        elif syntax_left:
            message = (f"{len(syntax_left)} syntax error(s) could not be "
                       "repaired automatically.")
        else:
            message = ("The corrected code still fails at run time. "
                       "See the execution result.")
        verification = {
            "verified": bool(verified), "message": message,
            "syntax_errors_left": len(syntax_left),
            "manual_issues_left": len(blocking),
            "execution_ok": runs_ok,
        }

    elapsed_ms = round((time.time() - started) * 1000)
    ml = None
    if lang == "python":
        try:
            from src.ml_model import RiskModel
            ml = _risk_model().predict(code)
        except Exception:
            ml = None

    result = {
        "success": True,
        "result_id": uuid.uuid4().hex[:12],
        "language": lang, "language_name": language_name(lang),
        "language_confidence": confidence, "language_reason": reason,
        "engines": original["engines"],
        "stats": code_stats(code),
        "original_code": code, "fixed_code": fixed_code,
        "original_issues": issues, "remaining_issues": remaining,
        "original_score": quality_score(original_all),
        "fixed_score": quality_score(after_all),
        "fixes": fixes, "partial": partial,
        "diff": unified_diff(code, fixed_code) if fixed_code != code else "",
        "execution": execution, "original_execution": original_execution,
        "verification": verification, "ml": ml,
        "elapsed_ms": elapsed_ms,
    }
    if store:
        _remember(result)
        try:
            stats_store.record(result["language_name"],
                               result["stats"]["total_lines"], issues,
                               len(fixes), verification["verified"],
                               elapsed_ms)
        except OSError:
            pass
    return result


_MODEL = None


def _risk_model():
    global _MODEL
    if _MODEL is None:
        from src.ml_model import RiskModel
        _MODEL = RiskModel()
    return _MODEL


def _remember(result):
    _RESULTS[result["result_id"]] = result
    while len(_RESULTS) > _MAX_RESULTS:
        _RESULTS.popitem(last=False)


def get_result(result_id):
    return _RESULTS.get(result_id)
