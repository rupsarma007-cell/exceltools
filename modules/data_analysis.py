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

# Create blueprint with template folder specified
data_analysis_bp = Blueprint('data_analysis', __name__, 
                             template_folder='../templates')

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

def get_dataframe():
    """Load full data from session and return as DataFrame."""
    full_data = load_data('full_data')
    if not full_data:
        return None
    return pd.DataFrame(full_data['full_data'])

@data_analysis_bp.route('/', methods=['GET', 'POST'])
def data_analysis_home():
    """Main entry point for data analysis section."""
    if request.method == 'POST':
        return handle_file_upload()
    
    full_data = load_data('full_data')
    columns = full_data['columns'] if full_data else []
    return render_template('data_analysis.html', columns=columns)

def handle_file_upload():
    """Handle file uploads and process data."""
    try:
        # Clear previous session data
        session.pop('full_data', None)
        
        if 'file' not in request.files:
            logger.warning("No file part in request")
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        logger.debug(f"Received file: {file.filename}")
        
        if file.filename == '':
            logger.warning("No selected file")
            return jsonify({'error': 'No selected file'}), 400
        
        # Check file extension
        if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            logger.warning(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Only CSV and Excel files are allowed'}), 400
        
        # Read file based on extension
        if file.filename.endswith('.csv'):
            logger.debug("Reading CSV file")
            df = pd.read_csv(file)
        else:
            logger.debug("Reading Excel file")
            df = pd.read_excel(file, engine='openpyxl')
        
        logger.debug(f"File read successfully. Shape: {df.shape}")
        
        # Store full data in server storage
        full_data = {
            'filename': file.filename,
            'columns': list(df.columns),  # Preserve original column order
            'full_data': prepare_data_for_json(df),
            'stats': {
                'rows': len(df),
                'columns': len(df.columns),
                'duplicates': int(df.duplicated().sum())
            }
        }
        
        save_data('full_data', full_data)
        logger.debug("Data saved to storage")
        
        # Prepare preview (first 20 rows) with original column order
        preview = full_data['full_data'][:20] if full_data['full_data'] else []
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'columns': full_data['columns'],  # Send original column order
            'preview': preview,
            'stats': full_data['stats']
        })
    except pd.errors.EmptyDataError:
        logger.error("The file is empty")
        return jsonify({'error': 'The file is empty'}), 400
    except pd.errors.ParserError:
        logger.error("Error parsing the file")
        return jsonify({'error': 'Error parsing the file. Please check the file format.'}), 400
    except Exception as e:
        logger.exception("Error processing file")
        return jsonify({'error': f"Error processing file: {str(e)}"}), 500

@data_analysis_bp.route('/find_duplicates', methods=['POST'])
def find_duplicates():
    """Find and return duplicate rows based on selected column."""
    try:
        data = request.get_json()
        column = data.get('column')
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        if column not in df.columns:
            return jsonify({'error': f'Column "{column}" not found'}), 400
        
        # Find duplicates
        duplicates = df[df.duplicated(subset=[column], keep=False)]
        
        # Prepare response
        duplicates_json = prepare_data_for_json(duplicates)
        return jsonify({
            'success': True,
            'duplicates': duplicates_json,
            'count': len(duplicates)
        })
    except Exception as e:
        logger.error(f"Error finding duplicates: {str(e)}")
        return jsonify({'error': f"Error finding duplicates: {str(e)}"}), 500

@data_analysis_bp.route('/export_duplicates', methods=['POST'])
def export_duplicates():
    """Export duplicates to Excel file."""
    try:
        data = request.get_json()
        column = data.get('column')
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        if column not in df.columns:
            return jsonify({'error': f'Column "{column}" not found'}), 400
        
        # Find duplicates
        duplicates = df[df.duplicated(subset=[column], keep=False)]
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            duplicates.to_excel(writer, index=False, sheet_name='Duplicates')
        
        output.seek(0)
        filename = f"duplicates_{secure_filename(column)}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting duplicates: {str(e)}")
        return jsonify({'error': f"Error exporting duplicates: {str(e)}"}), 500

@data_analysis_bp.route('/xlookup', methods=['POST'])
def xlookup():
    """Perform XLOOKUP-like operation."""
    try:
        data = request.get_json()
        lookup_col = data.get('lookup_col')
        lookup_val = data.get('lookup_val')
        return_col = data.get('return_col')
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        if lookup_col not in df.columns:
            return jsonify({'error': f'Lookup column "{lookup_col}" not found'}), 400
        
        # Find matching rows
        result = df[df[lookup_col].astype(str) == str(lookup_val)]
        
        if return_col == 'all':
            # Return entire row
            result_data = prepare_data_for_json(result)
            return jsonify({
                'success': True,
                'result': result_data,
                'count': len(result)
            })
        else:
            # Return specific column
            if return_col not in df.columns:
                return jsonify({'error': f'Return column "{return_col}" not found'}), 400
            
            values = result[return_col].dropna().tolist()
            return jsonify({
                'success': True,
                'result': values,
                'count': len(values)
            })
    except Exception as e:
        logger.error(f"Error performing XLOOKUP: {str(e)}")
        return jsonify({'error': f"Error performing XLOOKUP: {str(e)}"}), 500

