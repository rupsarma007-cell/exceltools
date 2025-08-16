from flask import Blueprint, render_template, request, jsonify, send_file
import os
import tempfile
from werkzeug.utils import secure_filename
import pythoncom
import comtypes.client
import time
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

converter_bp = Blueprint('converter', __name__, template_folder='templates')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {
        'docx', 'doc', 'pdf', 'xlsx', 'csv', 'jpg', 'jpeg', 'png'
    }

def convert_word_to_pdf(input_path, output_path):
    try:
        pythoncom.CoInitialize()
        word = comtypes.client.CreateObject("Word.Application")
        word.Visible = False
        
        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        
        doc = word.Documents.Open(input_path)
        doc.SaveAs(output_path, FileFormat=17)  # 17 = PDF format
        doc.Close()
        word.Quit()
        
        if not os.path.exists(output_path):
            raise Exception("PDF file was not created")
        if os.path.getsize(output_path) == 0:
            raise Exception("Created PDF is empty")
            
        return True
    except Exception as e:
        logger.error(f"Word to PDF conversion failed: {str(e)}")
        raise
    finally:
        pythoncom.CoUninitialize()

@converter_bp.route('/')
def index():
    return render_template('converter.html')

@converter_bp.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(file_path)
        
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        conversion_options = []
        
        if file_ext in ['docx', 'doc']:
            conversion_options = ['pdf', 'txt']
        elif file_ext in ['xlsx']:
            conversion_options = ['csv']
        elif file_ext in ['csv']:
            conversion_options = ['xlsx']
        elif file_ext in ['jpg', 'jpeg', 'png']:
            conversion_options = ['jpg', 'png']
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'conversion_options': conversion_options,
            'temp_dir': temp_dir
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@converter_bp.route('/convert', methods=['POST'])
def convert():
    try:
        data = request.get_json()
        if not data or 'filename' not in data or 'output_format' not in data or 'temp_dir' not in data:
            return jsonify({'error': 'Invalid request data'}), 400
        
        input_path = os.path.join(data['temp_dir'], secure_filename(data['filename']))
        output_format = data['output_format']
        
        output_dir = tempfile.mkdtemp()
        output_filename = f"{os.path.splitext(data['filename'])[0]}.{output_format}"
        output_path = os.path.join(output_dir, output_filename)
        
        if output_format == 'pdf' and data['filename'].lower().endswith(('.docx', '.doc')):
            convert_word_to_pdf(input_path, output_path)
        else:
            # Add other conversion logic here
            raise Exception(f"Conversion to {output_format} not implemented")
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/pdf' if output_format == 'pdf' else 'application/octet-stream'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'temp_dir' in data and os.path.exists(data['temp_dir']):
            shutil.rmtree(data['temp_dir'], ignore_errors=True)
        if 'output_dir' in locals() and os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)