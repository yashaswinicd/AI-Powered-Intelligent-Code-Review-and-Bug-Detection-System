"""Python analysis built on the standard ``ast`` module.

Python gets the deepest checks because its syntax tree is available
without any external tool. The module returns issues in the same format
as ``universal_analyzer`` (including repair edits), so one fixer handles
every language.
"""

import ast
import builtins
import difflib
import re

from src.lexer import scan
from src.universal_analyzer import (analyze_text, make_issue, SYNTAX_RULES,
                                    _line_indent)

BUILTIN_NAMES = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__spec__", "__package__",
    "__loader__", "__builtins__", "__path__", "__annotations__",
    "__debug__", "__class__", "__qualname__", "__module__",
}

# Standard-library modules that can be imported safely when a script uses
# the module name but forgot the import.
KNOWN_MODULES = {
    "math", "os", "sys", "re", "json", "random", "time", "datetime",
    "collections", "itertools", "functools", "string", "statistics",
    "copy", "csv", "heapq", "bisect", "decimal", "fractions", "pathlib",
    "logging", "subprocess", "threading", "typing", "io", "hashlib",
    "operator", "textwrap", "argparse", "uuid", "pickle", "shutil",
}

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
                ast.GeneratorExp)


class _Source:
    """Converts AST (line, utf-8 byte column) positions to string offsets."""

    def __init__(self, code):
        self.code = code
        self.lines = code.split("\n")
        self.starts = [0]
        for line in self.lines[:-1]:
            self.starts.append(self.starts[-1] + len(line) + 1)

    def offset(self, lineno, col):
        line = self.lines[lineno - 1]
        text_col = len(line.encode("utf-8")[:col].decode("utf-8", "ignore"))
        return self.starts[lineno - 1] + text_col

    def start(self, node):
        return self.offset(node.lineno, node.col_offset)

    def end(self, node):
        return self.offset(node.end_lineno, node.end_col_offset)

    def line_end(self, lineno):
        return self.starts[lineno - 1] + len(self.lines[lineno - 1])


# ---------------------------------------------------------------------
# scope resolver: finds names that are never defined anywhere
# ---------------------------------------------------------------------

class _Scope:
    def __init__(self, kind, parent):
        self.kind = kind
        self.parent = parent
        self.names = set()
        self.declared_global = set()
        self.declared_nonlocal = set()


