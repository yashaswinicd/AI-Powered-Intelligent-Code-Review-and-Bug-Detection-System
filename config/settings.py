import os

SECRET_KEY = 'your-secret-key-here'
DEBUG = True
HOST = '0.0.0.0'
PORT = 5000

UPLOAD_DIR = 'uploads/code_files'
ALLOWED_EXTENSIONS = {'py', 'java', 'cpp', 'c', 'js'}

MODEL_PATH = 'saved_models/code_review_model.pkl'
VECTORIZER_PATH = 'saved_models/vectorizer.pkl'

OUTPUT_FOLDER = 'outputs/reports'
REPORTS_DIR = 'outputs/reports'

SUPPORTED_LANGUAGES = {
    'py': 'Python',
    'java': 'Java',
    'cpp': 'C++',
    'c': 'C',
    'js': 'JavaScript'
}

BUG_THRESHOLD = 0.5
SEVERITY_LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
REPORTS_DIR = 'outputs/reports'