@data_analysis_bp.route('/global_search', methods=['POST'])
def global_search():
    """Search across all columns for a string and return matching rows."""
    try:
        data = request.get_json()
        search_str = data.get('search_str', '').lower()
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Convert all values to string for case-insensitive search
        df_str = df.astype(str)
        mask = df_str.apply(lambda col: col.str.lower().str.contains(search_str)).any(axis=1)
        results = df[mask]
        
        # Prepare response
        results_json = prepare_data_for_json(results)
        return jsonify({
            'success': True,
            'results': results_json,
            'count': len(results)
        })
    except Exception as e:
        logger.error(f"Error performing global search: {str(e)}")
        return jsonify({'error': f"Error performing global search: {str(e)}"}), 500

@data_analysis_bp.route('/export_search', methods=['POST'])
def export_search():
    """Export search results to Excel."""
    try:
        data = request.get_json()
        search_str = data.get('search_str', '').lower()
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Find matches
        df_str = df.astype(str)
        mask = df_str.apply(lambda col: col.str.lower().str.contains(search_str)).any(axis=1)
        results = df[mask]
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            results.to_excel(writer, index=False, sheet_name='Search Results')
        
        output.seek(0)
        filename = "search_results.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting search results: {str(e)}")
        return jsonify({'error': f"Error exporting search results: {str(e)}"}), 500

@data_analysis_bp.route('/pivot', methods=['POST'])
def create_pivot():
    """Create pivot table from data."""
    try:
        data = request.get_json()
        index = data.get('index')
        columns = data.get('columns')
        values = data.get('values')
        aggfunc = data.get('aggfunc', 'sum')
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Validate fields
        for field in [index] + ([columns] if columns else []) + [values]:
            if field and field not in df.columns:
                return jsonify({'error': f'Field "{field}" not found'}), 400
        
        # Create pivot table
        pivot = pd.pivot_table(
            df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
            fill_value=0,
            margins=True,
            margins_name='Total'
        )
        
        # Convert to JSON-serializable format
        pivot_json = pivot.reset_index().to_dict(orient='records')
        pivot_columns = pivot.columns.tolist()
        
        # Prepare column headers
        headers = [index] + [str(col) for col in pivot_columns]
        
        return jsonify({
            'success': True,
            'pivot_table': pivot_json,
            'headers': headers,
            'index': index,
            'columns': columns,
            'values': values,
            'aggfunc': aggfunc
        })
    except Exception as e:
        logger.error(f"Error creating pivot table: {str(e)}")
        return jsonify({'error': f"Error creating pivot table: {str(e)}"}), 500

@data_analysis_bp.route('/export_pivot', methods=['POST'])
def export_pivot():
    """Export pivot table to Excel."""
    try:
        data = request.get_json()
        index = data.get('index')
        columns = data.get('columns')
        values = data.get('values')
        aggfunc = data.get('aggfunc', 'sum')
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        # Create pivot table
        pivot = pd.pivot_table(
            df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
            fill_value=0,
            margins=True,
            margins_name='Total'
        )
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pivot.to_excel(writer, sheet_name='Pivot Table')
        
        output.seek(0)
        filename = "pivot_table.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting pivot table: {str(e)}")
        return jsonify({'error': f"Error exporting pivot table: {str(e)}"}), 500

# NEW FEATURE: Filter by Column
@data_analysis_bp.route('/filter_by_column', methods=['POST'])
def filter_by_column():
    """Filter data by specific column and value."""
    try:
        data = request.get_json()
        column = data.get('column')
        value = data.get('value')
        exact_match = data.get('exact_match', True)
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        if column not in df.columns:
            return jsonify({'error': f'Column "{column}" not found'}), 400
        
        # Apply filter
        if exact_match:
            filtered = df[df[column].astype(str) == str(value)]
        else:
            filtered = df[df[column].astype(str).str.contains(str(value), case=False, na=False)]
        
        # Prepare response
        filtered_json = prepare_data_for_json(filtered)
        return jsonify({
            'success': True,
            'filtered_data': filtered_json,
            'count': len(filtered)
        })
    except Exception as e:
        logger.error(f"Error filtering data: {str(e)}")
        return jsonify({'error': f"Error filtering data: {str(e)}"}), 500

@data_analysis_bp.route('/export_filtered', methods=['POST'])
def export_filtered():
    """Export filtered data to Excel."""
    try:
        data = request.get_json()
        column = data.get('column')
        value = data.get('value')
        exact_match = data.get('exact_match', True)
        
        df = get_dataframe()
        if df is None:
            return jsonify({'error': 'No data available'}), 400
        
        if column not in df.columns:
            return jsonify({'error': f'Column "{column}" not found'}), 400
        
        # Apply filter
        if exact_match:
            filtered = df[df[column].astype(str) == str(value)]
        else:
            filtered = df[df[column].astype(str).str.contains(str(value), case=False, na=False)]
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            filtered.to_excel(writer, index=False, sheet_name='Filtered Data')
        
        output.seek(0)
        filename = f"filtered_{secure_filename(column)}_{secure_filename(value)}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting filtered data: {str(e)}")
        return jsonify({'error': f"Error exporting filtered data: {str(e)}"}), 500