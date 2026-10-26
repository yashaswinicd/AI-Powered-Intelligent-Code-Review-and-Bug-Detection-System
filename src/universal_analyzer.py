"""Language-independent static analysis.

The checks here work on the scanned (string/comment-masked) source from
``src.lexer``, so they behave the same way for Java, C, C++
and JavaScript. Python has its
own AST based engine (``bug_detector``) but reuses the checks in this
module for secrets and syntax repairs.

Every issue is a plain dictionary. An issue that can be repaired carries
an ``edit`` (``{"start", "end", "text"}``, character offsets into the
analysed source) so the fixer can apply and verify it.
"""

import re

from src.lexer import scan
from src.language_support import LANGUAGES

OPENERS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {")": "(", "]": "[", "}": "{"}

SECRET_WORDS = re.compile(
    r"pass(?:word|wd)?|pwd|secret|api[_-]?key|apikey|access[_-]?key|"
    r"auth[_-]?token|token|private[_-]?key|credential", re.IGNORECASE)
LABEL_WORDS = re.compile(
    r"label|prompt|placeholder|hint|message|msg|title|text|field|"
    r"error|pattern|regex|url|path|file|name$", re.IGNORECASE)
PLACEHOLDER_VALUE = re.compile(
    r"^(<.*>|\*+|x+|\{.*\}|\$\{.*\}|%s|your[_\- ].*|changeme|"
    r"enter.*|none|null|todo)$", re.IGNORECASE)


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def make_issue(type_, line, severity, message, suggestion, *,
               column=1, category="bug", root_cause=None, source="rules",
               edit=None, alt_edits=None, rule=None, manual_note=None):
    return {
        "type": type_,
        "line": line,
        "column": column,
        "severity": severity,
        "message": message,
        "root_cause": root_cause or message,
        "suggestion": suggestion,
        "category": category,
        "source": source,
        "rule": rule or type_.lower().replace(" ", "_"),
        "edit": edit,
        "alt_edits": alt_edits or [],
        "fixable": edit is not None,
        "manual_note": manual_note,
    }


def _line_indent(code, index):
    start = code.rfind("\n", 0, index) + 1
    j = start
    while j < len(code) and code[j] in " \t":
        j += 1
    return code[start:j]


def _env_name(identifier):
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", identifier)
    name = re.sub(r"[^A-Za-z0-9]+", "_", spaced).strip("_").upper()
    return name or "SECRET"


# ---------------------------------------------------------------------
# lexical problems: unterminated strings and comments
# ---------------------------------------------------------------------

def check_lexical(sc, lang):
    issues = []
    for err in sc.errors:
        if err["kind"] == "string":
            quote = sc.code[err["index"]]
            line = err["line"]
            line_end = sc.line_end(line)
            raw = sc.code[err["index"] + 1:line_end]
            stripped = raw.rstrip()
            end_idx = err["index"] + 1 + len(stripped)

            # Candidate A: put the quote before a trailing ");" or ";"
            tail = re.search(r"[\s)\]};,]*$", stripped)
            suffix_len = len(tail.group(0)) if tail else 0
            suffix = stripped[len(stripped) - suffix_len:] if suffix_len else ""
            lead_trim = len(suffix) - len(suffix.lstrip())
            a_idx = end_idx - suffix_len + lead_trim
            edit_a = {"start": a_idx, "end": a_idx, "text": quote}
            edit_b = {"start": end_idx, "end": end_idx, "text": quote}
            if suffix_len and suffix.strip():
                edit, alt = edit_a, [edit_b]
            else:
                edit, alt = edit_b, []
            issues.append(make_issue(
                "Syntax Error", line, "critical",
                f"Unterminated string literal: the {quote} opened here is "
                "never closed on this line.",
                f"Add the missing closing {quote}.",
                column=err["column"], category="syntax",
                root_cause="A string must end with the same quote that "
                           "started it.",
                edit=edit, alt_edits=alt, rule="unterminated_string"))
        elif err["kind"] == "comment":
            end = len(sc.code)
            issues.append(make_issue(
                "Syntax Error", err["line"], "critical",
                "Unterminated block comment: '/*' has no matching '*/'.",
                "Close the comment with '*/'.",
                column=err["column"], category="syntax",
                edit={"start": end, "end": end, "text": "\n*/\n"},
                rule="unterminated_comment"))
        else:
            issues.append(make_issue(
                "Syntax Error", err["line"], "critical", err["message"],
                "Close the literal.", column=err["column"],
                category="syntax", rule="unterminated_literal"))
    return issues


# ---------------------------------------------------------------------
# bracket balance
# ---------------------------------------------------------------------

