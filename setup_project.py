import os

folders = [
    "data/raw", "data/processed", "data/sample",
    "models", "notebooks", "src", "templates",
    "static/css", "static/js", "static/images",
    "uploads", "outputs/reports", "outputs/logs",
    "outputs/predictions", "tests/sample_codes",
    "docs", "screenshots", "assets/icons",
]

files = [
    "app.py", "train.py", "predict.py", "config.py",
    "requirements.txt", "README.md", ".gitignore", "LICENSE",
    "src/preprocessing.py", "src/feature_extraction.py",
    "src/code_parser.py", "src/bug_detector.py",
    "src/review_engine.py", "src/security_checker.py",
    "src/performance_analyzer.py", "src/report_generator.py",
    "src/utils.py", "templates/index.html", "templates/review.html",
    "templates/result.html", "templates/dashboard.html",
    "static/css/style.css", "static/js/script.js",
    "tests/test_bug_detector.py", "tests/test_preprocessing.py",
    "tests/test_model.py", "docs/api_documentation.md",
    "notebooks/01_data_exploration.ipynb",
    "notebooks/02_preprocessing.ipynb",
    "notebooks/03_model_training.ipynb",
    "models/model_metrics.json",
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)
    print(f"✅ Folder created: {folder}")

for file in files:
    with open(file, 'w') as f:
        pass
    print(f"📄 File created: {file}")

print("\n🎉 Project structure ready!")