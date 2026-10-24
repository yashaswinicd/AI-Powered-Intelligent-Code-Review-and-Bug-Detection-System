"""
Multi-language bug detector built on Tree-sitter.

Supports: Java, JavaScript, C, C++
Checks:   syntax errors, division by zero, hardcoded passwords, empty catch blocks

Needs: pip install tree-sitter tree-sitter-java tree-sitter-javascript
                   tree-sitter-c tree-sitter-cpp
Written for the tree-sitter 0.22+ Python API.

The result has the same shape as BugDetector.detect():
    {"total_bugs": int, "bugs": [ {type, line, column, severity,
                                   message, root_cause, suggestion}, ... ]}
"""

import importlib
import os
import re

try:
    from tree_sitter import Language, Parser
    TREE_SITTER_OK = True
except Exception:  # package missing or incompatible
    Language = Parser = None
    TREE_SITTER_OK = False


# extension -> (display name, python package that holds the grammar)
LANGUAGES = {
    ".java": ("Java", "tree_sitter_java"),
    ".js": ("JavaScript", "tree_sitter_javascript"),
    ".c": ("C", "tree_sitter_c"),
    ".h": ("C", "tree_sitter_c"),
    ".cpp": ("C++", "tree_sitter_cpp"),
    ".cc": ("C++", "tree_sitter_cpp"),
    ".cxx": ("C++", "tree_sitter_cpp"),
    ".hpp": ("C++", "tree_sitter_cpp"),
}

COMMENT_TYPES = {"comment", "line_comment", "block_comment"}
STRING_TYPES = {
    "string_literal", "string", "raw_string_literal", "concatenated_string",
}
DECLARATION_TYPES = {
    "variable_declarator", "init_declarator",
    "assignment_expression", "augmented_assignment_expression",
}
DIVISION_OPERATORS = {"/", "%", "/=", "%="}
ZERO_LITERAL = re.compile(r"^[+]?0+(\.0*)?[fFdDlLuU]*$")
SECRET_NAME = re.compile(
    r"(password|passwd|pwd|secret|api_?key|token)", re.IGNORECASE
)

DIVISION_CAUSE = {
    "Java": "Integer division by zero throws ArithmeticException at runtime.",
    "JavaScript": (
        "JavaScript does not crash on division by zero. It returns "
        "Infinity or NaN, which usually breaks the logic later."
    ),
    "C": "Division by zero is undefined behavior and usually crashes the program.",
    "C++": "Division by zero is undefined behavior and usually crashes the program.",
}


