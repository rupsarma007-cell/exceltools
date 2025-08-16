import os
import json
import pandas as pd
import numpy as np
import uuid
import logging
from flask import Blueprint, request, jsonify, render_template, session, current_app, send_file
from io import BytesIO
from werkzeug.utils import secure_filename

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

merge_excel_bp = Blueprint('merge_excel', __name__)

# Helper functions for data storage
def save_data(key, data):
    """Save data to a JSON file and store the filename in session."""
    try:
        storage_dir = current_app.config['DATA_STORAGE']
        os.makedirs(storage_dir, exist_ok=True)
        filename = f"{key}_{str(uuid.uuid4())}.json"
        filepath = os.path.join(storage_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, default=str)
        
        session[key] = filename
        return filepath
    except Exception as e:
        logger.error(f"Error saving data: {str(e)}")
        raise

def load_data(key):
    """Load data from a JSON file stored in the session."""
    try:
        if key not in session:
            return None
            
        storage_dir = current_app.config['DATA_STORAGE']
        filepath = os.path.join(storage_dir, session[key])
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        return None

def convert_to_serializable(obj):
    """Convert numpy/pandas types to Python native types."""
    if pd.isna(obj):
        return None
    if isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    if isinstance(obj, (np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    return obj

def prepare_data_for_json(df):
    """Prepare pandas DataFrame for JSON serialization."""
    try:
        if isinstance(df, pd.DataFrame):
            # Convert to records and handle serialization
            records = df.replace({np.nan: None}).to_dict(orient='records')
            serializable_data = []
            for row in records:
                new_row = {}
                for key, value in row.items():
                    new_row[key] = convert_to_serializable(value)
                serializable_data.append(new_row)
            return serializable_data
        return df
    except Exception as e:
        logger.error(f"Error preparing data for JSON: {str(e)}")
        return []

@merge_excel_bp.route('/', methods=['GET'])
def merge_home():
    """Render the merge Excel files page."""
    return render_template('merge_excel.html')

@merge_excel_bp.route('/merge', methods=['POST'])
def merge_files():
    """Handle merging of multiple Excel/CSV files."""
    try:
        # Clear previous session data
        session.pop('merged_data', None)
        
        if 'files' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        files = request.files.getlist('files')
        if len(files) == 0 or all(file.filename == '' for file in files):
            return jsonify({'error': 'No selected files'}), 400
        
        # Validate file types
        valid_files = []
        for file in files:
            if file.filename == '':
                continue
            if not (file.filename.endswith('.csv') or 
                    file.filename.endswith('.xlsx') or 
                    file.filename.endswith('.xls')):
                return jsonify({
                    'error': f'Invalid file type: {file.filename}. Only CSV and Excel files are allowed'
                }), 400
            valid_files.append(file)
        
        if len(valid_files) < 2:
            return jsonify({'error': 'Please select at least 2 files to merge'}), 400
        
        # Read and merge files
        dfs = []
        common_columns = None
        first_file_columns = None  # Store column order from first file
        filenames = []
        
        for file in valid_files:
            try:
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file, engine='openpyxl')
                
                filenames.append(file.filename)
                
                # Track common columns and store first file's order
                if common_columns is None:
                    common_columns = set(df.columns)
                    first_file_columns = df.columns.tolist()  # PRESERVE ORDER
                else:
                    common_columns = common_columns.intersection(set(df.columns))
                
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error reading file {file.filename}: {str(e)}")
                return jsonify({
                    'error': f'Error reading file {file.filename}: {str(e)}'
                }), 400
        
        # Create ordered list of common columns based on first file
        common_columns_ordered = [
            col for col in first_file_columns 
            if col in common_columns
        ]
        
        # Align columns using preserved order
        aligned_dfs = []
        for df in dfs:
            # Add missing columns with NaN
            for col in common_columns_ordered:
                if col not in df.columns:
                    df[col] = np.nan
            
            # Select only common columns in preserved order
            df = df[common_columns_ordered]
            aligned_dfs.append(df)
        
        # Merge with preserved column order
        merged_df = pd.concat(aligned_dfs, ignore_index=True)
        
        # Store merged data
        merged_data = {
            'filenames': filenames,
            'columns': common_columns_ordered,  # Use the ordered columns
            'merged_data': prepare_data_for_json(merged_df),
            'stats': {
                'files': len(filenames),
                'rows': len(merged_df),
                'columns': len(common_columns_ordered)
            }
        }
        
        save_data('merged_data', merged_data)
        
        # Prepare preview
        preview = merged_data['merged_data'][:20] if merged_data['merged_data'] else []
        
        return jsonify({
            'success': True,
            'filenames': filenames,
            'columns': common_columns_ordered,  # Send ordered columns to frontend
            'preview': preview,
            'stats': merged_data['stats']
        })
    except Exception as e:
        logger.exception("Error merging files")
        return jsonify({'error': f"Error merging files: {str(e)}"}), 500

@merge_excel_bp.route('/export', methods=['GET'])
def export_merged():
    """Export merged data to Excel."""
    try:
        merged_data = load_data('merged_data')
        if not merged_data:
            return jsonify({'error': 'No merged data available'}), 400
        
        # Create DataFrame with preserved column order
        df = pd.DataFrame(
            merged_data['merged_data'],
            columns=merged_data['columns']  # Maintain original order
        )
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Merged Data')
        
        output.seek(0)
        filename = "merged_data.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting merged data: {str(e)}")
        return jsonify({'error': f"Error exporting merged data: {str(e)}"}), 500