"""A small, language-aware scanner.

Regular expressions on raw source are unreliable because the text inside
strings and comments looks like code. This scanner walks the source once
and produces two masked copies of it, both exactly the same length as the
original so every index and line number still lines up:

    code_only   strings (contents) and comments replaced by spaces
    no_comments only comments replaced by spaces

It also reports lexical errors it meets on the way (unterminated strings
and block comments).
"""

import bisect

from src.language_support import LANGUAGES

_REGEX_PREV_CHARS = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_PREV_WORDS = {"return", "typeof", "case", "in", "of", "delete",
                     "void", "throw", "new", "else", "do"}


class ScanResult:
    def __init__(self, code, code_only, no_comments, errors, line_starts):
        self.code = code
        self.code_only = code_only
        self.no_comments = no_comments
        self.errors = errors
        self._line_starts = line_starts

    def line_of(self, index):
        """1-based line number of a character index."""
        return bisect.bisect_right(self._line_starts, index)

    def column_of(self, index):
        """1-based column of a character index."""
        line = self.line_of(index)
        return index - self._line_starts[line - 1] + 1

    def line_start(self, line):
        return self._line_starts[line - 1]

    def line_end(self, line):
        """Index of the newline that ends the line (or end of text)."""
        if line < len(self._line_starts):
            return self._line_starts[line] - 1
        return len(self.code)


def _line_starts(code):
    starts = [0]
    for i, ch in enumerate(code):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _blank(buf, start, end):
    """Replace buf[start:end] with spaces, keeping newlines."""
    for i in range(start, min(end, len(buf))):
        if buf[i] != "\n" and buf[i] != "\r":
            buf[i] = " "


def _previous_significant(buf, index):
    """Previous non-space character and the word that precedes index."""
    j = index - 1
    while j >= 0 and buf[j] in " \t\r\n":
        j -= 1
    if j < 0:
        return "", ""
    char = buf[j]
    k = j
    while k >= 0 and (buf[k].isalnum() or buf[k] == "_"):
        k -= 1
    word = "".join(buf[k + 1:j + 1]) if k < j else ""
    return char, word


def scan(code, lang):
    cfg = LANGUAGES[lang]
    n = len(code)
    code_only = list(code)
    no_comments = list(code)
    starts = _line_starts(code)
    errors = []

    def line_of(idx):
        return bisect.bisect_right(starts, idx)

    def add_error(kind, idx, message):
        line = line_of(idx)
        errors.append({
            "kind": kind, "index": idx, "line": line,
            "column": idx - starts[line - 1] + 1, "message": message,
        })

    line_markers = cfg["line"]
    block = cfg["block"]
    quotes = cfg["quotes"]
    hash_directives = lang in ("c", "cpp")
    is_js = lang == "javascript"

    i = 0
    at_line_start = True
    while i < n:
        ch = code[i]

        if ch == "\n":
            at_line_start = True
            i += 1
            continue

        if ch in " \t\r":
            i += 1
            continue

        # Preprocessor lines (#include, #define, #region ...)
        if hash_directives and ch == "#" and at_line_start:
            j = i
            while j < n:
                if code[j] == "\n":
                    if code[j - 1] == "\\" or (j > 0 and code[j - 1] == "\r"
                                               and code[j - 2] == "\\"):
                        j += 1
                        continue
                    break
                j += 1
            _blank(code_only, i, j)
            i = j
            continue
        at_line_start = False

        # Line comments
        matched = False
        for marker in line_markers:
            if code.startswith(marker, i):
                j = code.find("\n", i)
                j = n if j == -1 else j
                _blank(code_only, i, j)
                _blank(no_comments, i, j)
                i = j
                matched = True
                break
        if matched:
            continue

        # Block comments
        for start_m, end_m in block:
            if code.startswith(start_m, i):
                j = code.find(end_m, i + len(start_m))
                if j == -1:
                    add_error("comment", i,
                              "Unterminated block comment (missing '*/').")
                    j = n
                else:
                    j += len(end_m)
                _blank(code_only, i, j)
                _blank(no_comments, i, j)
                i = j
                matched = True
                break
        if matched:
            continue

        # Regular-expression literals in JavaScript
        if is_js and ch == "/":
            prev_char, prev_word = _previous_significant(code_only, i)
            if (prev_char == "" or prev_char in _REGEX_PREV_CHARS
                    or prev_word in _REGEX_PREV_WORDS):
                j = i + 1
                in_class = False
                closed = False
                while j < n and code[j] != "\n":
                    c = code[j]
                    if c == "\\":
                        j += 2
                        continue
                    if c == "[":
                        in_class = True
                    elif c == "]":
                        in_class = False
                    elif c == "/" and not in_class:
                        closed = True
                        break
                    j += 1
                if closed:
                    j += 1
                    while j < n and code[j].isalpha():
                        j += 1
                    _blank(code_only, i + 1, j - 1)
                    i = j
                    continue

        # Triple-quoted / text-block strings
        if cfg["triple"] and ch in "\"'" and code.startswith(ch * 3, i):
            delim = ch * 3
            if lang != "python" and ch == "'":
                pass  # only """ is a text block outside Python
            else:
                j = code.find(delim, i + 3)
                if j == -1:
                    add_error("string", i,
                              "Unterminated multi-line string.")
                    j = n
                else:
                    j += 3
                _blank(code_only, i + 3, max(i + 3, j - 3))
                i = j
                continue

        # C++ raw string  R"delim( ... )delim"
        if lang == "cpp" and ch == '"' and i > 0 and code[i - 1] == "R":
            open_paren = code.find("(", i)
            if open_paren != -1 and open_paren - i <= 17:
                delim = code[i + 1:open_paren]
                closing = ")" + delim + '"'
                j = code.find(closing, open_paren)
                if j != -1:
                    j += len(closing)
                    _blank(code_only, i + 1, j - 1)
                    i = j
                    continue

        # Ordinary string / character literals
        if ch in quotes:
            # C++ digit separators (1'000)
            if ch == "'":
                nxt = code[i + 1] if i + 1 < n else ""
                if lang in ("cpp", "c") and i > 0 and \
                        code[i - 1].isalnum() and nxt.isalnum():
                    i += 1
                    continue

            multiline = ch == "`"
            j = i + 1
            closed = False
            while j < n:
                c = code[j]
                if c == "\\":
                    j += 2
                    continue
                if c == ch:
                    closed = True
                    break
                if c == "\n" and not multiline:
                    break
                j += 1

            if closed:
                _blank(code_only, i + 1, j)
                i = j + 1
            else:
                add_error("string", i,
                          "Unterminated string literal "
                          f"(missing closing {ch}).")
                end = j if j < n else n
                _blank(code_only, i + 1, end)
                i = end
            continue

        i += 1

    return ScanResult(code, "".join(code_only), "".join(no_comments),
                      errors, starts)
