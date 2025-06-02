from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Global storage
watchlist = []
previous_data = {}

# HTML template
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Options OI Tracker</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        h1 { color: #333; }
        .controls { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; align-items: center; }
        input, select, button { padding: 8px 12px; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #007bff; color: white; cursor: pointer; border: none; }
        button:hover { background: #0056b3; }
        .status { margin: 20px 0; padding: 10px; background: #f0f0f0; border-radius: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: bold; }
        .error { color: red; }
        .success { color: green; }
        .call { color: green; font-weight: bold; }
        .put { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Options OI Tracker</h1>
        
        <div class="controls">
            <input type="text" id="ticker" placeholder="Ticker (e.g., SPY)" style="text-transform: uppercase;">
            <input type="number" id="strike" placeholder="Strike Price" step="0.5">
            <select id="expiration">
                <option value="2024-12-20">Dec 20, 2024</option>
                <option value="2025-01-17">Jan 17, 2025</option>
                <option value="2025-02-21">Feb 21, 2025</option>
                <option value="2025-03-21">Mar 21, 2025</option>
            </select>
            <select id="optionType">
                <option value="C">Call</option>
                <option value="P">Put</option>
            </select>
            <button onclick="addOption()">Add Option</button>
            <button onclick="refreshData()">Refresh Data</button>
            <button onclick="clearAll()" style="background: #dc3545;">Clear All</button>
        </div>
        
        <div id="status" class="status"></div>
        
        <div id="watchlist"></div>
        
        <div id="data"></div>
    </div>
    
    <script>
        let watchlist = [];
        
        async function addOption() {
            const ticker = document.getElementById('ticker').value.toUpperCase();
            const strike = parseFloat(document.getElementById('strike').value);
            const expiration = document.getElementById('expiration').value;
            const optionType = document.getElementById('optionType').value;
            
            if (!ticker || !strike) {
                alert('Please enter ticker and strike price');
                return;
            }
            
            updateStatus('Adding option to watchlist...');
            
            const response = await fetch('/api/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker, strike, expiration, optionType})
            });
            
            const result = await response.json();
            
            if (result.success) {
                updateStatus(`Added: ${ticker} $${strike} ${optionType === 'C' ? 'Call' : 'Put'}`, 'success');
                document.getElementById('ticker').value = '';
                document.getElementById('strike').value = '';
                getWatchlist();
                getData();
            } else {
                updateStatus('Error adding option: ' + result.error, 'error');
            }
        }
        
        async function getWatchlist() {
            const response = await fetch('/api/watchlist');
            const data = await response.json();
            
            let html = '<h3>Watchlist:</h3>';
            if (data.watchlist.length === 0) {
                html += '<p>No options in watchlist</p>';
            } else {
                html += '<ul>';
                data.watchlist.forEach((item, index) => {
                    html += `<li>${item.ticker} $${item.strike} ${item.optionType === 'C' ? 'Call' : 'Put'} (${item.expiration}) 
                             <button onclick="removeOption(${index})" style="background: red; padding: 2px 8px;">X</button></li>`;
                });
                html += '</ul>';
            }
            
            document.getElementById('watchlist').innerHTML = html;
        }
        
        async function getData() {
            updateStatus('Fetching option data...');
            
            const response = await fetch('/api/data');
            const data = await response.json();
            
            if (data.error) {
                updateStatus('Error: ' + data.error, 'error');
                return;
            }
            
            if (data.results.length === 0) {
                document.getElementById('data').innerHTML = '<p>No data available yet. Add options to watchlist first.</p>';
                updateStatus('Ready');
                return;
            }
            
            let html = '<h3>Options Data:</h3>';
            html += '<table>';
            html += '<tr><th>Option</th><th>Last Price</th><th>Volume</th><th>Open Interest</th><th>OI Change</th><th>Status</th></tr>';
            
            data.results.forEach(opt => {
                const typeClass = opt.type === 'Call' ? 'call' : 'put';
                html += '<tr>';
                html += `<td><strong>${opt.ticker}</strong> $${opt.strike} <span class="${typeClass}">${opt.type}</span> ${opt.expiration}</td>`;
                
                if (opt.error) {
                    html += `<td colspan="5" class="error">Error: ${opt.error}</td>`;
                } else {
                    html += `<td>$${opt.lastPrice.toFixed(2)}</td>`;
                    html += `<td>${opt.volume.toLocaleString()}</td>`;
                    html += `<td>${opt.openInterest.toLocaleString()}</td>`;
                    html += `<td>${opt.oi_change > 0 ? '+' : ''}${opt.oi_change.toLocaleString()}</td>`;
                    html += `<td>${opt.status}</td>`;
                }
                html += '</tr>';
            });
            
            html += '</table>';
            document.getElementById('data').innerHTML = html;
            updateStatus('Last updated: ' + new Date().toLocaleTimeString());
        }
        
        async function removeOption(index) {
            await fetch(`/api/remove/${index}`, { method: 'DELETE' });
            getWatchlist();
            getData();
        }
        
        async function clearAll() {
            if (confirm('Clear all options?')) {
                await fetch('/api/clear', { method: 'DELETE' });
                getWatchlist();
                getData();
            }
        }
        
        function refreshData() {
            getData();
        }
        
        function updateStatus(message, type = '') {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
        }
        
        // Initial load
        getWatchlist();
        getData();
        
        // Auto refresh every 30 seconds
        setInterval(getData, 30000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/api/watchlist')
def get_watchlist():
    return jsonify({'watchlist': watchlist})

@app.route('/api/add', methods=['POST'])
def add_option():
    try:
        data = request.json
        watchlist.append(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove/<int:index>', methods=['DELETE'])
def remove_option(index):
    if 0 <= index < len(watchlist):
        watchlist.pop(index)
    return jsonify({'success': True})

@app.route('/api/clear', methods=['DELETE'])
def clear_watchlist():
    watchlist.clear()
    previous_data.clear()
    return jsonify({'success': True})

@app.route('/api/data')
def get_data():
    results = []
    
    for item in watchlist:
        try:
            # Create a result entry
            result = {
                'ticker': item['ticker'],
                'strike': item['strike'],
                'expiration': item['expiration'],
                'type': 'Call' if item['optionType'] == 'C' else 'Put',
                'status': 'Fetching...'
            }
            
            # Try to get option data
            ticker = yf.Ticker(item['ticker'])
            
            # Get option chain
            try:
                opt_chain = ticker.option_chain(item['expiration'])
                
                if item['optionType'] == 'C':
                    options_df = opt_chain.calls
                else:
                    options_df = opt_chain.puts
                
                # Find the specific strike
                option_data = options_df[options_df['strike'] == item['strike']]
                
                if not option_data.empty:
                    row = option_data.iloc[0]
                    
                    # Get current OI
                    current_oi = int(row.get('openInterest', 0))
                    
                    # Calculate OI change
                    key = f"{item['ticker']}_{item['strike']}_{item['expiration']}_{item['optionType']}"
                    oi_change = 0
                    if key in previous_data:
                        oi_change = current_oi - previous_data[key]
                    
                    previous_data[key] = current_oi
                    
                    result.update({
                        'lastPrice': float(row.get('lastPrice', 0)),
                        'volume': int(row.get('volume', 0)),
                        'openInterest': current_oi,
                        'oi_change': oi_change,
                        'status': 'OK',
                        'error': None
                    })
                else:
                    result.update({
                        'lastPrice': 0,
                        'volume': 0,
                        'openInterest': 0,
                        'oi_change': 0,
                        'status': 'Strike not found',
                        'error': 'Strike price not found in option chain'
                    })
                    
            except Exception as e:
                result.update({
                    'lastPrice': 0,
                    'volume': 0,
                    'openInterest': 0,
                    'oi_change': 0,
                    'status': 'Data error',
                    'error': str(e)
                })
                
            results.append(result)
            
        except Exception as e:
            results.append({
                'ticker': item['ticker'],
                'strike': item['strike'],
                'expiration': item['expiration'],
                'type': 'Call' if item['optionType'] == 'C' else 'Put',
                'lastPrice': 0,
                'volume': 0,
                'openInterest': 0,
                'oi_change': 0,
                'status': 'Error',
                'error': str(e)
            })
    
    return jsonify({'results': results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
