"""Unit tests. Run with:  python -m unittest discover -s tests -t .
(pytest also works if you have it installed)."""

import io
import unittest

from app import app
from src.execution_engine import ExecutionEngine
from src.language_support import detect_language
from src.lexer import scan
from src.pipeline import process_code
from src.universal_fixer import analyze, fix
from tests.benchmark_cases import CASES
from tests.run_benchmark import run as run_benchmark


def types(result):
    return {i["type"] for i in result["original_issues"]}


class LanguageDetectionTests(unittest.TestCase):
    def test_extension_wins(self):
        self.assertEqual(detect_language("x", "Main.java")[0], "java")

    def test_content_detection(self):
        samples = {
            "python": "def f(x):\n    return x\n",
            "java": "public class A { System.out.println(1); }",
            "cpp": "#include <iostream>\nint main(){ std::cout << 1; }",
            "c": "#include <stdio.h>\nint main(){ printf(\"x\"); }",
            "go": "package main\nfunc main() { fmt.Println(1) }",
            "rust": "fn main() { let mut x = 1; println!(\"{}\", x); }",
        }
        for expected, code in samples.items():
            self.assertEqual(detect_language(code)[0], expected, expected)

    def test_user_choice_overrides(self):
        self.assertEqual(detect_language("x", "a.py", "c")[0], "c")


class LexerTests(unittest.TestCase):
    def test_strings_and_comments_are_masked(self):
        sc = scan('int a; /* { */ char *s = "}("; // )\n', "c")
        self.assertNotIn("{", sc.code_only)
        self.assertNotIn("(", sc.code_only.replace("(", "", 0)[20:])
        self.assertEqual(len(sc.code_only), len(sc.code))

    def test_unterminated_string_reports_line(self):
        sc = scan('a = 1\nb = "oops\nc = 3\n', "python")
        self.assertEqual(sc.errors[0]["line"], 2)

    def test_js_regex_is_not_a_bracket(self):
        sc = scan("const r = /[(]+/g;\n", "javascript")
        self.assertNotIn("(", sc.code_only)


class PythonAnalysisTests(unittest.TestCase):
    def test_no_false_positive_on_scopes(self):
        code = ("data = [1, 2]\nsq = [x * x for x in data]\n"
                "if __name__ == '__main__':\n    r = sum(sq)\n"
                "    for i in range(2):\n        last = i\n    print(r, last)\n"
                "def f(a):\n    import math\n    g = lambda q: q + a\n"
                "    try:\n        return math.sqrt(g(1))\n"
                "    except ValueError as err:\n        print(err)\n")
        result = analyze(code, "python")
        self.assertEqual([i for i in result["issues"]], [])

    def test_typo_is_corrected(self):
        out = fix("count = 5\nprint(cuont)\n", "python")
        self.assertIn("print(count)", out["fixed_code"])

    def test_missing_import_is_added(self):
        out = fix("print(math.sqrt(16))\n", "python")
        self.assertIn("import math", out["fixed_code"])

    def test_syntax_repairs(self):
        cases = {
            "if True\n    print(1)\n": "if True:",
            'print "hi"\n': 'print("hi")',
            "x = 1\nif x = 1:\n    pass\n": "if x == 1:",
            'print("a"\n': 'print("a")',
        }
        for broken, expected in cases.items():
            out = fix(broken, "python")["fixed_code"]
            compile(out, "<test>", "exec")
            self.assertIn(expected, out)

    def test_division_guard_runs(self):
        result = process_code("a = 10\nb = 0\nprint(a / b)\n", store=False)
        self.assertTrue(result["execution"]["success"])
        self.assertEqual(result["execution"]["output"].strip(), "0")

    def test_secret_moved_to_environment(self):
        out = fix('password = "abc12345"\n', "python")["fixed_code"]
        self.assertIn('os.environ.get("PASSWORD"', out)
        self.assertIn("import os", out)


