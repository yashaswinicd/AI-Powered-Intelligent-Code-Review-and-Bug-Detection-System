# 🤖 AI-Powered Intelligent Code Review & Bug Detection System



![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)




![Flask](https://img.shields.io/badge/Flask-2.3.2-green.svg)




![ML](https://img.shields.io/badge/Machine-Learning-orange.svg)




![License](https://img.shields.io/badge/License-MIT-yellow.svg)




![Last Commit](https://img.shields.io/github/last-commit/yashaswinicd/AI-Powered-Code-Review-System)



> An AI-powered web application that automatically reviews code,
> detects bugs, checks security vulnerabilities and gives
> quality score with detailed suggestions.

---

## 🌟 Features

- 🐛 **Bug Detection** — Syntax errors, empty except blocks, hardcoded passwords
- 🔒 **Security Check** — SQL injection, XSS, weak cryptography, dangerous functions
- ⭐ **Code Quality** — Naming conventions, missing docstrings, code complexity
- 📊 **Quality Score** — 0-100 score with grade (A/B/C/D/F)
- 📄 **Report Generation** — Download TXT and JSON reports
- 🌐 **Web Interface** — Beautiful dark-themed Flask web app
- 📁 **File Upload** — Support for .py, .java, .cpp, .c, .js files

---

## 🖥️ Screenshots

### Home Page


![Home](docs/screenshots/home.png)



### Code Review Page


![Review](docs/screenshots/review.png)



### Dashboard


![Dashboard](docs/screenshots/dashboard.png)



---

## 🛠️ Tech Stack

| Technology | Purpose |
|-----------|---------|
| Python 3.8+ | Backend language |
| Flask | Web framework |
| Scikit-learn | Machine Learning |
| TF-IDF | Feature Extraction |
| HTML/CSS/JS | Frontend |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/yashaswinicd/AI-Powered-Code-Review-System.git
cd AI-Powered-Code-Review-System

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Train the model
python train.py
 
# Run the application
python app.py