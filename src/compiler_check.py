"""Optional verification with real compilers / parsers.

If a toolchain is installed (gcc, g++, node, javac) it is used to check
the code. The compiler is the final judge: its verdict is more reliable
than any heuristic. If the tool is missing the analyzer simply falls back
to its own rules, so nothing here is required to run the project.
"""

import os
import re
import shutil
import subprocess
import tempfile

_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"',
                         "\u201d": '"'})

# Messages that mean "the compiler could not check this file", not
# "this file has a bug" (missing headers, packages from other projects).
_ENVIRONMENT_NOISE = re.compile(
    r"No such file or directory|cannot open source file|"
    r"package .* does not exist|cannot access|file not found|"
    r"module .* not found", re.IGNORECASE)

_SYNTAX_WORDS = re.compile(
    r"expected|unexpected|syntax|missing|unterminated|invalid|stray|"
    r"parse error|illegal start|not a statement|reached end of file|"
    r"unclosed|unmatched|empty character", re.IGNORECASE)


def _run(cmd, stdin_text=None, cwd=None, timeout=20):
    return subprocess.run(
        cmd, input=stdin_text, capture_output=True, text=True,
        timeout=timeout, cwd=cwd, env={**os.environ, "LC_ALL": "C",
                                       "LANG": "C"})


def available_tools():
    return {
        "gcc": bool(shutil.which("gcc")),
        "g++": bool(shutil.which("g++")),
        "node": bool(shutil.which("node")),
        "javac": bool(shutil.which("javac")),
    }


def _classify(message):
    return "Syntax Error" if _SYNTAX_WORDS.search(message) else "Compile Error"


def parse_gcc(stderr):
    errors = []
    noise = False
    for line in stderr.splitlines():
        m = re.match(r"^(?:<stdin>|[^:\s]+):(\d+):(?:(\d+):)?\s*"
                     r"(fatal error|error):\s*(.*)$", line.translate(_QUOTES))
        if not m:
            continue
        message = m.group(4).strip()
        if _ENVIRONMENT_NOISE.search(message):
            noise = True
            continue
        errors.append({"line": int(m.group(1)),
                       "column": int(m.group(2) or 1),
                       "message": message})
    return errors, noise


def parse_node(stderr):
    """node --check prints 'file:LINE', a source line, a caret, then the
    SyntaxError message."""
    lines = stderr.splitlines()
    line_no = None
    for ln in lines:
        m = re.match(r"^.*\.m?js:(\d+)\s*$", ln)
        if m:
            line_no = int(m.group(1))
            break
    message = None
    for ln in lines:
        if ln.startswith("SyntaxError:"):
            message = ln[len("SyntaxError:"):].strip()
            break
    if line_no and message:
        return [{"line": line_no, "column": 1, "message": message}], False
    return [], False


def parse_javac(stderr):
    errors = []
    noise = False
    for line in stderr.splitlines():
        m = re.match(r"^[^:\s]+\.java:(\d+):\s*error:\s*(.*)$", line)
        if not m:
            continue
        message = m.group(2).strip()
        if _ENVIRONMENT_NOISE.search(message):
            noise = True
            continue
        errors.append({"line": int(m.group(1)), "column": 1,
                       "message": message})
    return errors, noise


def check(code, lang, timeout=20):
    """Return a result dictionary.

    available    a suitable tool was found and executed
    ok           the tool accepted the code (only meaningful if conclusive)
    conclusive   the verdict can be trusted (False if headers were missing)
    errors       list of {line, column, message, type}
    tool         name of the tool used
    """
    result = {"available": False, "ok": None, "conclusive": False,
              "errors": [], "tool": None}
    try:
        if lang in ("c", "cpp"):
            exe = shutil.which("gcc" if lang == "c" else "g++")
            if not exe:
                return result
            cmd = [exe, "-fsyntax-only", "-w", "-x",
                   "c" if lang == "c" else "c++", "-"]
            if lang == "cpp":
                cmd.insert(1, "-std=c++17")
            proc = _run(cmd, stdin_text=code, timeout=timeout)
            errors, noise = parse_gcc(proc.stderr)
            tool = os.path.basename(exe)
        elif lang in ("javascript",):
            exe = shutil.which("node")
            if not exe:
                return result
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "check.mjs")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(code)
                proc = _run([exe, "--check", path], timeout=timeout)
            errors, noise = parse_node(proc.stderr)
            tool = "node --check"
        elif lang == "java":
            exe = shutil.which("javac")
            if not exe:
                return result
            match = re.search(r"\bpublic\s+(?:final\s+|abstract\s+)*"
                              r"(?:class|interface|enum|record)\s+(\w+)",
                              code)
            class_name = match.group(1) if match else "Main"
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, class_name + ".java")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(code)
                proc = _run([exe, "-proc:none", "-Xlint:none", "-d", tmp,
                             path], timeout=timeout)
            errors, noise = parse_javac(proc.stderr)
            tool = "javac"
        else:
            return result
    except (subprocess.TimeoutExpired, OSError):
        return result

    for err in errors:
        err["type"] = _classify(err["message"])
    result.update(available=True, tool=tool, errors=errors,
                  ok=(proc.returncode == 0 and not errors),
                  conclusive=not (noise and not errors))
    if proc.returncode != 0 and not errors and not noise:
        # The tool failed in a way we do not understand: not conclusive.
        result["conclusive"] = False
        result["ok"] = None
    return result
