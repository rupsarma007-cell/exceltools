from flask import Flask, render_template
import os
from werkzeug.utils import secure_filename

# Create application instance
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DATA_STORAGE'] = 'data_storage'
app.config['ALLOWED_EXTENSIONS'] = {'docx', 'doc', 'pdf', 'xlsx', 'csv', 'jpg', 'jpeg', 'png'}

# Create required directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DATA_STORAGE'], exist_ok=True)

# Import and register all blueprints
from modules.data_analysis import data_analysis_bp
from modules.merge_excel import merge_excel_bp
from modules.compare_files import compare_files_bp
from modules.converter import converter_bp
from modules.split_excel import split_excel_bp  # Add this line

app.register_blueprint(data_analysis_bp, url_prefix='/data')
app.register_blueprint(merge_excel_bp, url_prefix='/merge')
app.register_blueprint(compare_files_bp, url_prefix='/compare')
app.register_blueprint(converter_bp, url_prefix='/converter')
app.register_blueprint(split_excel_bp, url_prefix='/split')  # Add this line

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)