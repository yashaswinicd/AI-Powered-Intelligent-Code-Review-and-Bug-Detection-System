from src.debugging_engine import DebuggingEngine

code = """if True
    print(1)"""

result = DebuggingEngine().fix(code)

print("FIXED CODE:")
print(result["fixed_code"])
print("SYNTAX VALID:", result["syntax_valid"])
print("TOTAL FIXES:", result["total_fixes"])
print("REMAINING BUGS:", result["remaining_bugs"])
print("VERIFIED:", result["verified"])
