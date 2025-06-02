from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Global storage for options data
previous_data = {}
watchlist = []

# HTML template for the web interface
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Options OI Tracker</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; display: flex; align-items: center; gap: 10px; }
        .controls { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; }
        input, select, button { padding: 8px 12px; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #007bff; color: white; cursor: pointer; border: none; }
        button:hover { background: #0056b3; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: bold; color: #555; position: sticky; top: 0; }
        tr:hover { background: #f8f9fa; }
        .positive { color: #28a745; font-weight: bold; }
        .negative { color: #dc3545; font-weight: bold; }
        .high-volume { background: #e3f2fd; }
        .extreme-change { background: #f3e5f5; }
        .status { display: flex; justify-content: space-between; align-items: center; margin: 10px 0; }
        .last-update { color: #666; font-size: 14px; }
        .loading { text-align: center; padding: 50px; }
        .call { color: #28a745; }
        .put { color: #dc3545; }
        .ticker-tag { background: #e9ecef; padding: 2px 8px; border-radius: 3px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Live Options OI Tracker</h1>
        
        <div class="status">
            <div>
                <span id="connection-status">🟢 Connected</span>
                <span class="last-update">Last update: <span id="last-update">Never</span></span>
            </div>
            <button onclick="refreshData()">🔄 Refresh Now</button>
        </div>
        
        <div class="controls">
            <input type="text" id="ticker" placeholder="Ticker (e.g., SPY)" style="text-transform: uppercase;">
            <input type="number" id="strike" placeholder="Strike Price" step="0.5">
            <input type="date" id="expiration" min="2025-01-01">
            <select id="optionType">
                <option value="C">Call</option>
                <option value="P">Put</option>
            </select>
            <button onclick="addToWatchlist()">+ Add to Watchlist</button>
            <button onclick="clearWatchlist()" style="background: #dc3545;">Clear All</button>
        </div>
        
        <div id="content">
            <div class="loading">Loading options data...</div>
        </div>
    </div>
    
    <script>
        let autoRefresh = true;
        
        async function fetchData() {
            try {
                const response = await fetch('/api/options');
                const data = await response.json();
                updateTable(data);
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('connection-status').textContent = '🔴 Disconnected';
            }
        }
        
        function updateTable(data) {
            if (!data.options || data.options.length === 0) {
                document.getElementById('content').innerHTML = '<p>No options in watchlist. Add some above!</p>';
                return;
            }
            
            let html = '<table><thead><tr>';
            html += '<th>Ticker</th><th>Expiration</th><th>Strike</th><th>Type</th>';
            html += '<th>Last</th><th>Bid/Ask</th><th>Volume</th><th>Open Interest</th>';
            html += '<th>OI Change</th><th>% Change</th><th>IV</th><th>Action</th>';
            html += '</tr></thead><tbody>';
            
            data.options.forEach((opt, index) => {
                const rowClass = opt.oi_change > 5000 ? 'high-volume' : 
                               Math.abs(opt.oi_pct_change) > 100 ? 'extreme-change' : '';
                
                html += `<tr class="${rowClass}">`;
                html += `<td><span class="ticker-tag">${opt.ticker}</span></td>`;
                html += `<td>${opt.expiration}</td>`;
                html += `<td>$${opt.strike.toFixed(2)}</td>`;
                html += `<td class="${opt.type.toLowerCase()}">${opt.type}</td>`;
                html += `<td>$${opt.lastPrice.toFixed(2)}</td>`;
                html += `<td>$${opt.bid.toFixed(2)}/$${opt.ask.toFixed(2)}</td>`;
                html += `<td>${opt.volume.toLocaleString()}</td>`;
                html += `<td>${opt.openInterest.toLocaleString()}</td>`;
                
                const changeClass = opt.oi_change > 0 ? 'positive' : 'negative';
                html += `<td class="${changeClass}">${opt.oi_change > 0 ? '+' : ''}${opt.oi_change.toLocaleString()}</td>`;
                html += `<td class="${changeClass}">${opt.oi_pct_change.toFixed(1)}%</td>`;
                html += `<td>${(opt.impliedVolatility * 100).toFixed(1)}%</td>`;
                html += `<td><button onclick="removeFromWatchlist(${index})" style="background: #dc3545; padding: 4px 8px;">Remove</button></td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            document.getElementById('content').innerHTML = html;
        }
        
        async function addToWatchlist() {
            const ticker = document.getElementById('ticker').value.toUpperCase();
            const strike = parseFloat(document.getElementById('strike').value);
            const expiration = document.getElementById('expiration').value;
            const optionType = document.getElementById('optionType').value;
            
            if (!ticker || !strike || !expiration) {
                alert('Please fill all fields');
                return;
            }
            
            const response = await fetch('/api/watchlist/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker, strike, expiration, optionType})
            });
            
            if (response.ok) {
                // Clear form
                document.getElementById('ticker').value = '';
                document.getElementById('strike').value = '';
                fetchData();
            }
        }
        
        async function removeFromWatchlist(index) {
            const response = await fetch(`/api/watchlist/remove/${index}`, {method: 'DELETE'});
            if (response.ok) fetchData();
        }
        
        async function clearWatchlist() {
            if (confirm('Clear all options from watchlist?')) {
                const response = await fetch('/api/watchlist/clear', {method: 'DELETE'});
                if (response.ok) fetchData();
            }
        }
        
        function refreshData() {
            fetchData();
        }
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            if (autoRefresh) fetchData();
        }, 30000);
        
        // Initial load
        fetchData();
        
        // Set default date to next Friday
        const nextFriday = new Date();
        nextFriday.setDate(nextFriday.getDate() + (5 - nextFriday.getDay() + 7) % 7);
        document.getElementById('expiration').value = nextFriday.toISOString().split('T')[0];
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/api/options')
def get_options():
    """Get current options data"""
    global previous_data
    
    results = []
    
    for item in watchlist:
        key = f"{item['ticker']}_{item['expiration']}"
        
        try:
            # Fetch data from yfinance
            ticker = yf.Ticker(item['ticker'])
            opt_chain = ticker.option_chain(item['expiration'])
            
            # Get the specific option
            if item['optionType'] == 'C':
                options_df = opt_chain.calls
            else:
                options_df = opt_chain.puts
                
            option_data = options_df[options_df['strike'] == item['strike']]
            
            if not option_data.empty:
                row = option_data.iloc[0]
                
                # Calculate OI changes
                option_key = f"{key}_{item['strike']}_{item['optionType']}"
                current_oi = row['openInterest']
                
                oi_change = 0
                oi_pct_change = 0
                
                if option_key in previous_data:
                    prev_oi = previous_data[option_key]
                    oi_change = current_oi - prev_oi
                    if prev_oi > 0:
                        oi_pct_change = (oi_change / prev_oi) * 100
                
                previous_data[option_key] = current_oi
                
                results.append({
                    'ticker': item['ticker'],
                    'expiration': item['expiration'],
                    'strike': item['strike'],
                    'type': 'Call' if item['optionType'] == 'C' else 'Put',
                    'lastPrice': row.get('lastPrice', 0),
                    'bid': row.get('bid', 0),
                    'ask': row.get('ask', 0),
                    'volume': int(row.get('volume', 0)),
                    'openInterest': int(current_oi),
                    'impliedVolatility': row.get('impliedVolatility', 0),
                    'oi_change': int(oi_change),
                    'oi_pct_change': oi_pct_change
                })
                
        except Exception as e:
            print(f"Error fetching {item}: {e}")
    
    return jsonify({'options': results})

@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """Add option to watchlist"""
    data = request.json
    watchlist.append(data)
    return jsonify({'status': 'success', 'watchlist_size': len(watchlist)})

@app.route('/api/watchlist/remove/<int:index>', methods=['DELETE'])
def remove_from_watchlist(index):
    """Remove option from watchlist"""
    if 0 <= index < len(watchlist):
        watchlist.pop(index)
    return jsonify({'status': 'success'})

@app.route('/api/watchlist/clear', methods=['DELETE'])
def clear_watchlist():
    """Clear entire watchlist"""
    watchlist.clear()
    previous_data.clear()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
