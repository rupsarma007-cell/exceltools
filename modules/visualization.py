from flask import Blueprint, request, jsonify
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64

visualization_bp = Blueprint('visualization', __name__)

@visualization_bp.route('/chart', methods=['GET', 'POST'])
def generate_chart():
    if request.method == 'POST':
        file = request.files['file']
        chart_type = request.form['chart_type']
        x_col = request.form['x_col']
        y_col = request.form['y_col']
        
        df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
        
        plt.figure(figsize=(10, 6))
        
        if chart_type == 'bar':
            df.plot.bar(x=x_col, y=y_col)
        elif chart_type == 'line':
            df.plot.line(x=x_col, y=y_col)
        elif chart_type == 'pie':
            df.plot.pie(y=y_col, labels=df[x_col])
        
        buf = BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return jsonify({'image': image_base64})
    
    return '''
    <h2>Create Chart</h2>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="file"><br>
        Chart Type:
        <select name="chart_type">
            <option value="bar">Bar Chart</option>
            <option value="line">Line Chart</option>
            <option value="pie">Pie Chart</option>
        </select><br>
        X Column: <input type="text" name="x_col"><br>
        Y Column: <input type="text" name="y_col"><br>
        <button type="submit">Generate Chart</button>
    </form>
    <div id="chartResult"></div>
    <script>
        document.querySelector('form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const response = await fetch('/charts/chart', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            document.getElementById('chartResult').innerHTML = 
                `<img src="data:image/png;base64,${result.image}">`;
        });
    </script>
    '''