def _closer_position(sc, opener_idx, lang):
    """Where a missing ')' or ']' most likely belongs."""
    text = sc.code_only
    line = sc.line_of(opener_idx)

    if lang == "python":
        # End of the statement: last non-blank line before the next line
        # whose indentation is not deeper than the opener's line.
        lines = sc.code.split("\n")
        base = len(lines[line - 1]) - len(lines[line - 1].lstrip())
        last = line
        for k in range(line, len(lines)):
            raw = lines[k]
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip())
            if indent <= base:
                break
            last = k + 1
        end = sc.line_start(last) + len(
            sc.code_only.split("\n")[last - 1].rstrip())
        return end

    line_start = sc.line_start(line)
    line_end = sc.line_end(line)
    segment = text[opener_idx + 1:line_end]
    cut = len(segment)
    for marker in ("{", ";"):
        pos = segment.find(marker)
        if pos != -1:
            cut = min(cut, pos)
    idx = opener_idx + 1 + cut
    while idx > opener_idx + 1 and text[idx - 1] in " \t":
        idx -= 1
    return idx


def check_brackets(sc, lang):
    text = sc.code_only
    issues = []
    stack = []

    def unclosed(opener, idx, at_eof):
        line = sc.line_of(idx)
        closer = OPENERS[opener]
        if opener == "{":
            end = len(sc.code)
            indent = _line_indent(sc.code, idx)
            edit = {"start": end, "end": end,
                    "text": ("" if sc.code.endswith("\n") else "\n")
                            + indent + "}\n"}
        else:
            pos = _closer_position(sc, idx, lang)
            edit = {"start": pos, "end": pos, "text": closer}
        issues.append(make_issue(
            "Syntax Error", line, "critical",
            f"Missing closing '{closer}' for the '{opener}' opened on "
            f"line {line}.",
            f"Add the missing '{closer}'.",
            column=sc.column_of(idx), category="syntax",
            root_cause=f"The '{opener}' on line {line} is never closed.",
            edit=edit, rule="unclosed_bracket"))

    for idx, ch in enumerate(text):
        if ch in OPENERS:
            stack.append((ch, idx))
        elif ch in CLOSERS:
            want = CLOSERS[ch]
            if stack and stack[-1][0] == want:
                stack.pop()
                continue
            match = None
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][0] == want:
                    match = k
                    break
            if match is None:
                line = sc.line_of(idx)
                issues.append(make_issue(
                    "Syntax Error", line, "critical",
                    f"Unexpected '{ch}': there is no matching '{want}' "
                    "before it.",
                    f"Remove this extra '{ch}'.",
                    column=sc.column_of(idx), category="syntax",
                    root_cause="Closing bracket without an opening one.",
                    edit={"start": idx, "end": idx + 1, "text": ""},
                    rule="extra_bracket"))
            else:
                for opener, oidx in stack[match + 1:]:
                    unclosed(opener, oidx, False)
                del stack[match:]
    for opener, oidx in reversed(stack):
        unclosed(opener, oidx, True)
    return issues


# ---------------------------------------------------------------------
# missing semicolons (languages that require them)
# ---------------------------------------------------------------------

_CONTROL_HEADER = re.compile(
    r"^(if|for|foreach|while|switch|catch|using|lock|synchronized|fixed)"
    r"\b\s*\(")
_CONTINUATION_START = re.compile(
    r"^(\.|\?|:|&&|\|\||\)|\]|\+(?!\+)|-(?!-)|\*|/|%|=|,|<<|>>|->|&|\||\^|"
    r"throws\b|where\b|extends\b|implements\b)")
_STATEMENT_WORD = re.compile(
    r"^(return|break|continue|throw|goto|yield|echo|print|include|"
    r"require|require_once|include_once|delete|import|package)\b")
_ASSIGNMENT = re.compile(r"(?<![=!<>])=(?![=>])")
_CALL_STATEMENT = re.compile(r"^(?:await\s+)?(?:new\s+)?[\w$.:>\-\[\]]+\s*\(")
_INCDEC = re.compile(r"^(\+\+|--)?[\w.\[\]$]+(\+\+|--)?$")
_DATA_BEFORE_BRACE = re.compile(
    r"(=|\(|,|\[|\breturn|\benum\s*\w*|\bnew\b[^{;]*|\bin|\bof)\s*$")


def _find_header_end(stmt):
    depth = 0
    for k, c in enumerate(stmt):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return k + 1
    return -1