class LanguageAnalyzer:

    def __init__(self):
        self._parsers = {}
        self._warned = set()

    # ---------------------------------------------------------
    # PUBLIC HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def supports(filename):
        ext = os.path.splitext(filename or "")[1].lower()
        return ext in LANGUAGES

    def _get_parser(self, ext):
        name, package = LANGUAGES[ext]

        if package in self._parsers:
            return self._parsers[package]

        parser = None

        if TREE_SITTER_OK:
            try:
                module = importlib.import_module(package)
                language = Language(module.language())
                try:
                    parser = Parser(language)
                except TypeError:  # very old API
                    parser = Parser()
                    parser.set_language(language)
            except Exception as error:
                if package not in self._warned:
                    print(f"Tree-sitter grammar '{package}' not usable: {error}")
                    self._warned.add(package)

        self._parsers[package] = parser
        return parser

    # ---------------------------------------------------------
    # TREE UTILITIES
    # ---------------------------------------------------------

    @staticmethod
    def _walk(root):
        """Iterate over every node, left to right, without recursion."""
        stack = [root]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    @staticmethod
    def _text(source, node):
        return source[node.start_byte:node.end_byte].decode("utf-8", "replace")

    @staticmethod
    def _issue(kind, node, severity, message, cause, suggestion):
        row, column = node.start_point
        return {
            "type": kind,
            "line": row + 1,
            "column": column + 1,
            "severity": severity,
            "message": message,
            "root_cause": cause,
            "suggestion": suggestion,
        }

    # ---------------------------------------------------------
    # CHECKS
    # ---------------------------------------------------------

    def _syntax_errors(self, root, language):
        errors = []
        stack = [root]

        while stack and len(errors) < 5:
            node = stack.pop()
            if not node.has_error:
                continue
            if node.type == "ERROR" or node.is_missing:
                if node.is_missing:
                    message = f"Missing '{node.type}'."
                else:
                    message = "Unexpected code that does not match the grammar."
                errors.append(self._issue(
                    "Syntax Error", node, "critical", message,
                    f"Invalid {language} syntax.",
                    "Fix the syntax error at the reported line.",
                ))
                continue
            stack.extend(reversed(node.children))

        return errors

    def _division_by_zero(self, root, source, language):
        issues = []
        severity = "medium" if language == "JavaScript" else "high"

        for node in self._walk(root):
            if node.type not in (
                "binary_expression", "assignment_expression",
                "augmented_assignment_expression",
            ):
                continue

            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None:
                continue

            operator = source[left.end_byte:right.start_byte].decode(
                "utf-8", "replace"
            ).strip()

            if operator not in DIVISION_OPERATORS:
                continue

            if ZERO_LITERAL.match(self._text(source, right).strip()):
                issues.append(self._issue(
                    "Division By Zero", node, severity,
                    "Division or modulo by zero.",
                    DIVISION_CAUSE.get(language, "Division by zero."),
                    "Check that the divisor is not zero before dividing.",
                ))

        return issues

    def _hardcoded_passwords(self, root, source):
        issues = []

        for node in self._walk(root):
            if node.type not in DECLARATION_TYPES:
                continue

            name_node = (
                node.child_by_field_name("name")
                or node.child_by_field_name("declarator")
                or node.child_by_field_name("left")
            )
            value_node = (
                node.child_by_field_name("value")
                or node.child_by_field_name("right")
            )

            if name_node is None or value_node is None:
                continue
            if value_node.type not in STRING_TYPES:
                continue

            name = self._text(source, name_node)
            value = self._text(source, value_node).strip()

            if len(value) <= 2:  # empty string
                continue
            if not SECRET_NAME.search(name):
                continue

            issues.append(self._issue(
                "Hardcoded Password", node, "high",
                "A password, key or token is written directly in the code.",
                "Secrets in source code leak through version control.",
                "Read it from an environment variable or a config file "
                "that is not committed.",
            ))

        return issues

    def _empty_catch(self, root):
        issues = []

        for node in self._walk(root):
            if node.type != "catch_clause":
                continue

            body = node.child_by_field_name("body")
            if body is None:
                for child in node.children:
                    if child.type in (
                        "block", "statement_block", "compound_statement"
                    ):
                        body = child
                        break
            if body is None:
                continue

            has_statement = any(
                child.is_named and child.type not in COMMENT_TYPES
                for child in body.children
            )

            if not has_statement:
                issues.append(self._issue(
                    "Empty Except", node, "medium",
                    "Empty catch block silently ignores the error.",
                    "Swallowed errors hide real problems and make "
                    "debugging hard.",
                    "Log the error or handle it properly.",
                ))

        return issues

    # ---------------------------------------------------------
    # MAIN ENTRY
    # ---------------------------------------------------------

    def detect(self, code, filename):
        ext = os.path.splitext(filename or "")[1].lower()

        if ext not in LANGUAGES:
            return {"total_bugs": 0, "bugs": []}

        language = LANGUAGES[ext][0]
        parser = self._get_parser(ext)

        if parser is None:
            return {
                "total_bugs": 0,
                "bugs": [],
                "note": (
                    f"{language} analysis is unavailable. "
                    "Install the tree-sitter packages from requirements.txt."
                ),
            }

        if not isinstance(code, str):
            code = ""

        source = code.encode("utf-8")
        tree = parser.parse(source)
        root = tree.root_node

        # A broken tree gives unreliable results, so report syntax only.
        if root.has_error:
            bugs = self._syntax_errors(root, language)
        else:
            bugs = []
            bugs.extend(self._division_by_zero(root, source, language))
            bugs.extend(self._hardcoded_passwords(root, source))
            bugs.extend(self._empty_catch(root))

        seen = set()
        unique = []
        for bug in sorted(bugs, key=lambda b: (b["line"], b["column"])):
            key = (bug["type"], bug["line"], bug["column"])
            if key not in seen:
                seen.add(key)
                unique.append(bug)

        return {"total_bugs": len(unique), "bugs": unique}


# ---------------------------------------------------------
# QUICK SELF TEST:  python -m src.language_analyzer
# ---------------------------------------------------------

SAMPLES = {
    "Main.java": """public class Main {
    public static void main(String[] args) {
        int x = 10 / 0;
        String password = "admin123";
        try {
            System.out.println(x);
        } catch (Exception e) {
        }
    }
}
""",
    "app.js": """const apiKey = "abc123";
let total = 5 / 0;
try {
  run();
} catch (err) {
}
""",
    "main.c": """#include <stdio.h>
int main() {
    char *password = "root";
    int y = 8 / 0;
    printf("%d", y);
    return 0;
}
""",
    "main.cpp": """#include <iostream>
int main() {
    int z = 4 % 0;
    try {
        std::cout << z;
    } catch (...) {
    }
    return 0;
}
""",
    "broken.java": """public class Broken {
    public static void main(String[] args) {
        int x = ;
    }
}
""",
}

if __name__ == "__main__":
    analyzer = LanguageAnalyzer()

    for name, sample in SAMPLES.items():
        result = analyzer.detect(sample, name)
        print(f"\n== {name}: {result['total_bugs']} issue(s)")
        if result.get("note"):
            print("  note:", result["note"])
        for bug in result["bugs"]:
            print(f"  line {bug['line']}: {bug['type']} [{bug['severity']}]")