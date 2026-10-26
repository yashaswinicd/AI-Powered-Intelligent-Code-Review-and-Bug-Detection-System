"""Analyze and automatically repair code in any supported language.

``analyze`` combines the rule engine with an optional real compiler.
``fix`` repairs the issues that have a safe, mechanical correction and
*verifies every change*: a fix is kept only if the problem is gone and
no new syntax problem appeared. Anything that cannot be fixed safely is
left untouched and reported for manual attention.
"""

import difflib
import re
import time
from collections import Counter

from src import compiler_check, python_analyzer
from src.language_support import LANGUAGES
from src.security_checker import SecurityChecker
from src.universal_analyzer import (SYNTAX_RULES, analyze_text, check_review,
                                    make_issue)

# Lower number = applied first. Syntax must be repaired before anything
# else, because a broken file hides the rest of the problems.
_PRIORITY = {
    "python_syntax": 1,
    "unterminated_comment": 1, "unterminated_string": 1,
    "unterminated_literal": 1, "extra_bracket": 2, "unclosed_bracket": 2,
    "missing_semicolon": 3, "missing_semicolon_after_type": 3,
    "compiler_semicolon": 3,
}
_BATCHABLE = {"missing_semicolon", "missing_semicolon_after_type",
              "hardcoded_secret", "loose_equality", "assignment_in_condition",
              "empty_catch", "java_string_equals", "compiler_semicolon",
              "compare_none", "unused_import", "undefined_variable",
              "xss_innerhtml", "weak_crypto", "dangerous_eval", "bare_except",
              "empty_except", "mutable_default", "is_literal"}


def _is_syntax(issue):
    return issue["category"] == "syntax" or issue["rule"] in SYNTAX_RULES


def _compiler_issue(err, tool, code_lines):
    message = err["message"]
    edit, alt = None, []
    rule = "compiler_error"
    if re.search(r"';' expected|expected ';'|expected ',' or ';'|"
                 r"expected ';' (before|after)", message):
        rule = "compiler_semicolon"
        ln = err["line"]
        candidates = []
        for target in (ln - 1, ln):
            if 1 <= target <= len(code_lines) and code_lines[target - 1].strip():
                candidates.append(target)
        edits = []
        for target in candidates:
            line_text = code_lines[target - 1].rstrip()
            edits.append(("line", target, len(line_text)))
        if edits:
            edit = {"line_end_of": edits[0][1], "text": ";"}
            alt = [{"line_end_of": e[1], "text": ";"} for e in edits[1:]]
    issue = make_issue(
        err["type"], err["line"],
        "critical" if err["type"] == "Syntax Error" else "high",
        message[:1].upper() + message[1:] + ".",
        "Fix the construct reported by the compiler.",
        column=err.get("column", 1), category="syntax"
        if err["type"] == "Syntax Error" else "bug",
        source=tool, edit=None, rule=rule)
    issue["edit"], issue["alt_edits"] = edit, alt
    issue["fixable"] = edit is not None
    return issue


def _dedupe(issues):
    """Drop exact duplicates and keep the fixable one when two engines
    report the same problem on the same line."""
    ordered = sorted(issues, key=lambda i: (not i.get("fixable"),
                                            i["line"], i["column"]))
    seen_rule, seen_type, unique = set(), set(), []
    for issue in ordered:
        k1 = (issue["rule"], issue["line"], issue["column"])
        k2 = (issue["type"], issue["line"])
        cross_engine = issue["category"] != "syntax"
        if k1 in seen_rule or (cross_engine and k2 in seen_type):
            continue
        seen_rule.add(k1)
        seen_type.add(k2)
        unique.append(issue)
    unique.sort(key=lambda i: (i["line"], i["column"]))
    return unique


