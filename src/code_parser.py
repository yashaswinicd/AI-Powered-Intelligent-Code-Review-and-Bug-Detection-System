import ast
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import SUPPORTED_LANGUAGES

class CodeParser:
    def __init__(self):
        self.supported_languages = SUPPORTED_LANGUAGES

    # =============================
    # Detect Language
    # =============================
    def detect_language(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        return self.supported_languages.get(ext, "Unknown")

    # =============================
    # Read Code File
    # =============================
    def read_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            return code
        except Exception as e:
            return f"Error reading file: {str(e)}"

    # =============================
    # Parse Python Code (AST)
    # =============================
    def parse_python(self, code):
        try:
            tree = ast.parse(code)
            functions = []
            classes = []
            imports = []

            for node in ast.walk(tree):
                # Get all functions
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args]
                    })
                # Get all classes
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        'name': node.name,
                        'line': node.lineno
                    })
                # Get all imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)

            return {
                'status': 'success',
                'functions': functions,
                'classes': classes,
                'imports': imports,
                'total_lines': len(code.splitlines())
            }

        except SyntaxError as e:
            return {
                'status': 'syntax_error',
                'error': str(e),
                'line': e.lineno
            }

    # =============================
    # Get Code Statistics
    # =============================
    def get_code_stats(self, code):
        lines = code.splitlines()
        stats = {
            'total_lines': len(lines),
            'blank_lines': sum(1 for l in lines if l.strip() == ''),
            'comment_lines': sum(1 for l in lines if l.strip().startswith('#')),
            'code_lines': sum(1 for l in lines if l.strip() and not l.strip().startswith('#'))
        }
        return stats

    # =============================
    # Main Parse Function
    # =============================
    def parse(self, filepath):
        language = self.detect_language(filepath)
        code = self.read_file(filepath)
        stats = self.get_code_stats(code)