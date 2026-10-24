import ast
import builtins


class BugDetector:
    def detect(self, code):
        bugs = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {
                "total_bugs": 1,
                "bugs": [{
                    "type": "Syntax Error",
                    "line": e.lineno or 1,
                    "column": e.offset or 1,
                    "severity": "critical",
                    "message": e.msg,
                    "root_cause": "Invalid Python syntax.",
                    "suggestion": "Fix the syntax error at the reported line."
                }]
            }

        builtin_names = set(dir(builtins))
        builtin_names.update({"True", "False", "None"})

        # Collect module-level names only.
        module_names = set()
        for statement in tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                module_names.add(statement.name)
            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                for alias in statement.names:
                    if alias.name != "*":
                        module_names.add(
                            alias.asname or (
                                alias.name.split(".")[0]
                                if isinstance(statement, ast.Import)
                                else alias.name
                            )
                        )
            elif isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    for child in ast.walk(target):
                        if isinstance(child, ast.Name):
                            module_names.add(child.id)
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                for child in ast.walk(statement.target):
                    if isinstance(child, ast.Name):
                        module_names.add(child.id)

        # Find names local to each function independently.
        function_locals = {}
        function_globals = {}

        class ScopeCollector(ast.NodeVisitor):
            def __init__(self):
                self.locals = set()
                self.globals = set()
                self.nonlocals = set()

            def visit_Global(self, node):
                self.globals.update(node.names)

            def visit_Nonlocal(self, node):
                self.nonlocals.update(node.names)

            def visit_FunctionDef(self, node):
                # Nested function name belongs to the current scope.
                self.locals.add(node.name)
                # Do not include nested function body in this scope.
                for decorator in node.decorator_list:
                    self.visit(decorator)
                for default in node.args.defaults + node.args.kw_defaults:
                    if default is not None:
                        self.visit(default)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                self.locals.add(node.name)

            def visit_Lambda(self, node):
                # Lambda body has its own scope.
                return

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                collector = ScopeCollector()
                # Arguments are local variables.
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

                # Collect assignments and references in this function,
                # without descending into nested functions or classes.
                class FunctionBodyCollector(ast.NodeVisitor):
                    def visit_FunctionDef(self, child):
                        if child is node:
                            for item in child.body:
                                self.visit(item)
                        else:
                            collector.locals.add(child.name)

                    visit_AsyncFunctionDef = visit_FunctionDef

                    def visit_ClassDef(self, child):
                        collector.locals.add(child.name)

                    def visit_Name(self, child):
                        if isinstance(child.ctx, (ast.Store, ast.Del)):
                            collector.locals.add(child.id)

                    def visit_Global(self, child):
                        collector.globals.update(child.names)

                    def visit_Nonlocal(self, child):
                        collector.nonlocals.update(child.names)

                FunctionBodyCollector().visit(node)
                function_locals[id(node)] = (
                    collector.locals - collector.globals - collector.nonlocals
                )
                function_globals[id(node)] = collector.globals

        # Detect division by literal zero or a simply assigned zero.
        zero_variables = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                is_zero = (
                    isinstance(value, ast.Constant)
                    and type(value.value) in (int, float)
                    and value.value == 0
                )
                if is_zero:
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            zero_variables.add(target.id)

        # Detect simple list/tuple index errors.
        list_lengths = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        list_lengths[target.id] = len(node.value.elts)

        # Undefined-name checks, using nearest enclosing function scope.
        parent_map = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                name = node.id
                if name in builtin_names:
                    continue

                parent = parent_map.get(node)
                current_function = None
                while parent is not None:
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        current_function = parent
                        break
                    parent = parent_map.get(parent)

                if current_function is not None:
                    local_names = function_locals.get(id(current_function), set())
                    global_names = function_globals.get(id(current_function), set())
                    is_known = (
                        name in local_names
                        or name in global_names
                        or name in module_names
                    )
                else:
                    is_known = name in module_names

                if not is_known:
                    bugs.append({
                        "type": "Undefined Variable",
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "severity": "high",
                        "message": f"Variable '{name}' is used before being defined.",
                        "root_cause": f"Variable '{name}' has no known definition in the analyzed scope.",
                        "suggestion": f"Define '{name}' before using it."
                    })

            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                right = node.right
                literal_zero = (
                    isinstance(right, ast.Constant)
                    and type(right.value) in (int, float)
                    and right.value == 0
                )
                variable_zero = isinstance(right, ast.Name) and right.id in zero_variables
                if literal_zero or variable_zero:
                    bugs.append({
                        "type": "Division By Zero",
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "severity": "critical",
                        "message": "Division by zero detected.",
                        "root_cause": "The divisor is zero.",
                        "suggestion": "Check that the divisor is not zero before calculation."
                    })

            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                variable = node.value.id
                index = node.slice
                if variable in list_lengths and isinstance(index, ast.Constant) and type(index.value) is int:
                    length = list_lengths[variable]
                    if index.value >= length or index.value < -length:
                        bugs.append({
                            "type": "Index Out Of Range",
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "severity": "high",
                            "message": f"List '{variable}' contains {length} elements, but index {index.value} was requested.",
                            "root_cause": f"Index {index.value} is outside the valid range.",
                            "suggestion": "Use a valid list index or check the list length."
                        })

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "eval":
                bugs.append({
                    "type": "Dangerous Function",
                    "line": node.lineno,
                    "column": node.col_offset + 1,
                    "severity": "high",
                    "message": "eval() can execute unsafe code.",
                    "root_cause": "Dynamic code execution through eval().",
                    "suggestion": "Avoid eval() and use safer alternatives."
                })

        unique_bugs = []
        seen = set()
        for bug in bugs:
            key = (bug["type"], bug["line"], bug["column"])
            if key not in seen:
                seen.add(key)
                unique_bugs.append(bug)

        return {"total_bugs": len(unique_bugs), "bugs": unique_bugs}