class _Binder(ast.NodeVisitor):
    """Collect the names bound directly in one scope."""

    def __init__(self, scope):
        self.scope = scope

    def bind(self, name):
        self.scope.names.add(name)

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bind(node.id)

    def visit_Global(self, node):
        self.scope.declared_global.update(node.names)

    def visit_Nonlocal(self, node):
        self.scope.declared_nonlocal.update(node.names)

    def visit_Import(self, node):
        for alias in node.names:
            self.bind(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name != "*":
                self.bind(alias.asname or alias.name)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.bind(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.bind(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node):
        if node.name:
            self.bind(node.name)

    def visit_MatchMapping(self, node):
        if node.rest:
            self.bind(node.rest)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.bind(node.name)
        for deco in node.decorator_list:
            self.visit(deco)
        for default in node.args.defaults + node.args.kw_defaults:
            if default is not None:
                self.visit(default)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.bind(node.name)
        for deco in node.decorator_list:
            self.visit(deco)
        for base in node.bases:
            self.visit(base)

    def visit_Lambda(self, node):
        for default in node.args.defaults + node.args.kw_defaults:
            if default is not None:
                self.visit(default)

    def _comprehension(self, node):
        # only the outermost iterable runs in the enclosing scope
        self.visit(node.generators[0].iter)

    visit_ListComp = visit_SetComp = visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension


def _arg_names(args):
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    if args.vararg:
        names.append(args.vararg.arg)
    if args.kwarg:
        names.append(args.kwarg.arg)
    return names


def find_undefined_names(tree):
    """Return a list of ast.Name nodes that are never bound anywhere."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and \
                any(a.name == "*" for a in node.names):
            return []

    module_scope = _Scope("module", None)
    global_assigned = set()
    problems = []

    def bind_body(scope, statements):
        binder = _Binder(scope)
        for stmt in statements:
            binder.visit(stmt)

    def visit_scope(node, scope):
        """Resolve the loads of ``node`` (a scope owner) in ``scope``."""
        body = node if isinstance(node, list) else None
        statements = body

        def lookup(name):
            current = scope
            first = True
            while current is not None:
                if current.kind == "class" and not first:
                    current = current.parent
                    continue
                if name in current.names or name in current.declared_global \
                        and current.kind != "module":
                    if name in current.declared_global:
                        return name in module_scope.names or \
                            name in global_assigned
                    return True
                first = False
                current = current.parent
            return name in BUILTIN_NAMES

        def walk(n):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if not lookup(n.id):
                    problems.append(n)
                return
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for deco in n.decorator_list:
                    walk(deco)
                for d in n.args.defaults + n.args.kw_defaults:
                    if d is not None:
                        walk(d)
                inner = _Scope("function", scope)
                inner.names.update(_arg_names(n.args))
                bind_body(inner, n.body)
                global_assigned.update(inner.declared_global & inner.names)
                inner.names -= inner.declared_global
                sub = _Resolver(inner)
                sub.run(n.body)
                return
            if isinstance(n, ast.ClassDef):
                for deco in n.decorator_list:
                    walk(deco)
                for base in n.bases + [k.value for k in n.keywords]:
                    walk(base)
                inner = _Scope("class", scope)
                bind_body(inner, n.body)
                sub = _Resolver(inner)
                sub.run(n.body)
                return
            if isinstance(n, ast.Lambda):
                for d in n.args.defaults + n.args.kw_defaults:
                    if d is not None:
                        walk(d)
                inner = _Scope("function", scope)
                inner.names.update(_arg_names(n.args))
                _Resolver(inner).run_expr(n.body)
                return
            if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp,
                              ast.GeneratorExp)):
                walk(n.generators[0].iter)
                inner = _Scope("function", scope)
                for gen in n.generators:
                    for t in ast.walk(gen.target):
                        if isinstance(t, ast.Name):
                            inner.names.add(t.id)
                resolver = _Resolver(inner)
                for k, gen in enumerate(n.generators):
                    if k > 0:
                        resolver.run_expr(gen.iter)
                    for cond in gen.ifs:
                        resolver.run_expr(cond)
                if isinstance(n, ast.DictComp):
                    resolver.run_expr(n.key)
                    resolver.run_expr(n.value)
                else:
                    resolver.run_expr(n.elt)
                return
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.arguments,)):
                    continue
                walk(child)

        return walk

    class _Resolver:
        def __init__(self, scope):
            self.scope = scope
            self.walker = visit_scope([], scope)

        def run(self, statements):
            for stmt in statements:
                self.walker(stmt)

        def run_expr(self, expr):
            self.walker(expr)

    bind_body(module_scope, tree.body)
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Global):
            module_scope.names.update(
                n for n in stmt.names if n in global_assigned)
    # names declared 'global' inside functions and assigned there count
    # as module level definitions
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            declared = set()
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Global):
                    declared.update(sub.names)
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Name) and \
                        isinstance(sub.ctx, ast.Store) and sub.id in declared:
                    global_assigned.add(sub.id)
    _Resolver(module_scope).run(tree.body)
    return problems


# ---------------------------------------------------------------------
# AST checks
# ---------------------------------------------------------------------

def _all_defined_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _function_names(tree):
    """(first line, last line, names defined inside) for every function."""
    spans = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = set(_arg_names(fn.args))
            for sub in ast.walk(fn):
                if isinstance(sub, ast.Name) and \
                        isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
            spans.append((fn.lineno, fn.end_lineno or fn.lineno, names))
    return spans


def _best_match(name, pool):
    scored = sorted(
        ((difflib.SequenceMatcher(None, name, cand).ratio(), cand)
         for cand in pool), reverse=True)
    scored = [(r, c) for r, c in scored if r >= 0.75]
    if not scored:
        return None
    if len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.06:
        return scored[0][1]
    return None


def _undefined_issue(node, src, defined, spans):
    name = node.id
    edit = None
    note = f"Define '{name}' before using it."
    if name in KNOWN_MODULES:
        edit = {"start": 0, "end": 0, "text": "", "ensure": f"import {name}"}
        note = f"Add 'import {name}' at the top of the file."
    else:
        local = set()
        for first, last, names in spans:
            if first <= node.lineno <= last:
                local = names  # keep the innermost (last matching) span
        match = _best_match(name, sorted(local - {name})) or \
            _best_match(name, sorted((defined | BUILTIN_NAMES) - {name}))
        if match:
            start = src.start(node)
            edit = {"start": start, "end": start + len(name), "text": match}
            note = f"Probably a typo: did you mean '{match}'?"
    return make_issue(
        "Undefined Variable", node.lineno, "high",
        f"Variable '{name}' is used but never defined.", note,
        column=node.col_offset + 1, category="bug",
        root_cause=f"'{name}' has no definition in any visible scope.",
        edit=edit, rule="undefined_variable")


def _operator_span(src, left, right, pattern):
    """Find an operator keyword between two single-line operands."""
    if left.end_lineno != right.lineno:
        return None
    a, b = src.end(left), src.start(right)
    m = re.search(pattern, src.code[a:b])
    if not m:
        return None
    return a + m.start(), a + m.end()


def _assignments_count(tree):
    counts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx,
                                                     (ast.Store, ast.Del)):
            counts[node.id] = counts.get(node.id, 0) + 1
        elif isinstance(node, ast.arg):
            counts[node.arg] = counts.get(node.arg, 0) + 1
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef,
                               ast.AsyncFunctionDef)):
            counts[node.name] = counts.get(node.name, 0) + 1
    return counts


def _mutated_names(tree):
    mutated = set()
    mutators = {"append", "extend", "insert", "pop", "remove", "clear",
                "__setitem__", "__delitem__", "add", "discard", "update"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in mutators and \
                    isinstance(node.func.value, ast.Name):
                mutated.add(node.func.value.id)
        elif isinstance(node, ast.AugAssign) and \
                isinstance(node.target, ast.Name):
            mutated.add(node.target.id)
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Name):
                        mutated.add(sub.id)
    return mutated


def _body_indent(src, stmt):
    return src.lines[stmt.lineno - 1][:stmt.col_offset]


def ast_issues(code, tree):
    src = _Source(code)
    issues = []
    defined = _all_defined_names(tree)
    store_counts = _assignments_count(tree)
    mutated = _mutated_names(tree)

    # undefined names
    spans = _function_names(tree)
    for node in find_undefined_names(tree):
        issues.append(_undefined_issue(node, src, defined, spans))

    # variables assigned zero exactly once and never changed
    zero_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is \
                not None:
            v = node.value
            if isinstance(v, ast.Constant) and type(v.value) in (int, float) \
                    and v.value == 0:
                targets = node.targets if isinstance(node, ast.Assign) \
                    else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name) and \
                            store_counts.get(t.id) == 1 and \
                            t.id not in mutated:
                        zero_vars.add(t.id)

    # lists whose length can be trusted
    list_lengths = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and \
                isinstance(node.value, (ast.List, ast.Tuple)):
            if any(isinstance(e, ast.Starred) for e in node.value.elts):
                continue
            for t in node.targets:
                if isinstance(t, ast.Name) and store_counts.get(t.id) == 1 \
                        and t.id not in mutated:
                    list_lengths[t.id] = len(node.value.elts)

    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    def guarded(node, name):
        """True if an enclosing if/ternary/and already tests ``name``."""
        current = parents.get(node)
        while current is not None:
            test = None
            if isinstance(current, (ast.If, ast.IfExp, ast.While)):
                test = current.test
            elif isinstance(current, ast.BoolOp):
                test = current
            if test is not None and any(
                    isinstance(n, ast.Name) and n.id == name
                    for n in ast.walk(test)):
                return True
            current = parents.get(current)
        return False

    for node in ast.walk(tree):
        # division / modulo by zero
        if isinstance(node, ast.BinOp) and \
                isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            r = node.right
            literal = isinstance(r, ast.Constant) and \
                type(r.value) in (int, float) and r.value == 0
            variable = isinstance(r, ast.Name) and r.id in zero_vars \
                and not guarded(node, r.id)
            if literal or variable:
                edit = None
                if variable and node.lineno == node.end_lineno:
                    symbol = {ast.Div: "/", ast.FloorDiv: "//",
                              ast.Mod: "%"}[type(node.op)]
                    left = ast.get_source_segment(src.code, node.left)
                    if left is not None:
                        edit = {"start": src.start(node),
                                "end": src.end(node),
                                "text": f"({left} {symbol} {r.id} if "
                                        f"{r.id} != 0 else 0)"}
                issues.append(make_issue(
                    "Division By Zero", node.lineno, "critical",
                    "Division by zero detected.",
                    "Check that the divisor is not zero before dividing. "
                    "The automatic fix returns 0 when the divisor is 0; "
                    "change that value if your program needs something "
                    "else.",
                    column=node.col_offset + 1, category="bug",
                    root_cause="The divisor is zero, so Python raises "
                               "ZeroDivisionError.", edit=edit,
                    rule="division_by_zero"))

        # index out of range on a list of known length
        if isinstance(node, ast.Subscript) and \
                isinstance(node.value, ast.Name):
            idx = node.slice
            if node.value.id in list_lengths and \
                    isinstance(idx, ast.Constant) and type(idx.value) is int:
                length = list_lengths[node.value.id]
                if idx.value >= length or idx.value < -length:
                    issues.append(make_issue(
                        "Index Out Of Range", node.lineno, "high",
                        f"List '{node.value.id}' has {length} element(s) "
                        f"but index {idx.value} is used.",
                        "Use a valid index or check len() first.",
                        column=node.col_offset + 1, category="bug",
                        root_cause=f"Index {idx.value} is outside the list.",
                        rule="index_out_of_range"))

        # eval()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "eval":
            start = src.start(node.func)
            issues.append(make_issue(
                "Dangerous Function", node.lineno, "high",
                "eval() executes arbitrary code.",
                "Use ast.literal_eval() for data, or parse the input "
                "explicitly.",
                column=node.col_offset + 1, category="security",
                root_cause="eval() runs whatever text it receives.",
                edit={"start": start, "end": start + 4,
                      "text": "ast.literal_eval", "ensure": "import ast"},
                rule="dangerous_eval"))

        # comparison with None / literals
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op, right = node.ops[0], node.comparators[0]
            if isinstance(op, (ast.Eq, ast.NotEq)) and \
                    isinstance(right, ast.Constant) and right.value is None:
                span = _operator_span(src, node.left, right,
                                      r"==|!=")
                edit = None
                if span:
                    edit = {"start": span[0], "end": span[1],
                            "text": "is" if isinstance(op, ast.Eq)
                            else "is not"}
                issues.append(make_issue(
                    "Comparison With None", node.lineno, "low",
                    "None should be compared with 'is' / 'is not'.",
                    "Replace '== None' with 'is None'.",
                    column=node.col_offset + 1, category="style",
                    edit=edit, rule="compare_none"))
            if isinstance(op, (ast.Is, ast.IsNot)) and \
                    isinstance(right, ast.Constant) and \
                    right.value is not None and \
                    not isinstance(right.value, (bool, type(Ellipsis))):
                span = _operator_span(src, node.left, right,
                                      r"\bis\s+not\b|\bis\b")
                edit = None
                if span:
                    edit = {"start": span[0], "end": span[1],
                            "text": "==" if isinstance(op, ast.Is) else "!="}
                issues.append(make_issue(
                    "Identity Comparison With Literal", node.lineno, "high",
                    "'is' compares object identity, not value, so "
                    "comparing with a literal is unreliable.",
                    "Use '==' to compare values.",
                    column=node.col_offset + 1, category="bug",
                    edit=edit, rule="is_literal"))

        # "text" + 5
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            l, r = node.left, node.right
            def kind(x):
                if isinstance(x, ast.Constant):
                    if isinstance(x.value, str):
                        return "str"
                    if type(x.value) in (int, float):
                        return "num"
                return None
            if {kind(l), kind(r)} == {"str", "num"}:
                issues.append(make_issue(
                    "Type Error", node.lineno, "high",
                    "A string and a number are added with '+'.",
                    "Convert the number with str(), or use an f-string.",
                    column=node.col_offset + 1, category="bug",
                    root_cause="Python cannot add str and int/float.",
                    rule="str_plus_number"))

        # int("abc")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("int", "float") and len(node.args) == 1 \
                and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            text = node.args[0].value.strip()
            try:
                (int if node.func.id == "int" else float)(text)
            except ValueError:
                issues.append(make_issue(
                    "Invalid Conversion", node.lineno, "high",
                    f"{node.func.id}({node.args[0].value!r}) always raises "
                    "ValueError.",
                    "Pass a numeric string, or validate the text first.",
                    column=node.col_offset + 1, category="bug",
                    rule="invalid_conversion"))

        # exception handlers
        if isinstance(node, ast.ExceptHandler):
            issues.extend(_handler_issues(node, src))

        # mutable default arguments
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            issues.extend(_mutable_default_issues(node, src))

        # unreachable statements
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list):
                for k, stmt in enumerate(block[:-1]):
                    if isinstance(stmt, (ast.Return, ast.Raise, ast.Break,
                                         ast.Continue)):
                        nxt = block[k + 1]
                        issues.append(make_issue(
                            "Unreachable Code", nxt.lineno, "medium",
                            f"This code can never run: line {stmt.lineno} "
                            "always leaves the block first.",
                            "Remove the unreachable statements or "
                            "restructure the logic.",
                            column=nxt.col_offset + 1, category="bug",
                            rule="unreachable_code"))
                        break
    return issues


def _handler_issues(node, src):
    issues = []
    only_pass = all(isinstance(s, ast.Pass) or
                    (isinstance(s, ast.Expr) and
                     isinstance(s.value, ast.Constant) and
                     s.value.value is Ellipsis)
                    for s in node.body)
    bare = node.type is None
    if not (bare or only_pass):
        return issues

    type_src = ast.get_source_segment(src.code, node.type) if node.type \
        else "Exception"
    name = node.name or "e"
    header = f"except {type_src} as {name}:"
    first = node.body[0]
    one_line = first.lineno == node.lineno

    edit = None
    if not one_line:
        start = src.start(node)
        header_end = src.offset(first.lineno, 0)
        header_text = src.code[start:header_end]
        colon = header_text.rfind(":")
        if only_pass:
            end = src.end(node.body[-1])
            indent = _body_indent(src, first)
            edit = {"start": start, "end": end,
                    "text": f"{header}\n{indent}"
                            f'print(f"Error: {{{name}}}")'}
        elif colon != -1 and bare:
            edit = {"start": start, "end": start + colon + 1, "text": header}

    if bare:
        issues.append(make_issue(
            "Bare Except", node.lineno, "medium",
            "'except:' catches every exception, including Ctrl+C and "
            "SystemExit.",
            "Catch 'Exception' (or something more specific) and handle it.",
            column=node.col_offset + 1, category="bug",
            root_cause="A bare except hides unrelated errors.",
            edit=edit, rule="bare_except"))
    else:
        issues.append(make_issue(
            "Empty Exception Handler", node.lineno, "medium",
            "The except block does nothing, so the error is silently "
            "swallowed.",
            "Log or handle the exception instead of ignoring it.",
            column=node.col_offset + 1, category="bug",
            root_cause="Swallowed exceptions hide failures.",
            edit=edit, rule="empty_except"))
    return issues


def _mutable_default_issues(fn, src):
    issues = []
    positional = fn.args.posonlyargs + fn.args.args
    pairs = list(zip(positional[len(positional) - len(fn.args.defaults):],
                     fn.args.defaults))
    pairs += [(a, d) for a, d in zip(fn.args.kwonlyargs,
                                     fn.args.kw_defaults) if d is not None]
    for arg, default in pairs:
        mutable = isinstance(default, (ast.List, ast.Dict, ast.Set)) or (
            isinstance(default, ast.Call) and isinstance(default.func,
                                                         ast.Name)
            and default.func.id in ("list", "dict", "set"))
        if not mutable:
            continue
        edit = None
        first = fn.body[0]
        has_doc = isinstance(first, ast.Expr) and \
            isinstance(first.value, ast.Constant) and \
            isinstance(first.value.value, str)
        anchor = fn.body[1] if has_doc and len(fn.body) > 1 else \
            (None if has_doc else first)
        if anchor is not None and anchor.lineno > fn.lineno and \
                default.lineno == default.end_lineno:
            original = ast.get_source_segment(src.code, default)
            indent = _body_indent(src, anchor)
            insert_at = src.offset(anchor.lineno, 0)
            edit = [
                {"start": src.start(default), "end": src.end(default),
                 "text": "None"},
                {"start": insert_at, "end": insert_at,
                 "text": f"{indent}if {arg.arg} is None:\n"
                         f"{indent}    {arg.arg} = {original}\n"},
            ]
        issues.append(make_issue(
            "Mutable Default Argument", default.lineno, "medium",
            f"The default value of '{arg.arg}' is a mutable object that "
            "is shared between calls.",
            "Use None as the default and create the object inside the "
            "function.",
            column=default.col_offset + 1, category="bug",
            root_cause="Default values are created once, so changes "
                       "persist between calls.",
            edit=edit, rule="mutable_default"))
    return issues


# ---------------------------------------------------------------------
# review checks (style)
# ---------------------------------------------------------------------

def review_issues(code, tree):
    src = _Source(code)
    issues = []
    used = {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    has_all = "__all__" in code

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if any(c.isupper() for c in name) and "_" not in name and \
                    not name.startswith("__") and not name[0].isupper():
                issues.append(make_issue(
                    "Naming Convention", node.lineno, "low",
                    f'Use snake_case instead of camelCase: "{name}".',
                    "Python convention: use snake_case for function names.",
                    category="style", rule="naming_function"))
            if ast.get_docstring(node) is None and not name.startswith("_"):
                issues.append(make_issue(
                    "Missing Docstring", node.lineno, "low",
                    f'"{name}" has no docstring.',
                    "Add a docstring explaining its purpose.",
                    category="style", rule="missing_docstring"))
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > 80:
                issues.append(make_issue(
                    "Long Function", node.lineno, "low",
                    f'"{name}" is {length} lines long.',
                    "Split it into smaller functions.",
                    category="style", rule="long_function"))
            params = len(node.args.args) + len(node.args.kwonlyargs)
            if params > 7:
                issues.append(make_issue(
                    "Too Many Parameters", node.lineno, "low",
                    f'"{name}" takes {params} parameters.',
                    "Group related parameters into an object.",
                    category="style", rule="many_params"))
        elif isinstance(node, ast.ClassDef):
            if ast.get_docstring(node) is None and not node.name.startswith("_"):
                issues.append(make_issue(
                    "Missing Docstring", node.lineno, "low",
                    f'"{node.name}" has no docstring.',
                    "Add a docstring explaining its purpose.",
                    category="style", rule="missing_docstring"))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            name = node.id
            if any(c.isupper() for c in name[1:]) and "_" not in name and \
                    not name.isupper() and name[0].islower():
                issues.append(make_issue(
                    "Naming Convention", node.lineno, "low",
                    f'Use snake_case instead of camelCase: "{name}".',
                    "Python convention: use snake_case for variable names.",
                    category="style", rule="naming_variable"))

    # deep nesting
    nested = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
              ast.AsyncWith)

    def depth_walk(stmts, depth):
        for stmt in stmts:
            d = depth
            if isinstance(stmt, nested):
                d = depth + 1
                if d > 4:
                    issues.append(make_issue(
                        "High Complexity", stmt.lineno, "medium",
                        f"Code is deeply nested (depth {d}).",
                        "Refactor nested blocks into smaller functions.",
                        category="style", rule="deep_nesting"))
                    return
            for fld in ("body", "orelse", "finalbody"):
                child = getattr(stmt, fld, None)
                if isinstance(child, list):
                    depth_walk(child, d)
            for handler in getattr(stmt, "handlers", []):
                depth_walk(handler.body, d)

    depth_walk(tree.body, 0)

    # unused imports
    if not has_all:
        parents = {}
        for p in ast.walk(tree):
            for c in ast.iter_child_nodes(p):
                parents[c] = p
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            if isinstance(parents.get(node), ast.Try):
                continue
            entries = []
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name.split(".")[0] \
                    if isinstance(node, ast.Import) else \
                    (alias.asname or alias.name)
                entries.append((alias, bound))
            unused = [(a, b) for a, b in entries if b not in used]
            if not unused:
                continue
            all_unused = len(unused) == len(entries)
            edit = None
            if node.end_lineno >= node.lineno:
                line_start = src.offset(node.lineno, 0)
                if all_unused:
                    end = src.line_end(node.end_lineno) + 1
                    # keep the file valid when the import is the only
                    # statement of a block
                    block = getattr(parents.get(node), "body", [])
                    if not (len(block) == 1 and block[0] is node):
                        edit = {"start": line_start,
                                "end": min(end, len(code)), "text": ""}
                else:
                    keep = [a for a, b in entries if b in used]
                    parts = ", ".join(
                        a.name + (f" as {a.asname}" if a.asname else "")
                        for a in keep)
                    prefix = "import " if isinstance(node, ast.Import) else \
                        f"from {'.' * node.level}{node.module or ''} import "
                    indent = _body_indent(src, node)
                    edit = {"start": src.start(node), "end": src.end(node),
                            "text": prefix + parts}
            for alias, bound in unused:
                issues.append(make_issue(
                    "Unused Import", node.lineno, "low",
                    f'Import "{bound}" is never used.',
                    f"Remove the unused import: {bound}.",
                    category="style", edit=edit, rule="unused_import"))
    return issues


# ---------------------------------------------------------------------
# syntax errors
# ---------------------------------------------------------------------

_BLOCK_START = re.compile(
    r"^\s*(if|elif|else|for|while|def|class|try|except|finally|with|async\s+def|"
    r"async\s+for|async\s+with|match|case)\b")


def _syntax_issue_from_exception(code, err):
    lines = code.split("\n")
    line_no = err.lineno or 1
    msg = err.msg or "invalid syntax"
    line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
    starts = [0]
    for l in lines[:-1]:
        starts.append(starts[-1] + len(l) + 1)

    def line_end_idx(n):
        return starts[n - 1] + len(lines[n - 1].rstrip())

    edit = None
    note = "Fix the syntax error at the reported line."

    if "expected ':'" in msg or (
            msg == "invalid syntax" and _BLOCK_START.match(line_text)
            and not line_text.rstrip().endswith(":")
            and not line_text.rstrip().endswith(("(", "[", "{", ","))):
        if 1 <= line_no <= len(lines):
            idx = line_end_idx(line_no)
            edit = {"start": idx, "end": idx, "text": ":"}
            note = "Add the missing ':' at the end of the line."
    elif "Missing parentheses in call to 'print'" in msg:
        m = re.match(r"^(\s*)print\s+(.*?)\s*$", line_text)
        if m:
            s = starts[line_no - 1]
            edit = {"start": s, "end": s + len(line_text.rstrip()),
                    "text": f"{m.group(1)}print({m.group(2)})"}
            note = "In Python 3, print is a function: use print(...)."
    elif "Maybe you meant '=='" in msg or "cannot assign" in msg or \
            ("invalid syntax" in msg and re.match(
                r"^\s*(if|elif|while)\b.*[^=!<>]=[^=].*:\s*$", line_text)):
        m = re.match(r"^(\s*(?:if|elif|while)\b[^=\n]*?)(?<![=!<>:])=(?!=)",
                     line_text)
        if m:
            s = starts[line_no - 1] + len(m.group(1))
            edit = {"start": s, "end": s + 1, "text": "=="}
            note = "Use '==' to compare values; '=' assigns."
    elif "expected an indented block" in msg:
        prev = line_no - 1
        while prev >= 1 and not lines[prev - 1].strip():
            prev -= 1
        if prev >= 1:
            indent = re.match(r"\s*", lines[prev - 1]).group(0)
            idx = line_end_idx(prev)
            edit = {"start": idx, "end": idx,
                    "text": f"\n{indent}    pass"}
            note = "Add an indented statement (here 'pass') to the block."

    return make_issue(
        "Syntax Error", line_no, "critical", msg[:1].upper() + msg[1:] + ".",
        note, column=err.offset or 1, category="syntax",
        root_cause="The code is not valid Python.", source="python",
        edit=edit, rule="python_syntax")


def analyze_python(code):
    heuristic, sc = analyze_text(code, "python")
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError) as err:
        syntax = [i for i in heuristic if i["category"] == "syntax"]
        if isinstance(err, SyntaxError):
            if not syntax:
                syntax = [_syntax_issue_from_exception(code, err)]
            else:
                for issue in syntax:
                    issue["confirmed_by"] = "python"
        else:
            syntax = [make_issue(
                "Syntax Error", 1, "critical", str(err),
                "Fix the syntax error.", category="syntax",
                rule="python_syntax")]
        others = [i for i in heuristic if i["category"] != "syntax"]
        return {"issues": syntax + others, "review_issues": [], "scan": sc,
                "engines": ["Python parser"], "syntax_ok": False}

    issues = [i for i in heuristic if i["category"] != "syntax"]
    issues += ast_issues(code, tree)
    review = review_issues(code, tree)
    bugs = [i for i in issues if i["category"] != "style"]
    review += [i for i in issues if i["category"] == "style"]
    return {"issues": bugs, "review_issues": review, "scan": sc,
            "engines": ["Python AST"], "syntax_ok": True}