class OtherLanguageTests(unittest.TestCase):
    def test_c_semicolons_fixed(self):
        code = '#include <stdio.h>\nint main(void) {\n    int x = 5\n    printf("%d", x)\n    return 0;\n}\n'
        out = fix(code, "c", use_compilers=False)["fixed_code"]
        self.assertIn("int x = 5;", out)
        self.assertIn('printf("%d", x);', out)

    def test_java_missing_brace_appended(self):
        code = "public class A {\n    void f() {\n        int x = 1;\n    }\n"
        out = fix(code, "java", use_compilers=False)["fixed_code"]
        self.assertTrue(out.rstrip().endswith("}"))
        self.assertEqual(out.count("{"), out.count("}"))

    def test_java_string_compare(self):
        code = 'class A { boolean f(String s) { return s == "x"; } }'
        out = fix(code, "java", use_compilers=False)["fixed_code"]
        self.assertIn('"x".equals(s)', out)

    def test_issue_lines_are_correct(self):
        code = "int main() {\n    int a = 1;\n    int b = 2\n    return 0;\n}\n"
        result = analyze(code, "c", use_compilers=False)
        lines = [i["line"] for i in result["issues"] if i["category"] == "syntax"]
        self.assertEqual(lines, [3])

    def test_clean_code_has_no_syntax_findings(self):
        for name, lang, code, expected in CASES:
            if expected:
                continue
            result = analyze(code, lang, use_compilers=False)
            syntax = [i for i in result["issues"] if i["category"] == "syntax"]
            self.assertEqual(syntax, [], name)


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionEngine(timeout=3)

    def test_normal_code_runs(self):
        out = self.engine.run('print(input().upper())', "abc")
        self.assertEqual(out["output"].strip(), "ABC")

    def test_runtime_error_has_line(self):
        out = self.engine.run("x = 1\nprint(1 / 0)\n")
        self.assertEqual(out["error_type"], "ZeroDivisionError")
        self.assertEqual(out["error_line"], 2)

    def test_dangerous_code_is_blocked(self):
        for code in ("import subprocess", "import os\nos.system('ls')",
                     "open('/tmp/x', 'w')", "exec('1')",
                     "getattr(__builtins__, 'x')"):
            self.assertEqual(self.engine.run(code)["error_type"],
                             "BlockedByPolicy", code)

    def test_infinite_loop_times_out(self):
        self.assertEqual(self.engine.run("while True: pass")["error_type"],
                         "TimeoutError")


class BenchmarkTests(unittest.TestCase):
    def test_quality_thresholds(self):
        report, failures = run_benchmark(verbose=False)
        self.assertEqual(report["false_positive_files"], 0, failures)
        self.assertGreaterEqual(report["precision"], 0.95, failures)
        self.assertGreaterEqual(report["recall"], 0.95, failures)
        self.assertGreaterEqual(report["fix_success_rate"], 0.95, failures)


class WebAppTests(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile
        from utils import stats_store
        # keep test runs out of the real dashboard statistics
        self._tmp = tempfile.mkdtemp()
        self._old_path = stats_store.STATS_PATH
        stats_store.STATS_PATH = os.path.join(self._tmp, "stats.json")
        self.client = app.test_client()

    def tearDown(self):
        from utils import stats_store
        stats_store.STATS_PATH = self._old_path

    def test_pages_load(self):
        for path in ("/", "/review", "/dashboard", "/api/health",
                     "/api/languages", "/api/stats", "/api/benchmark"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_debug_endpoint(self):
        response = self.client.post("/debug", json={
            "code": 'int main() {\n    int x = 1\n    return x;\n}\n',
            "language": "c"})
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("int x = 1;", data["fixed_code"])
        report = self.client.get(f"/report/{data['result_id']}/json")
        self.assertEqual(report.status_code, 200)

    def test_empty_code_rejected(self):
        response = self.client.post("/debug", json={"code": "   "})
        self.assertEqual(response.status_code, 400)

    def test_upload(self):
        response = self.client.post(
            "/upload-debug",
            data={"file": (io.BytesIO(b"int main() { int a = 1 }"), "a.c")},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)

    def test_bad_extension_rejected(self):
        response = self.client.post(
            "/upload-debug",
            data={"file": (io.BytesIO(b"x"), "a.exe")},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
