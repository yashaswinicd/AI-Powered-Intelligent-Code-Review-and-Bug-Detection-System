"""Run Python code in a restricted subprocess.

Protection layers (best effort, see README "Limitations"):
  1. A static policy check refuses code that imports process/network/file
     system modules or calls dangerous built-ins.
  2. The code runs in a separate interpreter (-I isolated mode) inside an
     empty temporary directory with a minimal environment.
  3. A wall-clock timeout, output limit and (on Linux/macOS) CPU, memory
     and file-size limits are applied.

This is a safety net for a study project, not a security boundary. Truly
untrusted code must be run in a container or virtual machine.
"""

import ast
import os
import re
import subprocess
import sys
import tempfile

BLOCKED_MODULES = {
    "subprocess", "shutil", "socket", "ctypes", "multiprocessing", "pty",
    "signal", "requests", "urllib", "http", "ftplib", "smtplib", "telnetlib",
    "asyncio.subprocess", "importlib", "pickle", "marshal", "webbrowser",
    "tkinter", "pathlib", "glob", "tempfile", "resource", "mmap", "sqlite3",
}
BLOCKED_CALLS = {"eval", "exec", "compile", "__import__",
                 "breakpoint", "getattr", "setattr", "delattr", "globals",
                 "locals", "vars", "memoryview", "exit", "quit"}
BLOCKED_OS_ATTRS = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename",
    "replace", "kill", "killpg", "fork", "forkpty", "execv", "execve",
    "execl", "execlp", "execvp", "spawnl", "spawnv", "chmod", "chown",
    "mkdir", "makedirs", "listdir", "scandir", "walk", "startfile",
    "environ", "putenv", "truncate", "write", "symlink", "link",
}
BLOCKED_DUNDERS = {"__class__", "__bases__", "__subclasses__", "__globals__",
                   "__builtins__", "__code__", "__mro__", "__import__",
                   "__loader__", "__spec__", "__getattribute__"}

MAX_OUTPUT = 20000


def _open_violation(node):
    """open() is allowed for reading, and for writing only to a plain
    relative file name (it ends up inside the throw-away sandbox folder)."""
    mode = "r"
    if len(node.args) > 1:
        arg = node.args[1]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            return "open() needs a literal mode string in the sandbox."
        mode = arg.value
    for kw in node.keywords:
        if kw.arg == "mode":
            if not (isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)):
                return "open() needs a literal mode string in the sandbox."
            mode = kw.value.value
    if not any(c in mode for c in "wax+"):
        return None
    target = node.args[0] if node.args else None
    if isinstance(target, ast.Constant) and isinstance(target.value, str):
        path = target.value.replace("\\", "/")
        if not path.startswith("/") and ":" not in path and ".." not in path:
            return None
    return ("Writing files is only allowed for a plain relative file name "
            "in the sandbox.")


def policy_violation(code):
    """Return (message, line) if the code breaks the policy, else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # the interpreter will report the syntax error itself
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BLOCKED_MODULES:
                    return (f"Importing '{alias.name}' is not allowed in "
                            "the sandbox.", node.lineno)
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top in BLOCKED_MODULES:
                return (f"Importing from '{node.module}' is not allowed "
                        "in the sandbox.", node.lineno)
            if top == "os" and any(a.name in BLOCKED_OS_ATTRS
                                   for a in node.names):
                return ("This 'os' function is not allowed in the sandbox.",
                        node.lineno)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                problem = _open_violation(node)
                if problem:
                    return problem, node.lineno
            if isinstance(func, ast.Name) and func.id in BLOCKED_CALLS:
                return (f"Calling '{func.id}()' is not allowed in the "
                        "sandbox.", node.lineno)
        elif isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_DUNDERS:
                return (f"Access to '{node.attr}' is not allowed in the "
                        "sandbox.", node.lineno)
            if isinstance(node.value, ast.Name) and node.value.id == "os" \
                    and node.attr in BLOCKED_OS_ATTRS:
                return (f"'os.{node.attr}' is not allowed in the sandbox.",
                        node.lineno)
            if isinstance(node.value, ast.Name) and node.value.id == "sys" \
                    and node.attr in ("modules", "exit"):
                return (f"'sys.{node.attr}' is not allowed in the sandbox.",
                        node.lineno)
    return None


def _limit_resources():  # pragma: no cover - runs in the child process
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1 * 2**20, 1 * 2**20))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    except Exception:
        pass


class ExecutionEngine:
    def __init__(self, timeout=5):
        self.timeout = timeout

    def run(self, code, stdin_input=""):
        blocked = policy_violation(code)
        if blocked:
            message, line = blocked
            return {"success": False, "return_code": None, "output": "",
                    "error": message, "error_type": "BlockedByPolicy",
                    "error_line": line, "skipped": True}

        with tempfile.TemporaryDirectory(prefix="sandbox_") as tmp:
            path = os.path.join(tmp, "main.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
            env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
            if os.name == "nt":
                env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
            kwargs = {"preexec_fn": _limit_resources} if os.name == "posix" \
                else {}
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", path],
                    input=stdin_input or "", capture_output=True, text=True,
                    timeout=self.timeout, cwd=tmp, env=env,
                    encoding="utf-8", errors="replace", **kwargs)
            except subprocess.TimeoutExpired:
                return {"success": False, "return_code": None, "output": "",
                        "error": f"Execution stopped after {self.timeout} "
                                 "seconds (possible infinite loop or input "
                                 "that never ends).",
                        "error_type": "TimeoutError", "error_line": None}

        stdout = proc.stdout[:MAX_OUTPUT]
        stderr = proc.stderr[:MAX_OUTPUT]
        error_type, error_line = None, None
        if proc.returncode != 0:
            lines = [l for l in stderr.strip().splitlines() if l.strip()]
            if lines:
                m = re.match(r"^([A-Za-z_][\w.]*(?:Error|Exception|Exit|"
                             r"Interrupt))\b", lines[-1])
                error_type = m.group(1) if m else "RuntimeError"
            hits = re.findall(r'File ".*?main\.py", line (\d+)', stderr)
            error_line = int(hits[-1]) if hits else None
            stderr = re.sub(r'File ".*?main\.py"', 'File "<your code>"',
                            stderr)
        return {"success": proc.returncode == 0,
                "return_code": proc.returncode, "output": stdout,
                "error": stderr, "error_type": error_type,
                "error_line": error_line}