def _line_metadata(sc):
    """For each line: paren depth at start/end and innermost brace tag."""
    text = sc.code_only
    depth = 0
    brace_stack = []
    starts, ends, tags = [], [], []
    stmt_start = 0
    line_begin = True
    type_closers = []  # (index of '}', body is a struct/class/union/enum)
    for idx, ch in enumerate(text):
        if line_begin:
            starts.append(depth)
            tags.append(brace_stack[-1][0] if brace_stack else "block")
            line_begin = False
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == "{":
            precedent = text[stmt_start:idx].strip()
            is_type = bool(re.search(
                r"\b(struct|class|union|enum)\b[^;(){}]*$", precedent))
            if re.search(r"\bcase\b|\bdefault\b", precedent):
                tag = "block"
            elif _DATA_BEFORE_BRACE.search(precedent) and \
                    not precedent.endswith(")"):
                tag = "data"
            else:
                tag = "block"
            if re.search(r"\benum\b", precedent):
                tag = "data"
            brace_stack.append((tag, is_type))
            stmt_start = idx + 1
        elif ch == "}":
            if brace_stack:
                _, is_type = brace_stack.pop()
                if is_type:
                    type_closers.append(idx)
            stmt_start = idx + 1
        elif ch == ";":
            stmt_start = idx + 1
        if ch == "\n":
            ends.append(depth)
            line_begin = True
    if not line_begin or not ends:
        ends.append(depth)
    while len(starts) < len(ends):
        starts.append(depth)
        tags.append("block")
    return starts, ends, tags, type_closers


def check_semicolons(sc, lang):
    cfg = LANGUAGES[lang]
    if not cfg["semicolons"]:
        return []
    lines = sc.code_only.split("\n")
    starts, ends, tags, type_closers = _line_metadata(sc)
    issues = []

    def next_nonblank(i):
        for k in range(i + 1, len(lines)):
            if lines[k].strip():
                return lines[k].strip()
        return ""

    def prev_nonblank(i):
        for k in range(i - 1, -1, -1):
            if lines[k].strip():
                return lines[k].strip()
        return ""

    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or starts[i] != 0 or ends[i] != 0 or tags[i] == "data":
            continue
        if s.endswith("\\") or s.startswith(("<?", "?>", "@", "#")):
            continue

        stmt = s
        while stmt.startswith("}"):
            stmt = stmt[1:].strip()
        guard = 0
        while stmt and guard < 4:
            guard += 1
            if stmt.startswith("else"):
                stmt = stmt[4:].strip()
                continue
            if _CONTROL_HEADER.match(stmt):
                end = _find_header_end(stmt)
                if end == -1:
                    stmt = ""
                    break
                stmt = stmt[end:].strip()
                continue
            if re.match(r"^(do|try|finally)\b", stmt):
                stmt = re.sub(r"^(do|try|finally)\b", "", stmt).strip()
                continue
            break
        if not stmt:
            continue
        if re.match(r"^(case\b|default\b|public:|private:|protected:)", stmt):
            continue
        if re.match(r"^\w+\s*:$", stmt):
            continue

        last = stmt[-1]
        if last in ";{},:":
            continue
        ends_ok = (last.isalnum() or last in "_)]\"'`" or
                   stmt.endswith(("++", "--")))
        if not ends_ok:
            continue

        nxt = next_nonblank(i)
        if nxt.startswith("{") or (nxt and _CONTINUATION_START.match(nxt)):
            continue

        looks_like_statement = bool(
            _STATEMENT_WORD.match(stmt)
            or _ASSIGNMENT.search(stmt)
            or (stmt.endswith(")") and _CALL_STATEMENT.match(stmt)
                and not re.match(
                    r"^(public|private|protected|static|final|abstract|"
                    r"virtual|override|async|inline|extern|void|int|char|"
                    r"long|short|double|float|bool|boolean|string|String|"
                    r"unsigned|signed|const|template|fn|func|fun|function|"
                    r"def)\b", stmt))
            or (_INCDEC.match(stmt) and stmt.endswith(("++", "--")))
            or (_INCDEC.match(stmt) and stmt.startswith(("++", "--"))))

        if not looks_like_statement:
            continue

        line_no = i + 1
        end_idx = sc.line_start(line_no) + len(raw.rstrip())
        issues.append(make_issue(
            "Syntax Error", line_no, "critical",
            "Missing semicolon at the end of this statement.",
            "Add ';' at the end of the line.",
            column=len(raw.rstrip()) + 1, category="syntax",
            root_cause=f"{LANGUAGES[lang]['name']} statements must end "
                       "with ';'.",
            edit={"start": end_idx, "end": end_idx, "text": ";"},
            rule="missing_semicolon"))

    # statements that share a line with the closing brace:  { x = 5 }
    text = sc.code_only
    stack = []
    stmt_start = 0
    flagged_lines = {i["line"] for i in issues}
    for idx, ch in enumerate(text):
        if ch == "{":
            precedent = text[stmt_start:idx].strip()
            data = bool(_DATA_BEFORE_BRACE.search(precedent)) and \
                not precedent.endswith(")") or bool(
                    re.search(r"\benum\b", precedent))
            if re.search(r"\bcase\b|\bdefault\b", precedent):
                data = False
            stack.append(data)
            stmt_start = idx + 1
        elif ch == "}":
            is_data = stack.pop() if stack else True
            segment = text[stmt_start:idx]
            body = segment.strip()
            if (not is_data and body
                    and "\n" not in segment
                    and sc.line_of(idx) not in flagged_lines
                    and (body[-1].isalnum() or body[-1] in "_)]\"'")
                    and not re.match(r"^(if|else|for|while|switch|do|try|"
                                     r"catch|finally|case|default)\b", body)
                    and (_STATEMENT_WORD.match(body)
                         or _ASSIGNMENT.search(body)
                         or (body.endswith(")")
                             and _CALL_STATEMENT.match(body)))):
                end_idx = stmt_start + len(segment.rstrip())
                line_no = sc.line_of(end_idx)
                issues.append(make_issue(
                    "Syntax Error", line_no, "critical",
                    "Missing semicolon at the end of this statement.",
                    "Add ';' before the closing brace.",
                    column=sc.column_of(end_idx), category="syntax",
                    root_cause=f"{LANGUAGES[lang]['name']} statements must "
                               "end with ';'.",
                    edit={"start": end_idx, "end": end_idx, "text": ";"},
                    rule="missing_semicolon"))
            stmt_start = idx + 1
        elif ch == ";":
            stmt_start = idx + 1

    if lang in ("c", "cpp"):
        text = sc.code_only
        for idx in type_closers:
            j = idx + 1
            while j < len(text) and text[j] in " \t\r\n":
                j += 1
            nxt_char = text[j] if j < len(text) else ""
            if nxt_char in (";", ",", ")", "*", "&"):
                continue
            # "} name;" or "} name[3] = ..." declares a variable
            if re.match(r"[A-Za-z_]\w*\s*(\[[^\]]*\]\s*)*[;,=]",
                        text[j:j + 80]):
                continue
            line_no = sc.line_of(idx)
            issues.append(make_issue(
                "Syntax Error", line_no, "critical",
                "Missing ';' after the closing brace of a struct, class "
                "or enum.",
                "Add ';' after '}'.", column=sc.column_of(idx) + 1,
                category="syntax",
                edit={"start": idx + 1, "end": idx + 1, "text": ";"},
                rule="missing_semicolon_after_type"))
    return issues


