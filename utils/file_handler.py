"""
file_handler.py
Handles file upload, validation, reading, and cleanup
for the AI-Powered Code Review and Bug Detection System.
"""

import os
import uuid
from werkzeug.utils import secure_filename

# Allowed code file extensions
ALLOWED_EXTENSIONS = {'py', 'js', 'java', 'cpp', 'c', 'ts', 'jsx', 'tsx'}

# Max file size: 5 MB
MAX_FILE_SIZE = 5 * 1024 * 1024

UPLOAD_FOLDER = os.path.join('uploads', 'code_files')


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_valid_size(file):
    """Check file size is within limit. Resets stream position after check."""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= MAX_FILE_SIZE


def save_uploaded_file(file, upload_folder=UPLOAD_FOLDER):
    """
    Validates and saves an uploaded file to disk with a unique name.
    Returns (success, filepath_or_error_message).
    """
    if file is None or file.filename == '':
        return False, "No file selected."

    if not allowed_file(file.filename):
        return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"

    if not is_valid_size(file):
        return False, "File too large. Max size is 5MB."

    os.makedirs(upload_folder, exist_ok=True)

    original_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    filepath = os.path.join(upload_folder, unique_name)

    try:
        file.save(filepath)
        return True, filepath
    except Exception as e:
        return False, f"Error saving file: {str(e)}"


def read_code_file(filepath):
    """Reads and returns the content of a code file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return True, f.read()
    except FileNotFoundError:
        return False, "File not found."
    except Exception as e:
        return False, f"Error reading file: {str(e)}"


def delete_file(filepath):
    """Deletes a file from disk if it exists."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True, "File deleted."
        return False, "File does not exist."
    except Exception as e:
        return False, f"Error deleting file: {str(e)}"


def get_file_extension(filename):
    """Returns the extension of a given filename (lowercase, no dot)."""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ""