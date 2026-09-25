import os

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".java", ".cpp",
    ".c", ".ts", ".jsx", ".tsx"
}

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_CODE_LINES = 10000


def validate_code(code, filename="code.py"):

    if not isinstance(code, str):
        raise ValueError("Code must be text.")

    if not code.strip():
        raise ValueError("Code cannot be empty.")

    lines = code.splitlines()

    if len(lines) > MAX_CODE_LINES:
        raise ValueError(
            f"Maximum {MAX_CODE_LINES} lines are allowed."
        )

    extension = os.path.splitext(filename)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    return True


def save_uploaded_file(file):

    if not file or not file.filename:
        raise ValueError("Invalid file.")

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    os.makedirs(
        "uploads/code_files",
        exist_ok=True
    )

    filename = os.path.basename(
        file.filename
    )

    path = os.path.join(
        "uploads/code_files",
        filename
    )

    file.save(path)

    if os.path.getsize(path) > MAX_FILE_SIZE:
        os.remove(path)
        raise ValueError(
            "File is too large. Maximum size is 5 MB."
        )

    return path


def read_uploaded_file(filepath):

    with open(
        filepath,
        "r",
        encoding="utf-8"
    ) as f:

        code = f.read()

    validate_code(
        code,
        os.path.basename(filepath)
    )

    return code


def get_file_info(filepath):

    return {
        "filename": os.path.basename(filepath),
        "size": os.path.getsize(filepath),
        "lines": len(
            read_uploaded_file(filepath).splitlines()
        )
    }


def delete_uploaded_file(filepath):

    if os.path.exists(filepath):
        os.remove(filepath)
        return True

    return False