
import ast
import builtins


class BugDetector:
    """Detect common Python issues using lightweight static analysis."""

    def detect(self, code):
        bugs = []

        # 1. Parse source code.
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError, TypeError) as exc:
            return {
                "total_bugs": 1,
                "bugs": [{
                    "type": "Syntax Error",
                    "line": getattr(exc, "lineno", None) or 1,
                    "column": getattr(exc, "offset", None) or 1,
                    "severity": "critical",
                    "message": str(getattr(exc, "msg", None) or exc),
                    "root_cause": "The source code could not be parsed.",
                    "suggestion": "Fix the syntax or invalid source input."
                }]
            }

        builtin_names = set(dir(builtins))
        builtin_names.update({"True", "False", "None"})

        def add_bug(kind, node, severity, message, root_cause, suggestion):
            bugs.append({
                "type": kind,
                "line": getattr(node, "lineno", 1),
                "column": getattr(node, "col_offset", 0) + 1,
                "severity": severity,
                "message": message,
                "root_cause": root_cause,
                "suggestion": suggestion
            })

        # 2. Collect module-level definitions.
        module_names = set()

        for statement in tree.body:
            if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                module_names.add(statement.name)

            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                for alias in statement.names:
                    if alias.name == "*":
                        continue

                    if alias.asname:
                        module_names.add(alias.asname)
                    elif isinstance(statement, ast.Import):
                        module_names.add(alias.name.split(".")[0])
                    else:
                        module_names.add(alias.name)

            elif isinstance(
                statement,
                (ast.Assign, ast.AnnAssign, ast.AugAssign)
            ):
                targets = (
                    statement.targets
                    if isinstance(statement, ast.Assign)
                    else [statement.target]
                )
                for target in targets:
                    for child in ast.walk(target):
                        if isinstance(child, ast.Name):
                            module_names.add(child.id)

            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                for child in ast.walk(statement.target):
                    if isinstance(child, ast.Name):
                        module_names.add(child.id)

        # 3. Collect function scopes.
        function_locals = {}
        function_globals = {}
        function_nonlocals = {}

        class ScopeCollector(ast.NodeVisitor):
            def __init__(self, root):
                self.root = root
                self.locals = set()
                self.globals = set()
                self.nonlocals = set()

            def visit_FunctionDef(self, node):
                if node is not self.root:
                    self.locals.add(node.name)
                    return
                for child in node.body:
                    self.visit(child)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                if node is not self.root:
                    self.locals.add(node.name)
                    return
                for child in node.body:
                    self.visit(child)

            def visit_Lambda(self, node):
                # Do not mix lambda-local names into the outer scope.
                return

            def visit_Name(self, node):
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    self.locals.add(node.id)

            def visit_Global(self, node):
                self.globals.update(node.names)

            def visit_Nonlocal(self, node):
                self.nonlocals.update(node.names)

            def visit_ExceptHandler(self, node):
                if node.name:
                    self.locals.add(node.name)
                for child in node.body:
                    self.visit(child)

        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue

            collector = ScopeCollector(node)

            args = (
                node.args.posonlyargs
                + node.args.args
                + node.args.kwonlyargs
            )
            collector.locals.update(arg.arg for arg in args)

            if node.args.vararg:
                collector.locals.add(node.args.vararg.arg)
            if node.args.kwarg:
                collector.locals.add(node.args.kwarg.arg)

            collector.visit(node)

            function_locals[id(node)] = (
                collector.locals
                - collector.globals
                - collector.nonlocals
            )
            function_globals[id(node)] = collector.globals
            function_nonlocals[id(node)] = collector.nonlocals

        # 4. Build parent relationships.
        parent_map = {}

        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent

        def enclosing_function(node):
            parent = parent_map.get(node)
            while parent is not None:
                if isinstance(
                    parent, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    return parent
                parent = parent_map.get(parent)
            return None

        # 5. Collect simple zero assignments and list lengths.
        zero_variables = set()
        list_lengths = {}

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                )

                if (
                    isinstance(value, ast.Constant)
                    and type(value.value) in (int, float)
                    and value.value == 0
                ):
                    for target in targets:
                        if isinstance(target, ast.Name):
                            zero_variables.add(target.id)

                if isinstance(value, (ast.List, ast.Tuple)):
                    for target in targets:
                        if isinstance(target, ast.Name):
                            list_lengths[target.id] = len(value.elts)

        # 6. Recognize simple zero guards that stop execution.
        def is_zero_comparison(test, variable):
            if not isinstance(test, ast.Compare):
                return False

            if len(test.ops) != 1 or len(test.comparators) != 1:
                return False

            left = test.left
            right = test.comparators[0]

            left_is_var = (
                isinstance(left, ast.Name) and left.id == variable
            )
            right_is_var = (
                isinstance(right, ast.Name) and right.id == variable
            )
            left_is_zero = (
                isinstance(left, ast.Constant)
                and type(left.value) in (int, float)
                and left.value == 0
            )
            right_is_zero = (
                isinstance(right, ast.Constant)
                and type(right.value) in (int, float)
                and right.value == 0
            )

            return (
                (left_is_var and right_is_zero)
                or (right_is_var and left_is_zero)
            ) and isinstance(test.ops[0], (ast.Eq, ast.Is))

        def terminates_branch(statements):
            """Conservatively check whether a branch stops on every path."""
            if not statements:
                return False

            last = statements[-1]

            if isinstance(last, (ast.Raise, ast.Return)):
                return True

            if isinstance(last, ast.If):
                return (
                    terminates_branch(last.body)
                    and terminates_branch(last.orelse)
                )

            return False

        def guard_protects_divisor(div_node, variable):
            function = enclosing_function(div_node)
            if function is None:
                return False

            # Find the direct statement containing the division.
            current = div_node
            while parent_map.get(current) is not function:
                current = parent_map.get(current)
                if current not in parent_map:
                    return False

            # Check earlier statements in the same function body.
            if current not in function.body:
                return False

            position = function.body.index(current)

            for statement in function.body[:position]:
                if (
                    isinstance(statement, ast.If)
                    and is_zero_comparison(statement.test, variable)
                    and terminates_branch(statement.body)
                ):
                    return True

            # Also handle a division inside the else branch of a zero check:
            # if b == 0: raise ValueError(...)
            # else: return a / b
            parent = parent_map.get(current)

            while parent is not None and parent is not function:
                if isinstance(parent, ast.If):
                    if (
                        current in parent.orelse
                        and is_zero_comparison(parent.test, variable)
                        and terminates_branch(parent.body)
                    ):
                        return True
                current = parent
                parent = parent_map.get(parent)

            return False

        # 7. Detect credentials and empty exception handlers.
        password_names = {
            "password", "passwd", "pwd", "secret",
            "api_key", "apikey", "access_token"
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                )
                value = node.value

                if (
                    isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                    and value.value.strip()
                ):
                    names = {
                        child.id.lower()
                        for target in targets
                        for child in ast.walk(target)
                        if isinstance(child, ast.Name)
                    }

                    if names & password_names:
                        add_bug(
                            "Hardcoded Password", node, "high",
                            "A password or secret appears hardcoded.",
                            "Sensitive credentials may be stored in source code.",
                            "Load credentials from environment variables or a secret manager."
                        )

            if isinstance(node, ast.ExceptHandler):
                if (
                    len(node.body) == 1
                    and isinstance(node.body[0], ast.Pass)
                ):
                    add_bug(
                        "Empty Except Block", node, "medium",
                        "The except block silently ignores an exception.",
                        "The exception is caught without handling or reporting it.",
                        "Handle the exception explicitly or log the error."
                    )

        # 8. Detect common issues.
        for node in ast.walk(tree):

            # Undefined-name heuristic.
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                name = node.id

                if name in builtin_names:
                    continue

                function = enclosing_function(node)

                if function is None:
                    known = name in module_names
                else:
                    known = (
                        name in function_locals.get(id(function), set())
                        or name in function_globals.get(id(function), set())
                        or name in function_nonlocals.get(id(function), set())
                        or name in module_names
                    )

                if not known:
                    add_bug(
                        "Undefined Variable", node, "high",
                        f"Variable '{name}' may be used before being defined.",
                        f"No definition for '{name}' was found in the analyzed scope.",
                        f"Define '{name}' or check its spelling and scope."
                    )

            # Division, floor division and modulo.
            if (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))
            ):
                right = node.right

                literal_zero = (
                    isinstance(right, ast.Constant)
                    and type(right.value) in (int, float)
                    and right.value == 0
                )
                signed_zero = (
                    isinstance(right, ast.UnaryOp)
                    and isinstance(right.op, (ast.UAdd, ast.USub))
                    and isinstance(right.operand, ast.Constant)
                    and type(right.operand.value) in (int, float)
                    and right.operand.value == 0
                )
                variable_zero = (
                    isinstance(right, ast.Name)
                    and right.id in zero_variables
                )

                if literal_zero or signed_zero or variable_zero:
                    add_bug(
                        "Division By Zero", node, "critical",
                        "Division or modulo by zero detected.",
                        "The divisor is zero according to this simple static check.",
                        "Check that the divisor is non-zero before calculation."
                    )

                elif isinstance(right, ast.Name):
                    if not guard_protects_divisor(node, right.id):
                        add_bug(
                            "Potential Division By Zero", node, "medium",
                            f"Variable '{right.id}' may be zero when used as a divisor.",
                            "Static analysis cannot prove that the divisor is non-zero.",
                            f"Validate '{right.id}' before performing this operation."
                        )

            # Simple constant list/tuple index checks.
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
            ):
                variable = node.value.id
                index = node.slice

                if (
                    variable in list_lengths
                    and isinstance(index, ast.Constant)
                    and type(index.value) is int
                ):
                    length = list_lengths[variable]

                    if index.value >= length or index.value < -length:
                        add_bug(
                            "Index Out Of Range", node, "high",
                            f"Index {index.value} is outside the known bounds of '{variable}' (length {length}).",
                            "The constant index is outside the list or tuple bounds.",
                            "Use a valid index or check the collection length."
                        )

            # Potentially unsafe eval.
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "eval"
            ):
                add_bug(
                    "Dangerous Function", node, "high",
                    "eval() can execute dynamically supplied expressions.",
                    "Dynamic evaluation can become unsafe with untrusted input.",
                    "Avoid eval() for untrusted input; use a safe parser or explicit logic."
                )

        # 9. Remove duplicate findings.
        unique_bugs = []
        seen = set()

        for bug in bugs:
            key = (bug["type"], bug["line"], bug["column"])
            if key not in seen:
                seen.add(key)
                unique_bugs.append(bug)

        return {
            "total_bugs": len(unique_bugs),
            "bugs": unique_bugs
        }
