🤖 AI-Powered Intelligent Code Review & Bug Detection System

Detect · Explain · Fix · Execute · Verify

An intelligent code review and debugging web application built with Python and Flask. It analyzes source code, identifies supported bugs and potential security issues, applies selected automatic fixes, executes code, and reports verification results.

"Python" (https://img.shields.io/badge/Python-3.10%2B-blue)
"Flask" (https://img.shields.io/badge/Flask-Web%20Framework-green)
"GitHub" (https://img.shields.io/badge/Version%20Control-GitHub-black)
"Status" (https://img.shields.io/badge/Project-Educational-orange)

---

🎬 Project Demo

"AI Code Review and Debugging Demo" (screenshots/demo.gif)

---

✨ Features

- Bug Detection: Detect supported issues such as syntax errors, division by zero, and undefined variables.
- Code Review: Analyze code and report potential quality issues.
- Security Analysis: Identify supported security risk patterns.
- Automatic Fixes: Apply selected corrections when a safe fix is available.
- Code Execution: Run submitted code and report output or runtime errors.
- Fix Verification: Re-analyze corrected code and report whether detected issues remain.
- File Upload: Upload source files through the web interface.
- Code Quality Report: Display a quality score and detected issue summaries.
- Web Interface: View code analysis, corrections, execution results, and verification status.

«Detection and automatic-fix capabilities depend on the implemented rules. The application does not guarantee that every bug or security vulnerability will be detected or corrected.»

---

🖥️ Screenshots

1. Home Page

"Project Home Page" (screenshots/home.png)

2. Code Review and Debugging Results

"Code Review Results" (screenshots/review.png)

3. Dashboard

"Project Dashboard" (screenshots/dashboard.png)

---

🛠️ Technology Stack

Technology| Purpose
Python| Backend development
Flask| Web application framework
Python AST| Python syntax and structural analysis
HTML| Page structure
CSS| Interface styling
JavaScript| Frontend interactions
Git and GitHub| Version control and repository hosting
Scikit-learn / TF-IDF| Machine-learning components, where configured

---

📁 Project Structure

AI-Powered Intelligent Code Review and Bug Detection System/
│
├── app.py
├── requirements.txt
├── README.md
│
├── src/
│   ├── bug_detector.py
│   ├── code_parser.py
│   ├── debugging_engine.py
│   ├── review_engine.py
│   ├── security_checker.py
│   ├── execution_engine.py
│   └── verification_engine.py
│
├── templates/
├── utils/
├── tests/
├── docs/
└── screenshots/
    ├── home.png
    ├── review.png
    ├── dashboard.png
    └── demo.gif

This structure illustrates the main project components. Actual files and folders may vary with the current repository version.

---

🚀 Getting Started

Prerequisites

Install the following:

- Python 3.10 or a compatible version
- pip
- Git

Step 1: Clone the Repository

git clone https://github.com/yashaswinicd/AI-Powered-Intelligent-Code-Review-and-Bug-Detection-System.git

Step 2: Open the Project Folder

cd AI-Powered-Intelligent-Code-Review-and-Bug-Detection-System

Step 3: Create a Virtual Environment

python -m venv venv

Step 4: Activate the Environment

Windows PowerShell:

.\venv\Scripts\Activate.ps1

If PowerShell prevents activation, you can use the virtual environment's Python executable directly.

Step 5: Install Dependencies

python -m pip install -r requirements.txt

Step 6: Run the Application

python app.py

Open the following address in your browser:

http://127.0.0.1:5000

The application may open the browser automatically when the server starts.

---

🧪 Example: Automatic Syntax Fix

Input Code

if True
    print("Hello World")

Corrected Code

if True:
    print("Hello World")

The application can detect the missing colon, apply the supported correction, execute the corrected code, and report verification status.

Actual results depend on the implemented debugging rules.

---

🧪 Testing

The project can be tested using cases such as:

- Valid Python programs
- Syntax errors, such as missing colons
- Division by zero
- Undefined variables
- Potential security risks
- Large source files, including 10,000-line inputs

Test results should be recorded separately. The presence of a test file alone does not mean that the test has passed.

---

🔐 Security Considerations

Warning: Executing untrusted source code can be dangerous.

Before using this application with untrusted code or deploying it publicly, implement a properly isolated execution environment with restricted permissions, resource limits, and appropriate timeouts.

Do not rely on static analysis alone to guarantee that code is secure.

---

⚠️ Current Limitations

- Static analysis only detects implemented patterns.
- Automatic fixes are limited to supported corrections.
- Successful execution does not guarantee bug-free code.
- Verification covers only the checks implemented by the application.
- Large-file performance and multi-language support require separate testing.

---

🔮 Future Enhancements

- Expanded bug detection and language support
- More comprehensive automated tests
- Secure sandboxed code execution
- Improved debugging explanations
- Detailed reports and analysis history
- Continuous integration and deployment

---

👩‍💻 Author

Yashaswini C D

GitHub: "@yashaswinicd" (https://github.com/yashaswinicd)

Project Repository: "AI-Powered Intelligent Code Review and Bug Detection System" (https://github.com/yashaswinicd/AI-Powered-Intelligent-Code-Review-and-Bug-Detection-System)

---

📄 License

Check the repository's existing license before redistributing this project. If you intend to publish it under the MIT License, include a valid "LICENSE" file in the repository.