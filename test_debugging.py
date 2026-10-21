from src.debugging_engine import DebuggingEngine

engine = DebuggingEngine()

tests = {
    "literal zero": "print(10 / 0)",
    "zero variable": "divisor = 0\nresult = 10 / divisor\nprint(result)",
    "normal code": "x = 10\nprint(x)",
}

for name, code in tests.items():
    result = engine.fix(code, [])

    print("\nTEST:", name)
    print("SYNTAX VALID:", result["syntax_valid"])
    print("TOTAL FIXES:", result["total_fixes"])
    print("REMAINING BUGS:", result["remaining_bugs"])
    print("VERIFIED:", result["verified"])
