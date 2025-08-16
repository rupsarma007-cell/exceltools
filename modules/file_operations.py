from flask import Blueprint, request, jsonify, send_file
import pandas as pd
from io import BytesIO
import os

file_ops_bp = Blueprint('file_ops', __name__)

@file_ops_bp.route('/merge', methods=['GET', 'POST'])
def merge_files():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if len(files) < 2:
            return jsonify({'error': 'Please upload at least 2 files'}), 400
        
        dfs = []
        for file in files:
            if file.filename.endswith('.csv'):
                dfs.append(pd.read_csv(file))
            else:
                dfs.append(pd.read_excel(file))
        
        merged_df = pd.concat(dfs, ignore_index=True)
        
        output = BytesIO()
        merged_df.to_excel(output, index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='merged_files.xlsx'
        )
    
    return '''
    <h2>Merge Files</h2>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="files" multiple>
        <button type="submit">Merge Files</button>
    </form>
    '''

@file_ops_bp.route('/compare', methods=['GET', 'POST'])
def compare_files():
    if request.method == 'POST':
        file1 = request.files['file1']
        file2 = request.files['file2']
        compare_col = request.form['compare_column']
        
        df1 = pd.read_csv(file1) if file1.filename.endswith('.csv') else pd.read_excel(file1)
        df2 = pd.read_csv(file2) if file2.filename.endswith('.csv') else pd.read_excel(file2)
        
        common = pd.merge(df1, df2, on=[compare_col])
        unique1 = df1[~df1[compare_col].isin(df2[compare_col])]
        unique2 = df2[~df2[compare_col].isin(df1[compare_col])]
        
        output = BytesIO()
        with pd.ExcelWriter(output) as writer:
            common.to_excel(writer, sheet_name='Common', index=False)
            unique1.to_excel(writer, sheet_name='Unique_to_File1', index=False)
            unique2.to_excel(writer, sheet_name='Unique_to_File2', index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='comparison_results.xlsx'
        )
    
    return '''
    <h2>Compare Files</h2>
    <form method="post" enctype="multipart/form-data">
        File 1: <input type="file" name="file1"><br>
        File 2: <input type="file" name="file2"><br>
        Compare Column: <input type="text" name="compare_column">
        <button type="submit">Compare</button>
    </form>
    '''