# ---------------------------------------------------------------------
# semantic checks
# ---------------------------------------------------------------------

def _secret_replacement(lang, env_name, snippet_before):
    """(replacement expression, ensure-line) or None if no safe fix."""
    if lang == "python":
        return f'os.environ.get("{env_name}", "")', "import os"
    if lang == "javascript":
        return f"process.env.{env_name}", None
    if lang == "java":
        return f'System.getenv("{env_name}")', None
    if lang == "c":
        return f'getenv("{env_name}")', "#include <stdlib.h>"
    if lang == "cpp":
        return f'std::getenv("{env_name}")', "#include <cstdlib>"
    return None


_SECRET_ASSIGN = re.compile(
    r"""(?P<name>[A-Za-z_$][\w$.]*)(?P<arr>\s*\[\s*\d*\s*\])?\s*
        (?P<op>:=|=|:)\s*
        (?P<q>["'])(?P<val>[^"'\n]{3,})(?P=q)""", re.VERBOSE)
_SECRET_DICT = re.compile(
    r"""(?P<q1>["'])(?P<name>[\w\-.]+)(?P=q1)\s*(?P<op>:|=>)\s*
        (?P<q>["'])(?P<val>[^"'\n]{3,})(?P=q)""", re.VERBOSE)


def check_secrets(sc, lang):
    issues = []
    nc_lines = sc.no_comments.split("\n")
    code_lines = sc.code_only.split("\n")
    for i, nc in enumerate(nc_lines):
        if not nc.strip():
            continue
        lower = nc.lower()
        if any(w in lower for w in ("getenv", "environ", "process.env",
                                    "os.environ", "config.get")):
            continue
        for pattern in (_SECRET_ASSIGN, _SECRET_DICT):
            for m in pattern.finditer(nc):
                name, val = m.group("name"), m.group("val")
                short = name.split(".")[-1]
                if not SECRET_WORDS.search(short):
                    continue
                if LABEL_WORDS.search(short) and not \
                        re.search(r"(pass|pwd|secret|key|token)$",
                                  short, re.IGNORECASE):
                    continue
                if " " in val.strip() or PLACEHOLDER_VALUE.match(val.strip()):
                    continue
                # the match must start in real code, not inside a string
                if pattern is _SECRET_ASSIGN and \
                        not code_lines[i][m.start("name"):m.end("name")].strip():
                    continue
                line_no = i + 1
                lit_start = sc.line_start(line_no) + m.start("q")
                lit_end = sc.line_start(line_no) + m.end()
                if pattern is _SECRET_DICT:
                    lit_start = sc.line_start(line_no) + m.start("q")
                edit = None
                note = ("Move the value into an environment variable or a "
                        "secrets manager.")
                if not m.groupdict().get("arr"):
                    risky = ("document." in sc.code or "window." in sc.code)
                    if not (lang == "javascript" and risky):
                        rep = _secret_replacement(
                            lang, _env_name(short), nc[:m.start()])
                        if rep:
                            expr, ensure = rep
                            edit = {"start": lit_start, "end": lit_end,
                                    "text": expr}
                            if ensure:
                                edit["ensure"] = ensure
                issues.append(make_issue(
                    "Hardcoded Credential", line_no, "high",
                    f"Credential '{short}' is hard-coded in the source.",
                    note, column=m.start("name") + 1, category="security",
                    root_cause="Secrets stored in source code leak through "
                               "version control and shared files.",
                    edit=edit, rule="hardcoded_secret"))
                break
    return issues


