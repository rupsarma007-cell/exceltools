from flask import Blueprint, request, send_file
import pandas as pd
from io import BytesIO

converters_bp = Blueprint('converters', __name__)

@converters_bp.route('/convert', methods=['GET', 'POST'])
def convert_files():
    if request.method == 'POST':
        file = request.files['file']
        target_format = request.form['format']
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        output = BytesIO()
        
        if target_format == 'csv':
            df.to_csv(output, index=False)
            mimetype = 'text/csv'
            extension = 'csv'
        else:
            df.to_excel(output, index=False)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            extension = 'xlsx'
        
        output.seek(0)
        return send_file(
            output,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f'converted_file.{extension}'
        )
    
    return '''
    <h2>Convert Files</h2>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <select name="format">
            <option value="xlsx">Excel</option>
            <option value="csv">CSV</option>
        </select>
        <button type="submit">Convert</button>
    </form>
    '''