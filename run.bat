@echo off
echo Starting AI Code Review System...
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python app.py
pause
