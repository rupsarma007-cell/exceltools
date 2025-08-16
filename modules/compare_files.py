# modules/compare_files.py
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

compare_files_bp = Blueprint('compare_files', __name__)

def nan_to_none(obj):
    """Convert numpy.nan to None for JSON serialization"""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj

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

@compare_files_bp.route('/', methods=['GET'])
def compare_home():
    """Render the compare files page."""
    return render_template('compare_files.html')

@compare_files_bp.route('/get_columns', methods=['POST'])
def get_columns():
    """Get columns from a file for the comparison tool."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        # Save the file temporarily to read it
        temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_path)
        
        # Read file based on extension
        if file.filename.lower().endswith('.csv'):
            df = pd.read_csv(temp_path)
        elif file.filename.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(temp_path, engine='openpyxl')
        elif file.filename.lower().endswith(('.htm', '.html')):
            dfs = pd.read_html(temp_path)
            df = dfs[0] if dfs else pd.DataFrame()
        elif file.filename.lower().endswith('.xml'):
            df = pd.read_xml(temp_path)
        else:
            os.remove(temp_path)
            return jsonify({'error': 'Unsupported file type'}), 400
        
        # Clean up the temporary file
        os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'columns': df.columns.tolist()
        })
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f"Error reading file: {str(e)}"}), 500

@compare_files_bp.route('/compare', methods=['POST'])
def compare_files():
    """Handle file comparison."""
    try:
        # Clear previous session data
        session.pop('comparison_results', None)
        
        # Check files
        if 'file1' not in request.files or 'file2' not in request.files:
            return jsonify({'error': 'Both files are required'}), 400
        
        file1 = request.files['file1']
        file2 = request.files['file2']
        col1 = request.form.get('column1')
        col2 = request.form.get('column2')
        
        if file1.filename == '' or file2.filename == '':
            return jsonify({'error': 'Both files must be selected'}), 400
        
        if not col1 or not col2:
            return jsonify({'error': 'Please select a column for each file'}), 400
        
        # Save files temporarily
        file1_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file1.filename))
        file2_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file2.filename))
        file1.save(file1_path)
        file2.save(file2_path)
        
        # Read files
        def read_file(file_path):
            try:
                if file_path.lower().endswith('.csv'):
                    return pd.read_csv(file_path)
                elif file_path.lower().endswith(('.xlsx', '.xls')):
                    return pd.read_excel(file_path, engine='openpyxl')
                elif file_path.lower().endswith(('.htm', '.html')):
                    dfs = pd.read_html(file_path)
                    return dfs[0] if dfs else pd.DataFrame()
                elif file_path.lower().endswith('.xml'):
                    return pd.read_xml(file_path)
                else:
                    return None
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {str(e)}")
                return None
        
        df1 = read_file(file1_path)
        df2 = read_file(file2_path)
        
        # Clean up temporary files
        os.remove(file1_path)
        os.remove(file2_path)
        
        if df1 is None or df2 is None:
            return jsonify({'error': 'Unsupported file type or error reading file'}), 400
        
        # Check if the selected columns exist
        if col1 not in df1.columns:
            return jsonify({'error': f'Column "{col1}" not found in first file'}), 400
        if col2 not in df2.columns:
            return jsonify({'error': f'Column "{col2}" not found in second file'}), 400
        
        # Clean the key columns: convert to string and strip for case-insensitive comparison
        df1['__compare_key'] = df1[col1].astype(str).str.strip().str.lower()
        df2['__compare_key'] = df2[col2].astype(str).str.strip().str.lower()
        
        # Find common keys
        common_keys = set(df1['__compare_key']).intersection(set(df2['__compare_key']))
        
        # Split data
        common_df1 = df1[df1['__compare_key'].isin(common_keys)].copy()
        common_df2 = df2[df2['__compare_key'].isin(common_keys)].copy()
        
        # Remove temporary keys for storage
        common_df1 = common_df1.drop(columns=['__compare_key'])
        common_df2 = common_df2.drop(columns=['__compare_key'])
        
        unique_df1 = df1[~df1['__compare_key'].isin(common_keys)].copy().drop(columns=['__compare_key'])
        unique_df2 = df2[~df2['__compare_key'].isin(common_keys)].copy().drop(columns=['__compare_key'])
        
        # Prepare data for JSON response
        def prepare_preview(df):
            preview = df.head(20).replace({np.nan: None}).to_dict(orient='records')
            return [{k: nan_to_none(v) for k, v in row.items()} for row in preview]
        
        # Store results
        comparison_results = {
            'common_in_first': prepare_data_for_json(common_df1),
            'common_in_second': prepare_data_for_json(common_df2),
            'unique_in_first': prepare_data_for_json(unique_df1),
            'unique_in_second': prepare_data_for_json(unique_df2),
            'filenames': {
                'file1': file1.filename,
                'file2': file2.filename
            },
            'columns': {
                'file1': col1,
                'file2': col2
            },
            'stats': {
                'common': len(common_df1),
                'unique_in_first': len(unique_df1),
                'unique_in_second': len(unique_df2)
            },
            'all_columns': {
                'file1': df1.drop(columns=['__compare_key']).columns.tolist(),
                'file2': df2.drop(columns=['__compare_key']).columns.tolist()
            }
        }
        
        save_data('comparison_results', comparison_results)
        
        # Prepare previews (first 20 rows)
        preview_common1 = prepare_preview(common_df1)
        preview_common2 = prepare_preview(common_df2)
        preview_unique1 = prepare_preview(unique_df1)
        preview_unique2 = prepare_preview(unique_df2)
        
        return jsonify({
            'success': True,
            'common_in_first': preview_common1,
            'common_in_second': preview_common2,
            'unique_in_first': preview_unique1,
            'unique_in_second': preview_unique2,
            'stats': comparison_results['stats'],
            'columns1': comparison_results['all_columns']['file1'],
            'columns2': comparison_results['all_columns']['file2']
        })
    except Exception as e:
        logger.error(f"Error comparing files: {str(e)}", exc_info=True)
        return jsonify({'error': f"Error comparing files: {str(e)}"}), 500

@compare_files_bp.route('/export', methods=['GET'])
def export_comparison():
    """Export comparison results to Excel."""
    try:
        comparison_data = load_data('comparison_results')
        if not comparison_data:
            return jsonify({'error': 'No comparison data available'}), 400
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Convert JSON data back to DataFrame
            if comparison_data['common_in_first']:
                df_common1 = pd.DataFrame(comparison_data['common_in_first'])
                df_common1.to_excel(writer, sheet_name='Common in First', index=False)
            if comparison_data['common_in_second']:
                df_common2 = pd.DataFrame(comparison_data['common_in_second'])
                df_common2.to_excel(writer, sheet_name='Common in Second', index=False)
            if comparison_data['unique_in_first']:
                df_unique1 = pd.DataFrame(comparison_data['unique_in_first'])
                df_unique1.to_excel(writer, sheet_name='Unique in First', index=False)
            if comparison_data['unique_in_second']:
                df_unique2 = pd.DataFrame(comparison_data['unique_in_second'])
                df_unique2.to_excel(writer, sheet_name='Unique in Second', index=False)
        
        output.seek(0)
        filename = "comparison_results.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting comparison: {str(e)}", exc_info=True)
        return jsonify({'error': f"Error exporting comparison: {str(e)}"}), 500