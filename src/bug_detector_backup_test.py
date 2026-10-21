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

        # ---------------------------------------------
        # COLLECT DEFINED VARIABLES
        # ---------------------------------------------

        defined_variables = set()

        for node in ast.walk(tree):

            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                )

                for target in targets:
                    for child in ast.walk(target):
                        if isinstance(child, ast.Name):
                            defined_variables.add(child.id)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined_variables.add(node.name)

                args = (
                    node.args.posonlyargs
                    + node.args.args
                    + node.args.kwonlyargs
                )

                for arg in args:
                    defined_variables.add(arg.arg)

                if node.args.vararg:
                    defined_variables.add(node.args.vararg.arg)

                if node.args.kwarg:
                    defined_variables.add(node.args.kwarg.arg)

            elif isinstance(node, ast.ClassDef):
                defined_variables.add(node.name)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined_variables.add(
                        alias.asname or alias.name.split(".")[0]
                    )

            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        defined_variables.add(alias.asname or alias.name)

            elif isinstance(node, (ast.For, ast.AsyncFor)):
                for child in ast.walk(node.target):
                    if isinstance(child, ast.Name):
                        defined_variables.add(child.id)

            elif isinstance(node, ast.ExceptHandler):
                if node.name:
                    defined_variables.add(node.name)

            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars:
                        for child in ast.walk(item.optional_vars):
                            if isinstance(child, ast.Name):
                                defined_variables.add(child.id)

        # ---------------------------------------------
        # COLLECT TOP-LEVEL DEFINITION LINES
        # ---------------------------------------------

        top_level_definitions = {}

        for statement in tree.body:

            if isinstance(statement, ast.Assign):
                targets = statement.targets

            elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
                targets = [statement.target]

            else:
                targets = []

            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child, ast.Name):
                        top_level_definitions.setdefault(
                            child.id, statement.lineno
                        )

            if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                top_level_definitions.setdefault(
                    statement.name, statement.lineno
                )

            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                for alias in statement.names:
                    if alias.name != "*":
                        imported_name = (
                            alias.asname
                            or (
                                alias.name.split(".")[0]
                                if isinstance(statement, ast.Import)
                                else alias.name
                            )
                        )
                        top_level_definitions.setdefault(
                            imported_name, statement.lineno
                        )

        # ---------------------------------------------
        # DETECT TOP-LEVEL USE BEFORE ASSIGNMENT
        # ---------------------------------------------

        for statement in tree.body:

            # Function and class bodies have separate execution rules.
            # Do not treat their bodies as immediately executed statements.
            if isinstance(
                statement,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Import,
                    ast.ImportFrom
                )
            ):
                continue

            if not isinstance(
                statement,
                (
                    ast.Expr,
                    ast.Assign,
                    ast.AnnAssign,
                    ast.AugAssign
                )
            ):
                continue

            for node in ast.walk(statement):

                if not (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                ):
                    continue

                name = node.id
                definition_line = top_level_definitions.get(name)

                if (
                    definition_line is not None
                    and definition_line > node.lineno
                    and name not in builtin_names
                ):
                    bugs.append({
                        "type": "Undefined Variable",
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "severity": "high",
                        "message": (
                            f"Variable '{name}' is used before being defined."
                        ),
                        "root_cause": (
                            f"Variable '{name}' is assigned later in the module."
                        ),
                        "suggestion": f"Define '{name}' before using it."
                    })

        # ---------------------------------------------
        # DETECT VARIABLES ASSIGNED ZERO
        # ---------------------------------------------

        zero_variables = set()

        for node in ast.walk(tree):

            if isinstance(node, ast.Assign):
                is_zero = (
                    isinstance(node.value, ast.Constant)
                    and type(node.value.value) in (int, float)
                    and node.value.value == 0
                )

                if is_zero:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            zero_variables.add(target.id)

            elif isinstance(node, ast.AnnAssign):
                is_zero = (
                    isinstance(node.value, ast.Constant)
                    and type(node.value.value) in (int, float)
                    and node.value.value == 0
                )

                if is_zero and isinstance(node.target, ast.Name):
                    zero_variables.add(node.target.id)

        # ---------------------------------------------
        # COLLECT SIMPLE LIST AND TUPLE LENGTHS
        # ---------------------------------------------

        list_lengths = {}

        for node in ast.walk(tree):

            if isinstance(node, ast.Assign) and isinstance(
                node.value, (ast.List, ast.Tuple)
            ):
                length = len(node.value.elts)

                for target in node.targets:
                    if isinstance(target, ast.Name):
                        list_lengths[target.id] = length

        # ---------------------------------------------
        # DETECT BUGS
        # ---------------------------------------------

        for node in ast.walk(tree):

            # DIVISION BY ZERO
            if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Div, ast.FloorDiv, ast.Mod)
            ):
                literal_zero = (
                    isinstance(node.right, ast.Constant)
                    and type(node.right.value) in (int, float)
                    and node.right.value == 0
                )

                variable_zero = (
                    isinstance(node.right, ast.Name)
                    and node.right.id in zero_variables
                )

                if literal_zero or variable_zero:
                    divisor = (
                        node.right.id if variable_zero else None
                    )

                    if divisor:
                        message = (
                            "Division by zero detected. "
                            f"Variable '{divisor}' has value 0."
                        )
                        root_cause = (
                            f"The divisor variable '{divisor}' "
                            "is assigned the value 0."
                        )
                    else:
                        message = "Division by zero detected."
                        root_cause = "The divisor is zero."

                    bugs.append({
                        "type": "Division By Zero",
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "severity": "critical",
                        "message": message,
                        "root_cause": root_cause,
                        "suggestion": (
                            "Check that the divisor is not zero "
                            "before calculation."
                        )
                    })

            # INDEX OUT OF RANGE
            if isinstance(node, ast.Subscript) and isinstance(
                node.value, ast.Name
            ):
                variable = node.value.id

                if variable in list_lengths:
                    index_value = None

                    if (
                        isinstance(node.slice, ast.Constant)
                        and type(node.slice.value) is int
                    ):
                        index_value = node.slice.value

                    if index_value is not None:
                        length = list_lengths[variable]

                        if (
                            index_value >= length
                            or index_value < -length
                        ):
                            bugs.append({
                                "type": "Index Out Of Range",
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "severity": "high",
                                "message": (
                                    f"List '{variable}' contains "
                                    f"{length} elements, but index "
                                    f"{index_value} was requested."
                                ),
                                "root_cause": (
                                    f"Index {index_value} is outside "
                                    "the valid range."
                                ),
                                "suggestion": (
                                    "Use a valid list index or "
                                    "check the list length."
                                )
                            })

            # UNDEFINED VARIABLE
            if isinstance(node, ast.Name) and isinstance(
                node.ctx, ast.Load
            ):
                name = node.id

                if (
                    name not in defined_variables
                    and name not in builtin_names
                ):
                    bugs.append({
                        "type": "Undefined Variable",
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "severity": "high",
                        "message": (
                            f"Variable '{name}' is used before being defined."
                        ),
                        "root_cause": (
                            f"Variable '{name}' has no known "
                            "definition in the analyzed code."
                        ),
                        "suggestion": f"Define '{name}' before using it."
                    })

            # DANGEROUS EVAL
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "eval"
                ):
                    bugs.append({
                        "type": "Dangerous Function",
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                        "severity": "high",
                        "message": "eval() can execute unsafe code.",
                        "root_cause": (
                            "Dynamic code execution through eval()."
                        ),
                        "suggestion": (
                            "Avoid eval() and use safer alternatives."
                        )
                    })

        # ---------------------------------------------
        # REMOVE DUPLICATES
        # ---------------------------------------------

        unique_bugs = []
        seen = set()

        for bug in bugs:
            key = (
                bug["type"],
                bug["line"],
                bug["column"]
            )

            if key not in seen:
                seen.add(key)
                unique_bugs.append(bug)

        return {
            "total_bugs": len(unique_bugs),
            "bugs": unique_bugs
        }