def _match_brace(text, open_idx):
    depth = 0
    for k in range(open_idx, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return -1


_CATCH = re.compile(r"\bcatch\b\s*(\((?P<args>[^()]*)\))?\s*\{")


def _empty_catch_statement(lang, args):
    var = None
    if args:
        parts = args.replace("final ", "").split()
        if parts:
            var = parts[-1].strip("&*")
    if lang == "java":
        return f'System.err.println("Error: " + {var or "e"}.getMessage());'
    if lang == "javascript":
        return f"console.error({var or 'error'});"
    return None


def check_empty_catch(sc, lang):
    if lang == "python":
        return []
    issues = []
    text = sc.code_only
    for m in _CATCH.finditer(text):
        open_idx = m.end() - 1
        close_idx = _match_brace(text, open_idx)
        if close_idx == -1:
            continue
        body = text[open_idx + 1:close_idx]
        raw_body = sc.code[open_idx + 1:close_idx]
        if body.strip() or raw_body.strip():
            continue  # has code, or at least an explanatory comment
        line = sc.line_of(m.start())
        args = m.group("args")
        edit = None
        stmt = _empty_catch_statement(lang, args)
        indent = _line_indent(sc.code, m.start())
        if stmt:
            edit = {"start": open_idx + 1, "end": close_idx,
                    "text": f"\n{indent}    {stmt}\n{indent}"}
        if lang == "javascript" and args is None:
            edit = {"start": m.start(), "end": close_idx + 1,
                    "text": f"catch (error) {{\n{indent}    "
                            f"console.error(error);\n{indent}}}"}
        if lang == "cpp" and args is not None and "..." in args:
            edit = {"start": open_idx + 1, "end": close_idx,
                    "text": f'\n{indent}    std::cerr << "Error caught" '
                            f'<< std::endl;\n{indent}',
                    "ensure": "#include <iostream>"}
        issues.append(make_issue(
            "Empty Exception Handler", line, "medium",
            "Empty catch block: the error is silently swallowed.",
            "Log or handle the exception instead of ignoring it.",
            column=m.start() + 1 - (sc.line_start(line) if False else 0),
            category="bug",
            root_cause="Swallowed exceptions hide failures and make "
                       "debugging very hard.",
            edit=edit, rule="empty_catch"))
        issues[-1]["column"] = sc.column_of(m.start())
    return issues


_DIV_ZERO = re.compile(r"(?<![/*])/=?\s*0+(?:\.0*)?(?![\w.])")
_MOD_ZERO = re.compile(r"%\s*0+(?![\w.])")
_ZERO_ASSIGN = re.compile(
    r"\b(?:int|long|short|double|float|var|let|const|auto|val)?\s*"
    r"(?P<n>[A-Za-z_]\w*)\s*=\s*0(?:\.0*)?\s*;")


_TERNARY_LANGS = {"c", "cpp", "java", "javascript"}


def check_division_by_zero(sc, lang):
    issues = []
    lines = sc.code_only.split("\n")
    text = sc.code_only
    reported = set()

    def report(line_no, edit=None):
        if line_no in reported:
            return
        reported.add(line_no)
        issues.append(make_issue(
            "Division By Zero", line_no, "critical",
            "Division by zero detected.",
            "Make sure the divisor is not zero before dividing. The "
            "automatic fix returns 0 when the divisor is 0; change that "
            "value if your program needs something else.",
            category="bug",
            root_cause="The divisor is zero at this point, so the "
                       "operation will fail or give a wrong result at "
                       "run time.",
            edit=edit, rule="division_by_zero"))

    for i, line in enumerate(lines):
        if _DIV_ZERO.search(line) or _MOD_ZERO.search(line):
            report(i + 1)

    # a variable that is assigned zero exactly once and never changed
    for m in _ZERO_ASSIGN.finditer(text):
        name = m.group("n")
        writes = re.findall(
            r"(?<![\w.])" + re.escape(name) +
            r"\s*(?:\+\+|--|[-+*/%&|^]?=(?!=))|(?:\+\+|--)\s*" +
            re.escape(name) + r"\b", text)
        if len(writes) != 1:
            continue
        decl_line = sc.line_of(m.start())
        guard = re.compile(r"\b" + re.escape(name) +
                           r"\s*(?:!==?|>|<)\s*0|\bif\s*\(\s*" +
                           re.escape(name) + r"\s*\)")
        for j in range(decl_line - 1, len(lines)):
            line = lines[j]
            if j == decl_line - 1:  # same line: only look after the decl
                line = " " * (m.end() - sc.line_start(decl_line)) + \
                    line[m.end() - sc.line_start(decl_line):]
            use = re.search(r"[/%]\s*" + re.escape(name) + r"\b(?!\s*\()",
                            line)
            if not use:
                continue
            previous = lines[j - 1] if j else ""
            if guard.search(line) or guard.search(previous):
                continue  # the division is already protected
            edit = None
            simple = re.search(
                r"(?<![\w.)\]*/%])(?P<l>[\w.]+)\s*(?P<op>[/%])\s*"
                + re.escape(name) + r"\b(?!\s*[\w(.])", line)
            if simple and lang in _TERNARY_LANGS and \
                    simple.group("l") not in ("return",):
                strict = "!==" if lang == "javascript" else "!="
                base = sc.line_start(j + 1)
                edit = {"start": base + simple.start("l"),
                        "end": base + simple.end(),
                        "text": f"({name} {strict} 0 ? "
                                f"{simple.group('l')} {simple.group('op')} "
                                f"{name} : 0)"}
            report(j + 1, edit)
    return issues


_COND_ASSIGN = re.compile(
    r"\b(?P<kw>if|while)\s*\(\s*(?P<var>[A-Za-z_$][\w$.]*)\s*(?P<eq>=)"
    r"\s*(?P<rhs>-?\d+(?:\.\d+)?|true|false|null|NULL|nullptr)\s*\)")


def check_condition_assignment(sc, lang):
    issues = []
    for m in _COND_ASSIGN.finditer(sc.code_only):
        eq_idx = m.start("eq")
        line = sc.line_of(m.start())
        issues.append(make_issue(
            "Assignment In Condition", line, "high",
            f"'{m.group('var')} = {m.group('rhs')}' assigns a value inside "
            f"a '{m.group('kw')}' condition instead of comparing.",
            "Use '==' to compare values.", column=sc.column_of(eq_idx),
            category="bug",
            root_cause="A single '=' assigns; the condition is therefore "
                       "always decided by the assigned value.",
            edit={"start": eq_idx, "end": eq_idx + 1, "text": "=="},
            rule="assignment_in_condition"))
    return issues


def check_js_equality(sc, lang):
    if lang != "javascript":
        return []
    issues = []
    for m in re.finditer(r"(?<![=!<>])(==|!=)(?!=)", sc.code_only):
        after = sc.code_only[m.end():m.end() + 12].strip()
        before = sc.code_only[max(0, m.start() - 12):m.start()].strip()
        if re.match(r"(null|undefined)\b", after) or \
                re.search(r"\b(null|undefined)$", before):
            continue
        op = m.group(1)
        issues.append(make_issue(
            "Loose Equality", sc.line_of(m.start()), "low",
            f"'{op}' performs type coercion before comparing.",
            f"Use '{op}=' for a strict comparison.",
            column=sc.column_of(m.start()), category="style",
            root_cause="Loose equality can treat different types as equal "
                       "(for example 0 == '').",
            edit={"start": m.start(), "end": m.end(), "text": op + "="},
            rule="loose_equality"))
    return issues


_JAVA_STR_CMP_1 = re.compile(
    r"(?P<var>\b[A-Za-z_][\w.]*(?:\(\))?)\s*(?P<op>==|!=)\s*(?P<q>\")")
_JAVA_STR_CMP_2 = re.compile(
    r"(?P<q>\")\s*(?P<op>==|!=)\s*(?P<var>[A-Za-z_][\w.]*(?:\(\))?)")


def check_java_string_compare(sc, lang):
    if lang != "java":
        return []
    text = sc.code_only
    issues = []
    for m in _JAVA_STR_CMP_1.finditer(text):
        q_start = m.start("q")
        q_end = text.find('"', q_start + 1)
        if q_end == -1 or "\n" in text[q_start:q_end]:
            continue
        literal = sc.code[q_start:q_end + 1]
        var = m.group("var")
        neg = "!" if m.group("op") == "!=" else ""
        issues.append(make_issue(
            "String Comparison With ==", sc.line_of(m.start()), "high",
            "Strings are compared with '==', which compares object "
            "references instead of text.",
            "Use equals() to compare the text of two strings.",
            column=sc.column_of(m.start()), category="bug",
            root_cause="'==' checks whether both variables point to the "
                       "same object, not whether the characters are equal.",
            edit={"start": m.start("var"), "end": q_end + 1,
                  "text": f"{neg}{literal}.equals({var})"},
            rule="java_string_equals"))
    for m in _JAVA_STR_CMP_2.finditer(text):
        q_start = m.start("q")
        q_end = text.find('"', q_start + 1)
        if q_end == -1 or q_end > m.start("op") or "\n" in text[q_start:q_end]:
            continue
        literal = sc.code[q_start:q_end + 1]
        var = m.group("var")
        neg = "!" if m.group("op") == "!=" else ""
        issues.append(make_issue(
            "String Comparison With ==", sc.line_of(m.start()), "high",
            "Strings are compared with '==', which compares object "
            "references instead of text.",
            "Use equals() to compare the text of two strings.",
            column=sc.column_of(m.start()), category="bug",
            edit={"start": q_start, "end": m.end("var"),
                  "text": f"{neg}{literal}.equals({var})"},
            rule="java_string_equals"))
    return issues


_DANGEROUS = [
    ({"c", "cpp"}, re.compile(r"(?<![\w.])gets\s*\("), "critical",
     "Unsafe function gets()",
     "gets() cannot limit how much it reads and causes buffer overflows.",
     "Use fgets(buffer, size, stdin) instead."),
    ({"c", "cpp"}, re.compile(r"(?<![\w.])(strcpy|strcat|sprintf|vsprintf)"
                              r"\s*\("), "high",
     "Unsafe string function",
     "This function does not check the size of the destination buffer.",
     "Use strncpy/strncat/snprintf and pass the buffer size."),
    ({"c", "cpp"}, re.compile(r"(?<![\w.>:$])system\s*\("), "high",
     "Command execution via system()",
     "system() runs a shell command; unchecked input allows injection.",
     "Avoid the shell, or validate every part of the command."),
    ({"java"}, re.compile(r"\bRuntime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*"
                          r"exec\s*\("), "high",
     "Command execution via Runtime.exec()",
     "Running external commands with user data allows command injection.",
     "Use ProcessBuilder with a fixed argument list and validate input."),
    ({"java"}, re.compile(r"\bObjectInputStream\b"), "medium",
     "Unsafe deserialization",
     "Deserializing untrusted data can execute attacker-chosen code.",
     "Validate the source or use a safe format such as JSON."),
    ({"javascript"},
     re.compile(r"\bnew\s+Function\s*\(|\bchild_process\b"), "high",
     "Dynamic code or command execution",
     "Building code or commands from strings allows injection.",
     "Avoid new Function / child_process with untrusted input."),
]


def check_dangerous_calls(sc, lang):
    issues = []
    lines = sc.code_only.split("\n")
    for langs, pattern, severity, name, why, fix in _DANGEROUS:
        if lang not in langs:
            continue
        for i, line in enumerate(lines):
            if pattern.search(line):
                issues.append(make_issue(
                    name, i + 1, severity, why, fix, category="security",
                    root_cause=why, rule="dangerous_call"))
    if lang in ("c", "cpp"):
        for i, line in enumerate(sc.no_comments.split("\n")):
            if re.search(r"\bscanf\s*\(\s*\"[^\"]*%s", line):
                issues.append(make_issue(
                    "Unbounded scanf %s", i + 1, "medium",
                    "scanf(\"%s\") reads a word of any length into a "
                    "fixed buffer.",
                    "Give a width, for example scanf(\"%49s\", buf).",
                    category="security", rule="scanf_s"))
    return issues


_JUMP = re.compile(r"^(return\b|break\s*;|continue\s*;|throw\b|goto\b)")


def check_unreachable(sc, lang):
    if lang not in ("c", "cpp", "java", "javascript"):
        return []
    issues = []
    lines = sc.code_only.split("\n")
    starts, ends, tags, _ = _line_metadata(sc)

    def nxt(i):
        for k in range(i + 1, len(lines)):
            if lines[k].strip():
                return k
        return None

    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s.endswith(";") and lang != "javascript":
            continue
        if not _JUMP.match(s) or ends[i] != 0 or starts[i] != 0:
            continue
        if s.endswith("{") or "{" in s:
            continue
        # a jump that is the body of an un-braced if/else/for/while
        p = i - 1
        while p >= 0 and not lines[p].strip():
            p -= 1
        if p >= 0:
            prev = lines[p].strip()
            if re.match(r"^(if|else|for|while|foreach)\b", prev) and \
                    not prev.endswith(("{", ";")):
                continue
            if prev.endswith(")") and re.match(
                    r"^(\}\s*)?(else\s+)?(if|for|while)\b", prev):
                continue
        k = nxt(i)
        if k is None:
            continue
        follower = lines[k].strip()
        if follower.startswith(("}", "case ", "default", "else", "#",
                                "catch", "finally")):
            continue
        if re.match(r"^\w+\s*:$", follower):
            continue
        issues.append(make_issue(
            "Unreachable Code", k + 1, "medium",
            f"This code can never run: line {i + 1} always leaves the "
            "block before reaching it.",
            "Remove the unreachable statements or restructure the logic.",
            category="bug",
            root_cause="Statements after return/break/continue/throw "
                       "are never executed.",
            rule="unreachable_code"))
    return issues


# ---------------------------------------------------------------------
# review / style
# ---------------------------------------------------------------------

def check_review(sc, lang, max_depth=5):
    issues = []
    lines = sc.code_only.split("\n")
    depth = 0
    deepest = (0, 1)
    for i, line in enumerate(lines):
        for ch in line:
            if ch == "{":
                depth += 1
                if depth > deepest[0]:
                    deepest = (depth, i + 1)
            elif ch == "}":
                depth = max(0, depth - 1)
    if deepest[0] > max_depth:
        issues.append(make_issue(
            "High Complexity", deepest[1], "medium",
            f"Code is deeply nested (depth {deepest[0]}).",
            "Split the nested blocks into smaller functions.",
            category="style", rule="deep_nesting"))

    long_lines = [i + 1 for i, l in enumerate(sc.code.split("\n"))
                  if len(l.rstrip()) > 140]
    if long_lines:
        issues.append(make_issue(
            "Long Line", long_lines[0], "low",
            f"{len(long_lines)} line(s) are longer than 140 characters "
            f"(first at line {long_lines[0]}).",
            "Break long lines to keep the code readable.",
            category="style", rule="long_lines"))

    for i, line in enumerate(sc.code.split("\n")):
        if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line) and any(
                marker in line for marker in
                (LANGUAGES[lang]["line"] + ["/*", "*"])):
            issues.append(make_issue(
                "Pending Task Comment", i + 1, "low",
                "A TODO/FIXME comment marks unfinished work.",
                "Finish the task or track it in an issue list.",
                category="style", rule="todo_comment"))
            break
    return issues


# ---------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------

SYNTAX_RULES = {"unterminated_string", "unterminated_comment",
                "unclosed_bracket", "extra_bracket", "missing_semicolon",
                "missing_semicolon_after_type", "unterminated_literal"}


def analyze_text(code, lang):
    """Rule-based analysis (no external tools). Returns (issues, scan)."""
    sc = scan(code, lang)
    issues = []
    issues += check_lexical(sc, lang)
    issues += check_brackets(sc, lang)
    issues += check_semicolons(sc, lang)
    issues += check_secrets(sc, lang)
    if lang != "python":
        issues += check_empty_catch(sc, lang)
        issues += check_division_by_zero(sc, lang)
        issues += check_condition_assignment(sc, lang)
        issues += check_js_equality(sc, lang)
        issues += check_java_string_compare(sc, lang)
        issues += check_dangerous_calls(sc, lang)
        issues += check_unreachable(sc, lang)
    return issues, sc
