AI-Powered Intelligent Code Review & Bug Detection System

Detect · Explain · Fix · Execute · Verify

A Python-based web application for analyzing source code, identifying potential bugs and security issues, applying supported automatic fixes, executing code, and verifying the results.

Features

- Bug Detection — Detect supported issues such as division by zero, undefined variables, and syntax errors.
- Code Review — Analyze source code and report potential code quality issues.
- Security Analysis — Check for supported security risk patterns.
- Automatic Fixes — Apply selected fixes when a safe correction can be determined.
- Code Execution — Execute submitted code and report output or runtime errors.
- Fix Verification — Re-analyze corrected code and report whether detected issues remain.
- File Upload — Upload source files for analysis.
- Web Interface — Review detected issues, code quality information, execution results, and corrected code.

«Detection and automatic-fix capabilities depend on the implemented rules and supported programming languages. The tool does not guarantee detection or correction of every bug.»

Tech Stack

Technology| Purpose
Python| Backend logic and analysis
Flask| Web application and API routes
Python AST| Python syntax and structural analysis
HTML, CSS, JavaScript| User interface
Scikit-learn / TF-IDF| Machine-learning components, where configured
Git and GitHub| Version control and source hosting

Project Structure

AI-Powered Intelligent Code Review and Bug Detection System/
├── app.py
├── src/
│   ├── bug_detector.py
│   ├── code_parser.py
│   ├── debugging_engine.py
│   ├── review_engine.py
│   ├── security_checker.py
│   ├── execution_engine.py
│   └── verification_engine.py
├── templates/
├── utils/
├── tests/
├── requirements.txt
└── README.md

Some files or directories may differ depending on the current project version.

Getting Started

Prerequisites

- Python 3.10 or a compatible supported version
- pip
- Git

1. Clone the repository

git clone https://github.com/yashaswinicd/AI-Powered-Intelligent-Code-Review-and-Bug-Detection-System.git

2. Open the project directory

cd AI-Powered-Intelligent-Code-Review-and-Bug-Detection-System

3. Create a virtual environment

python -m venv venv

4. Activate the environment

Windows PowerShell:

.\venv\Scripts\Activate.ps1

If PowerShell blocks activation, use:

.\venv\Scripts\python.exe -m pip install -r requirements.txt

5. Install dependencies

python -m pip install -r requirements.txt

6. Run the application

python app.py

Open the local website at:

http://127.0.0.1:5000

The application may open your default browser automatically when the server starts.

Example

Input

if True
    print("Hello World")

Expected correction

if True:
    print("Hello World")

The application can report the syntax error, apply the supported correction, execute the corrected code, and indicate whether verification succeeds.

Actual results depend on the implemented analyzer and execution environment.

Testing

Test the application with cases such as:

- Valid Python code
- Missing-colon syntax errors
- Division by zero
- Undefined variables
- Code with potential security risks
- Large source files, including 10,000-line inputs

Record the actual results of each test before claiming that all tests pass.

Security Notice

Do not run untrusted source code on a personal computer or production server without proper isolation. Running arbitrary code can cause data loss, unauthorized file access, or other security problems. Use a restricted sandbox with appropriate resource and permission limits before deploying this application for public use.

Current Limitations

- Static analysis detects only patterns implemented by the analyzer.
- Automatic fixes are limited to supported corrections.
- A successful execution does not necessarily mean the code is bug-free.
- Verification reports only the checks performed by the application.
- Large-file performance and language-specific support should be tested separately.

Future Improvements

- Broader static analysis and language support
- More comprehensive automated tests
- Safer isolated code execution
- Improved debugging explanations
- Detailed test reports and analysis history
- Continuous integration and deployment

Author

Yashaswini C D

GitHub: "@yashaswinicd" (https://github.com/yashaswinicd)

License

This project is intended for educational and development purposes. Add a "LICENSE" file to the repository if you intend to distribute the project under a specific open-source license.