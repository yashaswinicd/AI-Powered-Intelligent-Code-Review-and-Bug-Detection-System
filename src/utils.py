import os
import json
from datetime import datetime
from config import LOGS_DIR

def log_message(message, level="INFO"):
    os.makedirs(LOGS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    log_file = os.path.join(
        LOGS_DIR,
        f"app_{datetime.now().strftime('%Y%m%d')}.log"
    )
    with open(log_file, 'a') as f:
        f.write(log_entry + '\n')

def get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()

def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/(1024*1024):.1f} MB"

def load_json(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_json(data, filepath):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
    return True

def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

if __name__ == "__main__":
    log_message("Utils module loaded!", "INFO")
    print(f"✅ Timestamp: {get_timestamp()}")
    print(f"✅ File size: {format_file_size(2048)}")