from src.multi_language_analyzer import MultiLanguageAnalyzer


def test_python_syntax_error_has_line_number():
    result = MultiLanguageAnalyzer().analyze("def broken(:\n    pass\n", "sample.py")
    assert result["language"] == "Python"
    assert result["success"] is False
    assert result["diagnostics"][0]["line"] == 1


def test_javascript_valid_syntax_when_node_available():
    analyzer = MultiLanguageAnalyzer()
    result = analyzer.analyze("const total = 2 + 3;\nconsole.log(total);\n", "sample.js")
    if result["available"]:
        assert result["language"] == "JavaScript"
        assert result["success"] is True


def test_javascript_syntax_error_reports_line_when_node_available():
    analyzer = MultiLanguageAnalyzer()
    result = analyzer.analyze("const total = ;\nconsole.log(total);\n", "sample.js")
    if result["available"]:
        assert result["success"] is False
        assert result["diagnostics"]
        assert result["diagnostics"][0]["line"] == 1


def test_c_syntax_error_reports_line_when_gcc_available():
    analyzer = MultiLanguageAnalyzer()
    result = analyzer.analyze("int main(void) {\n    int x = 1\n    return x;\n}\n", "sample.c")
    if result["available"]:
        assert result["language"] == "C"
        assert result["success"] is False
        assert result["diagnostics"]
        assert result["diagnostics"][0]["line"] == 3


def test_generic_filename_can_detect_javascript():
    result = MultiLanguageAnalyzer().analyze("const value = 1;\nconsole.log(value);", "code.py")
    assert result["language"] == "JavaScript"
