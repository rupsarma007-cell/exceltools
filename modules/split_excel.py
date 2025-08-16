from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
import pandas as pd
from io import BytesIO
import zipfile
from werkzeug.utils import secure_filename
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

split_excel_bp = Blueprint('split_excel_bp', __name__, template_folder='../templates')

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls', 'csv'}

def clean_filename(value):
    """Clean values to create safe filenames"""
    if pd.isna(value):
        return "NA"
    return str(value).replace('/', '_').replace('\\', '_').replace(':', '_')

@split_excel_bp.route('/', methods=['GET', 'POST'])
def split_excel():
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            logger.warning('No file uploaded in request')
            return redirect(request.url)
        
        file = request.files['file']
        primary_column = request.form.get('primary_column')
        secondary_column = request.form.get('secondary_column') or None
        
        # Validate file presence
        if file.filename == '':
            flash('No file selected', 'error')
            logger.warning('Empty filename in request')
            return redirect(request.url)
        
        # Validate primary column selection
        if not primary_column:
            flash('Please select a primary column to split by', 'error')
            logger.warning('No primary column selected for splitting')
            return redirect(request.url)
        
        # Check file extension
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload Excel (XLSX, XLS) or CSV file.', 'error')
            logger.warning(f'Invalid file type uploaded: {file.filename}')
            return redirect(request.url)
        
        try:
            logger.info(f'Processing file: {file.filename}, splitting by primary: {primary_column}, secondary: {secondary_column}')
            
            # Read the Excel file
            if file.filename.lower().endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Validate columns exist
            if primary_column not in df.columns:
                flash(f'Primary column "{primary_column}" not found in the file', 'error')
                logger.warning(f'Primary column not found: {primary_column}')
                return redirect(request.url)
            
            if secondary_column and secondary_column not in df.columns:
                flash(f'Secondary column "{secondary_column}" not found in the file', 'error')
                logger.warning(f'Secondary column not found: {secondary_column}')
                return redirect(request.url)
            
            # Group data based on column selections
            if secondary_column:
                grouped = df.groupby([primary_column, secondary_column])
            else:
                grouped = df.groupby(primary_column)
            
            # Create in-memory zip file
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                for group, data in grouped:
                    if secondary_column:
                        primary_value, secondary_value = group
                        filename = f"{clean_filename(primary_value)}_{clean_filename(secondary_value)}.xlsx"
                    else:
                        primary_value = group
                        filename = f"{clean_filename(primary_value)}.xlsx"
                    
                    # Create Excel file in memory
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        data.to_excel(writer, index=False, sheet_name='Data')
                    
                    # Add to zip
                    zip_file.writestr(filename, output.getvalue())
            
            zip_buffer.seek(0)
            logger.info(f'Successfully split file into {len(grouped)} parts')
            
            # Send the zip file
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name='split_files.zip'
            )
            
        except Exception as e:
            error_msg = f'Error processing file: {str(e)}'
            flash(error_msg, 'error')
            logger.error(error_msg, exc_info=True)
            return redirect(request.url)
    
    return render_template('split_excel.html')