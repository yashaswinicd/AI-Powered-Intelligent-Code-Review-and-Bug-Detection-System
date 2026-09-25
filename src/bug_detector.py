import ast


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

        # ---------------------------------------------
        # COLLECT VARIABLES
        # ---------------------------------------------

        defined_variables = set()

        builtin_names = {
            "print", "len", "range", "str", "int",
            "float", "list", "dict", "set", "tuple",
            "sum", "min", "max", "abs", "round",
            "input", "enumerate", "zip", "map", "filter",
            "True", "False", "None"
        }

        for node in ast.walk(tree):

            if isinstance(node, ast.Assign):

                for target in node.targets:

                    if isinstance(target, ast.Name):
                        defined_variables.add(target.id)

            elif isinstance(node, ast.AnnAssign):

                if isinstance(node.target, ast.Name):
                    defined_variables.add(node.target.id)

            elif isinstance(node, ast.AugAssign):

                if isinstance(node.target, ast.Name):
                    defined_variables.add(node.target.id)

            elif isinstance(node, ast.FunctionDef):

                defined_variables.add(node.name)

                for arg in node.args.args:
                    defined_variables.add(arg.arg)

            elif isinstance(node, ast.ClassDef):

                defined_variables.add(node.name)

            elif isinstance(node, ast.Import):

                for alias in node.names:
                    defined_variables.add(
                        alias.asname or alias.name.split(".")[0]
                    )

            elif isinstance(node, ast.ImportFrom):

                for alias in node.names:
                    defined_variables.add(
                        alias.asname or alias.name
                    )

        # ---------------------------------------------
        # ZERO VARIABLES
        # ---------------------------------------------

        zero_variables = set()

        for node in ast.walk(tree):

            if isinstance(node, ast.Assign):

                if (
                    isinstance(node.value, ast.Constant)
                    and node.value.value == 0
                ):

                    for target in node.targets:

                        if isinstance(target, ast.Name):
                            zero_variables.add(target.id)

            elif isinstance(node, ast.AnnAssign):

                if (
                    isinstance(node.value, ast.Constant)
                    and node.value.value == 0
                    and isinstance(node.target, ast.Name)
                ):

                    zero_variables.add(node.target.id)

        # ---------------------------------------------
        # SIMPLE LIST LENGTHS
        # ---------------------------------------------

        list_lengths = {}

        for node in ast.walk(tree):

            if isinstance(node, ast.Assign):

                if isinstance(node.value, ast.List):

                    length = len(node.value.elts)

                    for target in node.targets:

                        if isinstance(target, ast.Name):
                            list_lengths[target.id] = length

        # ---------------------------------------------
        # DETECT BUGS
        # ---------------------------------------------

        for node in ast.walk(tree):

            # -----------------------------------------
            # DIVISION BY ZERO
            # -----------------------------------------

            if isinstance(node, ast.BinOp):

                if isinstance(
                    node.op,
                    (
                        ast.Div,
                        ast.FloorDiv,
                        ast.Mod
                    )
                ):

                    literal_zero = (
                        isinstance(node.right, ast.Constant)
                        and node.right.value == 0
                    )

                    variable_zero = (
                        isinstance(node.right, ast.Name)
                        and node.right.id in zero_variables
                    )

                    if literal_zero or variable_zero:

                        if variable_zero:

                            divisor = node.right.id

                            message = (
                                f"Division by zero detected. "
                                f"Variable '{divisor}' has value 0."
                            )

                            root_cause = (
                                f"The divisor variable '{divisor}' "
                                f"is assigned the value 0."
                            )

                        else:

                            message = (
                                "Division by zero detected."
                            )

                            root_cause = (
                                "The divisor is zero."
                            )

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

            # -----------------------------------------
            # INDEX OUT OF RANGE
            # -----------------------------------------

            if isinstance(node, ast.Subscript):

                if isinstance(node.value, ast.Name):

                    variable = node.value.id

                    if variable in list_lengths:

                        index_value = None

                        if isinstance(
                            node.slice,
                            ast.Constant
                        ):

                            if isinstance(
                                node.slice.value,
                                int
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
                                        f"The index {index_value} is "
                                        f"outside the valid range."
                                    ),
                                    "suggestion": (
                                        "Use a valid list index or "
                                        "check the list length."
                                    )
                                })

            # -----------------------------------------
            # UNDEFINED VARIABLE
            # -----------------------------------------

            if isinstance(node, ast.Name):

                if isinstance(
                    node.ctx,
                    ast.Load
                ):

                    name = node.id

                    if (
                        name not in defined_variables
                        and name not in builtin_names
                    ):

                        # Ignore attribute names such as obj.value
                        parent_attribute = False

                        for parent in ast.walk(tree):

                            for child in ast.iter_child_nodes(parent):

                                if (
                                    child is node
                                    and isinstance(
                                        parent,
                                        ast.Attribute
                                    )
                                    and parent.value is node
                                ):

                                    parent_attribute = True
                                    break

                            if parent_attribute:
                                break

                        if not parent_attribute:

                            bugs.append({
                                "type": "Undefined Variable",
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "severity": "high",
                                "message": (
                                    f"Variable '{name}' "
                                    f"is used before being defined."
                                ),
                                "root_cause": (
                                    f"Variable '{name}' has no "
                                    f"known definition before use."
                                ),
                                "suggestion": (
                                    f"Define '{name}' before using it."
                                )
                            })

            # -----------------------------------------
            # DANGEROUS EVAL
            # -----------------------------------------

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
                        "message": (
                            "eval() can execute unsafe code."
                        ),
                        "root_cause": (
                            "Dynamic code execution through eval()."
                        ),
                        "suggestion": (
                            "Avoid eval() and use safer alternatives."
                        )
                    })

        # ---------------------------------------------
        # REMOVE DUPLICATE BUGS
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