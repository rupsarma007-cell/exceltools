import os

# Flask settings
SECRET_KEY = 'your-secret-key-change-this'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)