"""Labelled test programs used by the benchmark and the unit tests.

Every case is (name, language, source code, expected issue types).
An empty list means the program is correct and must produce no findings.
The programs are small on purpose: each one isolates a single situation.
"""

SYN = "Syntax Error"

CASES = [
    # ------------------------------------------------------------ Python
    ("py clean fizzbuzz", "python",
     'def fizzbuzz(n):\n    """Return the FizzBuzz word for n."""\n'
     '    if n % 15 == 0:\n        return "FizzBuzz"\n    if n % 3 == 0:\n'
     '        return "Fizz"\n    if n % 5 == 0:\n        return "Buzz"\n'
     '    return str(n)\n\nfor i in range(1, 16):\n    print(fizzbuzz(i))\n', []),
    ("py clean class", "python",
     'class Account:\n    """A bank account."""\n\n    def __init__(self, owner):\n'
     '        self.owner = owner\n        self.balance = 0\n\n'
     '    def deposit(self, amount):\n        """Add money."""\n'
     '        self.balance += amount\n        return self.balance\n\n'
     'acc = Account("Asha")\nprint(acc.deposit(50))\n', []),
    ("py clean comprehension scope", "python",
     'data = [1, 2, 3]\nsquares = [x * x for x in data]\n'
     'total = sum(v for v in squares if v > 1)\n'
     'if __name__ == "__main__":\n    result = total\n'
     '    for i in range(3):\n        last = i\n    print(result, last)\n', []),
    ("py clean lambda closure", "python",
     'def make_adder(n):\n    """Build an adder."""\n    def add(x):\n'
     '        return x + n\n    return add\n\nplus3 = make_adder(3)\n'
     'print(plus3(4))\nsquare = lambda q: q * q\nprint(square(5))\n', []),
    ("py clean exceptions", "python",
     'def read_number(text):\n    """Parse an int."""\n    try:\n'
     '        return int(text)\n    except ValueError as err:\n'
     '        print("bad number", err)\n        return None\n\n'
     'print(read_number("12"))\n', []),
    ("py clean sqlish log", "python",
     'count = 3\nprint(f"Update complete: {count} rows")\n'
     'print("Select an option from the menu")\n', []),
    ("py clean parameterised sql", "python",
     'import sqlite3\nconn = sqlite3.connect(":memory:")\ncur = conn.cursor()\n'
     'cur.execute("CREATE TABLE t (id INTEGER)")\n'
     'cur.execute("SELECT * FROM t WHERE id = ?", (1,))\n', []),
    ("py clean global fn import", "python",
     'import math\n\ncounter = 0\n\ndef bump():\n    """Increase the counter."""\n'
     '    global counter\n    counter += 1\n    return math.sqrt(counter)\n\n'
     'print(bump())\n', []),
    ("py missing colon", "python",
     'x = 3\nif x > 2\n    print("big")\n', [SYN]),
    ("py unclosed paren", "python",
     'values = [1, 2, 3]\nprint(sum(values)\nprint("done")\n', [SYN]),
    ("py unterminated string", "python",
     'name = "Asha\nprint(name)\n', [SYN]),
    ("py print statement", "python", 'print "hello"\n', [SYN]),
    ("py assignment in if", "python",
     'x = 4\nif x = 5:\n    print(x)\n', [SYN]),
    ("py missing indent", "python",
     'def f():\nprint(1)\n', [SYN]),
    ("py undefined variable", "python",
     'total = 5\nprint(totl)\n', ["Undefined Variable"]),
    ("py missing import", "python",
     'print(math.sqrt(16))\n', ["Undefined Variable"]),
    ("py division by zero", "python",
     'a = 10\nb = 0\nprint(a / b)\n', ["Division By Zero"]),
    ("py bare except", "python",
     'try:\n    x = int("5")\nexcept:\n    print("bad")\n', ["Bare Except"]),
    ("py empty except", "python",
     'try:\n    x = int("5")\nexcept ValueError:\n    pass\n',
     ["Empty Exception Handler"]),
    ("py hardcoded password", "python",
     'password = "admin123"\nprint(len(password))\n', ["Hardcoded Credential"]),
    ("py mutable default", "python",
     'def add(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n',
     ["Mutable Default Argument"]),
    ("py eval", "python", 'value = eval(input())\nprint(value)\n',
     ["Dangerous Function"]),
    ("py md5", "python",
     'import hashlib\nh = hashlib.md5(b"x").hexdigest()\nprint(h)\n',
     ["Weak Cryptography"]),
    ("py sql concat", "python",
     'user = input()\nquery = "SELECT * FROM users WHERE name = \'" + user + "\'"\n'
     'print(query)\n', ["SQL Injection Risk"]),
    ("py unreachable", "python",
     'def f():\n    return 1\n    print("never")\n', ["Unreachable Code"]),
    ("py multiple", "python",
     'password = "letmein"\nprint(y)\ntry:\n    pass\nexcept:\n    pass\n',
     ["Hardcoded Credential", "Undefined Variable", "Bare Except"]),

    # -------------------------------------------------------------- Java
    ("java clean hello", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        System.out.println("Hello");\n    }\n}\n', []),
    ("java clean control flow", "java",
     'public class Main {\n    static int sum(int n) {\n        int total = 0;\n'
     '        for (int i = 0; i < n; i++) {\n            total += i;\n        }\n'
     '        return total;\n    }\n\n    public static void main(String[] a) {\n'
     '        if (sum(3) > 2)\n            System.out.println("big");\n'
     '        else\n            System.out.println("small");\n    }\n}\n', []),
    ("java clean allman braces", "java",
     'public class Main\n{\n    public static void main(String[] args)\n    {\n'
     '        String s = "a";\n        if (s.equals("a"))\n        {\n'
     '            System.out.println(s);\n        }\n    }\n}\n', []),
    ("java clean try catch", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        try {\n            int x = Integer.parseInt("5");\n'
     '            System.out.println(x);\n        } catch (NumberFormatException e) {\n'
     '            System.out.println("bad");\n        }\n    }\n}\n', []),
    ("java missing semicolon", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        int x = 5\n        System.out.println(x);\n    }\n}\n', [SYN]),
    ("java missing brace", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        System.out.println("hi");\n    }\n', [SYN]),
    ("java unterminated string", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        System.out.println("hi);\n    }\n}\n', [SYN]),
    ("java hardcoded password", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        String password = "admin123";\n        System.out.println(password.length());\n'
     '    }\n}\n', ["Hardcoded Credential"]),
    ("java empty catch", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        try {\n            int x = Integer.parseInt("5");\n'
     '        } catch (Exception e) {\n        }\n    }\n}\n',
     ["Empty Exception Handler"]),
    ("java string ==", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        String s = args.length > 0 ? args[0] : "x";\n'
     '        if (s == "x") {\n            System.out.println("same");\n        }\n'
     '    }\n}\n', ["String Comparison With =="]),
    ("java division by zero", "java",
     'public class Main {\n    public static void main(String[] args) {\n'
     '        int a = 10;\n        int b = 0;\n        System.out.println(a / b);\n'
     '    }\n}\n', ["Division By Zero"]),
    ("java sql concat", "java",
     'public class Main {\n    static String q(String name) {\n'
     '        return "SELECT * FROM users WHERE name = \'" + name + "\'";\n'
     '    }\n}\n', ["SQL Injection Risk"]),

    # ----------------------------------------------------------------- C
    ("c clean hello", "c",
     '#include <stdio.h>\n\nint main(void) {\n    printf("Hello\\n");\n'
     '    return 0;\n}\n', []),
    ("c clean struct enum", "c",
     '#include <stdio.h>\n\nenum Color { RED, GREEN, BLUE };\n\n'
     'struct Point {\n    int x;\n    int y;\n};\n\nint a[] = {\n    1,\n    2\n};\n\n'
     'int main(void) {\n    struct Point p = {1, 2};\n    printf("%d %d\\n", p.x, a[1]);\n'
     '    return 0;\n}\n', []),
    ("c clean braces in strings", "c",
     '#include <stdio.h>\n\nint main(void) {\n    printf("{ ( [ // not a comment\\n");\n'
     '    char c = \'}\';\n    printf("%c\\n", c);\n    return 0;\n}\n', []),
    ("c clean macros switch", "c",
     '#include <stdio.h>\n#define MAX 10\n\nint main(void) {\n    int n = 2;\n'
     '    switch (n) {\n        case 1:\n            printf("one\\n");\n'
     '            break;\n        default:\n            printf("other %d\\n", MAX);\n'
     '    }\n    return 0;\n}\n', []),
    ("c missing semicolon", "c",
     '#include <stdio.h>\nint main(void) {\n    int x = 5\n    printf("%d", x);\n'
     '    return 0;\n}\n', [SYN]),
    ("c missing brace", "c",
     '#include <stdio.h>\nint main(void) {\n    printf("hi");\n    return 0;\n', [SYN]),
    ("c extra brace", "c",
     '#include <stdio.h>\nint main(void) {\n    printf("hi");\n    return 0;\n}\n}\n',
     [SYN]),
    ("c unterminated string", "c",
     '#include <stdio.h>\nint main(void) {\n    printf("hello);\n    return 0;\n}\n',
     [SYN]),
    ("c struct missing semicolon", "c",
     'struct P { int a; }\nint main(void) { return 0; }\n', [SYN]),
    ("c division by zero", "c",
     '#include <stdio.h>\nint main(void) {\n    int x = 5;\n    int y = 0;\n'
     '    printf("%d", x / y);\n    return 0;\n}\n', ["Division By Zero"]),
    ("c gets", "c",
     '#include <stdio.h>\nint main(void) {\n    char buf[10];\n    gets(buf);\n'
     '    return 0;\n}\n', ["Unsafe function gets()"]),
    ("c assignment in condition", "c",
     '#include <stdio.h>\nint main(void) {\n    int x = 3;\n    if (x = 5) {\n'
     '        printf("five\\n");\n    }\n    return 0;\n}\n',
     ["Assignment In Condition"]),
    ("c hardcoded password", "c",
     '#include <stdio.h>\nint main(void) {\n    const char *password = "admin123";\n'
     '    printf("%s", password);\n    return 0;\n}\n', ["Hardcoded Credential"]),

    # --------------------------------------------------------------- C++
    ("cpp clean hello", "cpp",
     '#include <iostream>\n#include <vector>\nusing namespace std;\n\n'
     'class Box {\npublic:\n    int w = 1;\n};\n\nint main() {\n'
     '    vector<int> v = {1, 2, 3};\n    Box b;\n    cout << v.size() + b.w << endl;\n'
     '    return 0;\n}\n', []),
    ("cpp clean lambda template", "cpp",
     '#include <iostream>\n\ntemplate <typename T>\nT twice(T x) {\n'
     '    return x * 2;\n}\n\nint main() {\n    auto f = [](int a) { return a + 1; };\n'
     '    std::cout << f(twice(2)) << std::endl;\n    return 0;\n}\n', []),
    ("cpp missing semicolon", "cpp",
     '#include <iostream>\nint main() {\n    int x = 5\n    std::cout << x;\n'
     '    return 0;\n}\n', [SYN]),
    ("cpp class missing semicolon", "cpp",
     '#include <iostream>\nclass A {\npublic:\n    int x;\n}\nint main() {\n'
     '    return 0;\n}\n', [SYN]),
    ("cpp unterminated string", "cpp",
     '#include <iostream>\nint main() {\n    std::cout << "hi;\n    return 0;\n}\n',
     [SYN]),

    # -------------------------------------------------------- JavaScript
    ("js clean functions", "javascript",
     'const items = [1, 2, 3];\nfunction total(list) {\n'
     '  return list.reduce((a, b) => a + b, 0);\n}\n'
     'const config = { name: "app", retries: 3 };\n'
     'console.log(total(items), config.name);\n', []),
    ("js clean regex template", "javascript",
     'const re = /[(]+\\d{2}/g;\nconst name = "Asha";\n'
     'console.log(`Hello ${name}`, re.test("(12"));\n'
     'const half = 10 / 2 / 5;\nconsole.log(half);\n', []),
    ("js clean async class", "javascript",
     'class Counter {\n  constructor() {\n    this.n = 0;\n  }\n  inc() {\n'
     '    this.n += 1;\n    return this.n;\n  }\n}\n'
     'async function run() {\n  const c = new Counter();\n  return c.inc();\n}\n'
     'run().then(console.log);\n', []),
    ("js clean null compare", "javascript",
     'function f(x) {\n  if (x == null) {\n    return 0;\n  }\n  return x;\n}\n'
     'console.log(f(null));\n', []),
    ("js missing brace", "javascript",
     'function f(a) {\n  if (a > 1) {\n    return 1;\n  \n  return 2;\n}\n'
     'console.log(f(2));\n', [SYN, "Unreachable Code"]),
    ("js unclosed paren", "javascript",
     'function f(a {\n  return a;\n}\nconsole.log(f(1));\n', [SYN]),
    ("js unterminated string", "javascript",
     'const s = "hello;\nconsole.log(s);\n', [SYN]),
    ("js hardcoded key", "javascript",
     'const apiKey = "abcd1234efgh";\nconsole.log(apiKey.length);\n',
     ["Hardcoded Credential"]),
    ("js empty catch", "javascript",
     'try {\n  JSON.parse("{");\n} catch (e) {\n}\n', ["Empty Exception Handler"]),
    ("js eval", "javascript", 'const r = eval("1 + 1");\nconsole.log(r);\n',
     ["Dangerous Function"]),
    ("js innerHTML", "javascript",
     'const el = document.getElementById("a");\nel.innerHTML = location.hash;\n',
     ["XSS Vulnerability"]),
]
