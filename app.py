from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
from werkzeug.utils import secure_filename

from config.settings import (
    SECRET_KEY, DEBUG, PORT, HOST,
    UPLOAD_DIR, ALLOWED_EXTENSIONS
)
from src.code_parser import CodeParser
from src.bug_detector import BugDetector
from src.review_engine import ReviewEngine
from src.security_checker import SecurityChecker
from src.report_generator import ReportGenerator

# =============================
# Flask App Initialize
# =============================
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialize all modules
parser = CodeParser()
detector = BugDetector()
engine = ReviewEngine()
security = SecurityChecker()
reporter = ReportGenerator()

# =============================
# Helper Function
# =============================
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =============================
# HOME PAGE
# =============================
@app.route('/')
def index():
    return render_template('index.html')

# =============================
# REVIEW PAGE
# =============================
@app.route('/review')
def review_page():
    return render_template('review.html')

# =============================
# DASHBOARD PAGE
# =============================
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# =============================
# ANALYZE CODE — Text Input
# =============================
@app.route('/analyze', methods=['POST'])
def analyze_code():
    try:
        data = request.get_json()
        code = data.get('code', '')
        filename = data.get('filename', 'code.py')

        if not code.strip():
            return jsonify({
                'success': False,
                'error': 'Code is empty!'
            })

        # Run Review
        review_result = engine.review(code, filename)

        # Run Security Check
        security_result = security.check(code)

        # Generate Report
        report = reporter.generate(review_result, security_result)

        return jsonify({
            'success': True,
            'filename': filename,
            'score': review_result['score'],
            'grade': review_result['grade'],
            'stats': review_result['stats'],
            'total_issues': review_result['total_issues'],
            'bugs': review_result['bugs'],
            'review_issues': review_result['review_issues'],
            'security': security_result,
            'all_issues': review_result['all_issues'],
            'text_report': report['text_report'],
            'ml_prediction': review_result.get('ml_prediction')
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# =============================
# ANALYZE CODE — File Upload
# =============================
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded!'
            })

        file = request.files['file']

        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected!'
            })

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_DIR, filename)
            file.save(filepath)

            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()

            review_result = engine.review(code, filename)
            security_result = security.check(code)
            report = reporter.generate(review_result, security_result)

            return jsonify({
                'success': True,
                'filename': filename,
                'score': review_result['score'],
                'grade': review_result['grade'],
                'stats': review_result['stats'],
                'total_issues': review_result['total_issues'],
                'bugs': review_result['bugs'],
                'security': security_result,
                'all_issues': review_result['all_issues'],
                'text_report': report['text_report'],
                'ml_prediction': review_result.get('ml_prediction')
            })
        else:
            return jsonify({
                'success': False,
                'error': 'File type not allowed!'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# =============================
# DOWNLOAD REPORT
# =============================
@app.route('/download/<filename>')
def download_report(filename):
    try:
        report_path = os.path.join('outputs', 'reports', filename)
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)})

# =============================
# API — Health Check
# =============================
@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'running',
        'message': 'AI Code Review System is Active!',
        'version': '1.0.0'
    })

# =============================
# Run App
# =============================
if __name__ == '__main__':
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    print("🚀 AI Code Review System Starting...")
    print(f"🌐 Open: http://localhost:{PORT}")
    app.run(debug=DEBUG, host=HOST, port=PORT)