def analyze(code, lang, use_compilers=True):
    """Full analysis of one source file.

    Returns a dict:
      issues          bugs, syntax errors and security problems
      review_issues   style / maintainability suggestions
      engines         names of the analysers that took part
      compiler        result of the real compiler check (if any)
    """
    compiler = {"available": False}

    if lang == "python":
        base = python_analyzer.analyze_python(code)
        issues, review = base["issues"], base["review_issues"]
        sc, engines = base["scan"], ["Rule engine"] + base["engines"]
    else:
        issues, sc = analyze_text(code, lang)
        engines = ["Rule engine"]
        review = check_review(sc, lang)
        if use_compilers:
            compiler = compiler_check.check(code, lang)
            if compiler["available"] and compiler["conclusive"]:
                engines.append(compiler["tool"])
                if compiler["ok"]:
                    # The compiler accepts the file, so any heuristic
                    # syntax finding is a false alarm.
                    issues = [i for i in issues if not _is_syntax(i)]
                else:
                    code_lines = code.split("\n")
                    heuristic = [i for i in issues if _is_syntax(i)]
                    for err in compiler["errors"]:
                        near = [h for h in heuristic
                                if abs(h["line"] - err["line"]) <= 1]
                        if near:
                            for h in near:
                                h["confirmed_by"] = compiler["tool"]
                            continue
                        issues.append(_compiler_issue(
                            err, compiler["tool"], code_lines))

    security = SecurityChecker().check(code, lang)["vulnerabilities"]
    if security:
        engines.append("Security rules")
    issues = _dedupe(issues + security)
    review = _dedupe(review)
    return {"issues": issues, "review_issues": review, "engines": engines,
            "compiler": compiler, "scan": sc}


def _edit_list(edit):
    if edit is None:
        return []
    return list(edit) if isinstance(edit, list) else [edit]


def _resolve_edit(edit, code):
    """Turn an issue edit into (start, end, text, ensure)."""
    if "line_end_of" in edit:
        lines = code.split("\n")
        ln = edit["line_end_of"]
        if not 1 <= ln <= len(lines):
            return None
        start = sum(len(l) + 1 for l in lines[:ln - 1]) + len(
            lines[ln - 1].rstrip())
        return start, start, edit["text"], edit.get("ensure")
    return edit["start"], edit["end"], edit["text"], edit.get("ensure")


def _ensure_line(code, line, lang):
    """Insert a required import/include near the top if it is missing."""
    if re.search(r"^\s*" + re.escape(line) + r"\s*$", code, re.MULTILINE):
        return code
    lines = code.split("\n")
    pos = 0
    for k, l in enumerate(lines[:40]):
        s = l.strip()
        if s.startswith("#!") or s.startswith("# -*-") or \
                s.startswith("from __future__"):
            pos = k + 1
    if lang == "python":
        # skip a leading module docstring
        m = re.match(r'\s*(?:[rRuU]?("""|\'\'\')[\s\S]*?\1\s*\n)', code)
        if m and pos == 0:
            pos = code[:m.end()].count("\n")
    if lang in ("c", "cpp"):
        last_inc = -1
        for k, l in enumerate(lines):
            if l.strip().startswith("#include"):
                last_inc = k
        pos = last_inc + 1
    lines.insert(pos, line)
    return "\n".join(lines)


def apply_edits(code, edits, lang):
    """Apply non-overlapping edits (resolved against ``code``)."""
    resolved = []
    for edit in edits:
        r = _resolve_edit(edit, code)
        if r:
            resolved.append(r)
    resolved.sort(key=lambda r: (r[0], r[1]), reverse=True)
    out = code
    last_start = None
    ensures = []
    for start, end, text, ensure in resolved:
        if last_start is not None and end > last_start:
            continue  # overlaps a later edit, skip it
        out = out[:start] + text + out[end:]
        last_start = start
        if ensure:
            ensures.append(ensure)
    for line in dict.fromkeys(ensures):
        out = _ensure_line(out, line, lang)
    return out


def _syntax_count(result):
    return sum(1 for i in result["issues"] if _is_syntax(i))


