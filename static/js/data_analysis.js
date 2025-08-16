document.addEventListener('DOMContentLoaded', function() {
    // File upload handling
    document.getElementById('uploadBtn').addEventListener('click', uploadFile);
    document.getElementById('findDupesBtn').addEventListener('click', findDuplicates);
    
    let currentData = null;
    
    async function uploadFile() {
        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];
        
        if (!file) {
            alert('Please select a file first');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/data/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Store the data and display results
            currentData = data;
            displayFileInfo(data);
            populateColumnSelect(data.columns);
            displayPreview(data.preview);
            
            // Show results section
            document.getElementById('resultsSection').style.display = 'block';
            
        } catch (error) {
            console.error('Error:', error);
            alert('Error processing file: ' + error.message);
        }
    }
    
    function displayFileInfo(data) {
        document.getElementById('filename').textContent = data.filename;
        document.getElementById('dimensions').textContent = 
            `${data.stats.rows} rows × ${data.stats.columns} columns`;
        document.getElementById('dupeCount').textContent = data.stats.duplicates;
    }
    
    function populateColumnSelect(columns) {
        const select = document.getElementById('dupeColumn');
        select.innerHTML = '';
        
        columns.forEach(col => {
            const option = document.createElement('option');
            option.value = col;
            option.textContent = col;
            select.appendChild(option);
        });
    }
    
    function displayPreview(previewData) {
        const table = document.getElementById('previewTable');
        table.innerHTML = '';
        
        // Create header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        Object.keys(previewData[0]).forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create body
        const tbody = document.createElement('tbody');
        
        previewData.forEach(row => {
            const tr = document.createElement('tr');
            
            Object.values(row).forEach(value => {
                const td = document.createElement('td');
                td.textContent = value;
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
    }
    
    async function findDuplicates() {
        if (!currentData) return;
        
        const column = document.getElementById('dupeColumn').value;
        
        try {
            const response = await fetch('/data/find_duplicates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    data: currentData.preview,
                    column: column
                })
            });
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            alert(`Found ${data.count} duplicate entries`);
            displayPreview(data.duplicates);
            
        } catch (error) {
            console.error('Error:', error);
            alert('Error finding duplicates: ' + error.message);
        }
    }
});