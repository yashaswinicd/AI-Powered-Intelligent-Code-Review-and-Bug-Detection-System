from src.bug_detector import BugDetector

code = """import os

def test():
    password = "admin123"
    x = 10 / 0
    print(x)
    y = unknown_variable
"""

result = BugDetector().detect(code)

print("TOTAL BUGS:", result["total_bugs"])
print()

for bug in result["bugs"]:
    print(
        bug["type"],
        "| Line:", bug["line"],
        "| Severity:", bug["severity"]
    )