def _describe(issue, original_line, new_line):
    return {
        "type": issue["type"], "line": issue["line"],
        "description": issue["suggestion"],
        "original": original_line, "fixed": new_line,
    }


def fix(code, lang, use_compilers=True, time_budget=25.0, max_rounds=60):
    """Repair ``code``. Returns the corrected code and a log of fixes."""
    started = time.time()
    current = code
    fixes = []
    rejected = set()
    state = analyze(current, lang, use_compilers)
    rounds = 0
    partial = False

    while rounds < max_rounds:
        rounds += 1
        if time.time() - started > time_budget:
            partial = True
            break

        everything = state["issues"] + state["review_issues"]
        candidates = [i for i in everything
                      if i.get("fixable") and
                      (i["rule"], i["line"], i["column"]) not in rejected]
        if not candidates:
            break
        candidates.sort(key=lambda i: (_PRIORITY.get(i["rule"], 9),
                                       i["line"], i["column"]))
        top_priority = _PRIORITY.get(candidates[0]["rule"], 9)
        group = [c for c in candidates
                 if _PRIORITY.get(c["rule"], 9) == top_priority]

        # Try the whole group at once when it is safe to do so, then one by
        # one if the batch is not accepted.
        attempts = []
        if len(group) > 1 and all(g["rule"] in _BATCHABLE for g in group):
            attempts.append(group)
        attempts.extend([g] for g in group[:3])

        accepted = False
        for attempt in attempts:
            for variant in range(1 + max(len(i["alt_edits"])
                                         for i in attempt)):
                edits = []
                for issue in attempt:
                    if variant == 0:
                        edits.extend(_edit_list(issue["edit"]))
                    elif variant <= len(issue["alt_edits"]):
                        edits.extend(_edit_list(issue["alt_edits"][variant - 1]))
                    else:
                        edits.extend(_edit_list(issue["edit"]))
                candidate = apply_edits(current, edits, lang)
                if candidate == current:
                    continue
                new_state = analyze(candidate, lang, use_compilers)
                before, after = _syntax_count(state), _syntax_count(new_state)
                new_all = new_state["issues"] + new_state["review_issues"]
                before_count = Counter((i["rule"], i["message"])
                                       for i in everything)
                after_count = Counter((i["rule"], i["message"])
                                      for i in new_all)
                wanted = Counter((i["rule"], i["message"]) for i in attempt)
                resolved = all(after_count[k] <= before_count[k] - m
                               for k, m in wanted.items())
                better_syntax = after < before
                no_new_syntax = after <= before
                total_before = len(everything)
                if (better_syntax or (resolved and no_new_syntax)) and \
                        len(new_all) <= total_before:
                    old_lines = current.split("\n")
                    new_lines = candidate.split("\n")
                    for issue in attempt:
                        ln = issue["line"]
                        fixes.append(_describe(
                            issue,
                            old_lines[ln - 1] if ln <= len(old_lines) else "",
                            _nearest_line(new_lines, old_lines, ln)))
                    current, state = candidate, new_state
                    accepted = True
                    break
            if accepted:
                break
        if not accepted:
            for issue in group[:3] if len(attempts) > 1 else group:
                rejected.add((issue["rule"], issue["line"], issue["column"]))
            if len(group) > 3:
                continue

    return {"fixed_code": current, "fixes": fixes, "partial": partial,
            "state": state}


def _nearest_line(new_lines, old_lines, line_no):
    """Best guess for how a changed line looks after the edit."""
    old = old_lines[line_no - 1] if line_no <= len(old_lines) else ""
    matcher = difflib.get_close_matches(
        old, new_lines[max(0, line_no - 3):line_no + 3], n=1, cutoff=0.4)
    return matcher[0] if matcher else (
        new_lines[line_no - 1] if line_no <= len(new_lines) else "")


def unified_diff(original, fixed):
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True), fixed.splitlines(keepends=True),
        fromfile="original", tofile="corrected", n=2))
