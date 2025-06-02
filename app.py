from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime
import time

app = Flask(__name__)
CORS(app)

# Polygon.io API Key
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', 'YOUR_KEY_HERE')

# Storage
watchlist = []
previous_oi_data = {}

# HTML template
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Options OI Tracker</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .status { padding: 10px; background: #f0f8ff; border-radius: 5px; margin: 10px 0; }
        .controls { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; align-items: center; }
        input, select, button { padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
        button { background: #007bff; color: white; cursor: pointer; border: none; }
        button:hover { background: #0056b3; }
        button.remove { background: #dc3545; padding: 5px 10px; }
        .info { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: bold; }
        tr:hover { background: #f5f5f5; }
        .call { color: #28a745; font-weight: bold; }
        .put { color: #dc3545; font-weight: bold; }
        .positive { color: #28a745; }
        .negative { color: #dc3545; }
        .watchlist-item { background: #f8f9fa; padding: 8px 12px; margin: 5px; border-radius: 5px; display: inline-block; }
        .success { color: #155724; background: #d4edda; padding: 10px; border-radius: 5px; }
        .error { color: #721c24; background: #f8d7da; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Options OI Tracker</h1>
        
        <div class="info">
            <strong>Powered by Polygon.io</strong><br>
            Free tier: 5 calls/minute | Basic: $9.99/month
        </div>
        
        <div id="apiStatus" class="status">Checking API...</div>
        
        <div class="controls">
            <input type="text" id="ticker" placeholder="Ticker (e.g., SPY)" style="text-transform: uppercase;" value="SPY">
            <input type="date" id="expiration" min="2024-12-01" max="2027-12-31">
            <input type="number" id="strike" placeholder="Strike Price" step="0.5">
            <select id="optionType">
                <option value="call">Call</option>
                <option value="put">Put</option>
            </select>
            <button onclick="addToWatchlist()">+ Add to Watchlist</button>
            <button onclick="refreshAll()" style="background: #28a745;">Refresh All</button>
            <button onclick="clearWatchlist()" style="background: #dc3545;">Clear All</button>
        </div>
        
        <div id="watchlistDisplay"></div>
        <div id="results"></div>
    </div>
    
    <script>
        // Set default date to next Friday
        function setDefaultDate() {
            const today = new Date();
            const friday = new Date(today);
            const daysUntilFriday = (5 - today.getDay() + 7) % 7 || 7;
            friday.setDate(today.getDate() + daysUntilFriday);
            document.getElementById('expiration').value = friday.toISOString().split('T')[0];
        }
        
        async function checkAPI() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.working) {
                    document.getElementById('apiStatus').innerHTML = 
                        '<div class="success">API Connected</div>';
                } else {
                    document.getElementById('apiStatus').innerHTML = 
                        '<div class="error">API Error: ' + data.error + '</div>';
                }
            } catch (error) {
                document.getElementById('apiStatus').innerHTML = 
                    '<div class="error">Connection Error</div>';
            }
        }
        
        async function addToWatchlist() {
            const ticker = document.getElementById('ticker').value.toUpperCase();
            const expiration = document.getElementById('expiration').value;
            const strike = parseFloat(document.getElementById('strike').value);
            const optionType = document.getElementById('optionType').value;
            
            if (!ticker || !expiration || !strike) {
                alert('Please fill all fields');
                return;
            }
            
            const response = await fetch('/api/watchlist/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticker, expiration, strike, optionType})
            });
            
            if (response.ok) {
                document.getElementById('strike').value = '';
                displayWatchlist();
                refreshAll();
            } else {
                const data = await response.json();
                alert('Error: ' + data.error);
            }
        }
        
        async function displayWatchlist() {
            const response = await fetch('/api/watchlist');
            const data = await response.json();
            
            let html = '<h3>Watchlist (' + data.watchlist.length + ' options):</h3>';
            if (data.watchlist.length === 0) {
                html += '<p>No options in watchlist.</p>';
            } else {
                html += '<div>';
                data.watchlist.forEach((item, index) => {
                    html += '<span class="watchlist-item">';
                    html += item.ticker + ' $' + item.strike + ' ' + item.optionType + ' (' + item.expiration + ') ';
                    html += '<button class="remove" onclick="removeFromWatchlist(' + index + ')">×</button>';
                    html += '</span>';
                });
                html += '</div>';
            }
            
            document.getElementById('watchlistDisplay').innerHTML = html;
        }
        
        async function removeFromWatchlist(index) {
            await fetch('/api/watchlist/remove/' + index, { method: 'DELETE' });
            displayWatchlist();
            refreshAll();
        }
        
        async function clearWatchlist() {
            if (confirm('Clear all options?')) {
                await fetch('/api/watchlist/clear', { method: 'DELETE' });
                displayWatchlist();
                document.getElementById('results').innerHTML = '';
            }
        }
        
        async function refreshAll() {
            document.getElementById('results').innerHTML = '<p>Loading...</p>';
            
            const response = await fetch('/api/refresh');
            const data = await response.json();
            
            if (data.error) {
                document.getElementById('results').innerHTML = 
                    '<div class="error">Error: ' + data.error + '</div>';
                return;
            }
            
            if (data.options.length === 0) {
                document.getElementById('results').innerHTML = '<p>No data available.</p>';
                return;
            }
            
            let html = '<h3>Options Data:</h3>';
            html += '<table>';
            html += '<tr><th>Option</th><th>Last</th><th>Bid/Ask</th><th>Volume</th><th>Open Interest</th><th>OI Change</th><th>% Change</th></tr>';
            
            data.options.forEach(opt => {
                const typeClass = opt.type === 'call' ? 'call' : 'put';
                const changeClass = opt.oi_change > 0 ? 'positive' : opt.oi_change < 0 ? 'negative' : '';
                
                html += '<tr>';
                html += '<td><strong>' + opt.ticker + '</strong> $' + opt.strike + ' <span class="' + typeClass + '">' + opt.type + '</span> ' + opt.expiration + '</td>';
                html += '<td>$' + opt.last_price.toFixed(2) + '</td>';
                html += '<td>$' + opt.bid.toFixed(2) + '/$' + opt.ask.toFixed(2) + '</td>';
                html += '<td>' + opt.volume.toLocaleString() + '</td>';
                html += '<td>' + opt.open_interest.toLocaleString() + '</td>';
                html += '<td class="' + changeClass + '">' + (opt.oi_change > 0 ? '+' : '') + opt.oi_change.toLocaleString() + '</td>';
                html += '<td class="' + changeClass + '">' + opt.oi_pct_change.toFixed(1) + '%</td>';
                html += '</tr>';
            });
            
            html += '</table>';
            html += '<p>Last updated: ' + new Date().toLocaleTimeString() + '</p>';
            
            document.getElementById('results').innerHTML = html;
        }
        
        // Initialize
        setDefaultDate();
        checkAPI();
        displayWatchlist();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/api/status')
def api_status():
    """Check Polygon API status"""
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/AAPL/prev?apiKey={POLYGON_API_KEY}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return jsonify({'working': True})
        elif response.status_code == 401:
            return jsonify({'working': False, 'error': 'Invalid API key'})
        else:
            return jsonify({'working': False, 'error': f'API error: {response.status_code}'})
    except Exception as e:
        return jsonify({'working': False, 'error': str(e)})

@app.route('/api/watchlist')
def get_watchlist():
    return jsonify({'watchlist': watchlist})

@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    data = request.json
    
    # Check if already exists
    for item in watchlist:
        if (item['ticker'] == data['ticker'] and 
            item['strike'] == data['strike'] and 
            item['expiration'] == data['expiration'] and
            item['optionType'] == data['optionType']):
            return jsonify({'error': 'Already in watchlist'}), 400
    
    watchlist.append(data)
    return jsonify({'success': True})

@app.route('/api/watchlist/remove/<int:index>', methods=['DELETE'])
def remove_from_watchlist(index):
    if 0 <= index < len(watchlist):
        watchlist.pop(index)
    return jsonify({'success': True})

@app.route('/api/watchlist/clear', methods=['DELETE'])
def clear_watchlist():
    watchlist.clear()
    previous_oi_data.clear()
    return jsonify({'success': True})

@app.route('/api/refresh')
def refresh_data():
    """Fetch current data for all watchlist items"""
    if not watchlist:
        return jsonify({'options': []})
    
    results = []
    
    for item in watchlist:
        try:
            # Build option symbol for Polygon
            # Format: O:TICKER[YYMMDD][C/P][STRIKE*1000]
            date_obj = datetime.strptime(item['expiration'], '%Y-%m-%d')
            exp_formatted = date_obj.strftime('%y%m%d')
            strike_formatted = f"{int(item['strike'] * 1000):08d}"
            option_type = 'C' if item['optionType'] == 'call' else 'P'
            option_symbol = f"O:{item['ticker']}{exp_formatted}{option_type}{strike_formatted}"
            
            # Get option data from Polygon
            url = f"https://api.polygon.io/v2/aggs/ticker/{option_symbol}/prev?apiKey={POLYGON_API_KEY}"
            response = requests.get(url, timeout=10)
            
            # Default values
            result_data = {
                'ticker': item['ticker'],
                'expiration': item['expiration'],
                'strike': item['strike'],
                'type': item['optionType'],
                'last_price': 0,
                'bid': 0,
                'ask': 0,
                'volume': 0,
                'open_interest': 0,
                'oi_change': 0,
                'oi_pct_change': 0
            }
            
            if response.status_code == 200:
                data = response.json()
                if 'results' in data and len(data['results']) > 0:
                    result = data['results'][0]
                    
                    # Update with actual data
                    result_data['last_price'] = result.get('c', 0)  # Close price
                    result_data['volume'] = int(result.get('v', 0))  # Volume
                    
                    # For Polygon, we might need different endpoint for OI
                    # This is simplified - you may need to use options chain endpoint
                    
            # Calculate OI change (simplified for now)
            key = f"{item['ticker']}_{item['expiration']}_{item['strike']}_{item['optionType']}"
            current_oi = result_data['open_interest']
            
            if key in previous_oi_data:
                prev_oi = previous_oi_data[key]
                result_data['oi_change'] = current_oi - prev_oi
                if prev_oi > 0:
                    result_data['oi_pct_change'] = (result_data['oi_change'] / prev_oi) * 100
            
            previous_oi_data[key] = current_oi
            results.append(result_data)
            
            # Rate limiting for free tier
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error fetching {item}: {e}")
            # Add with default values on error
            results.append({
                'ticker': item['ticker'],
                'expiration': item['expiration'],
                'strike': item['strike'],
                'type': item['optionType'],
                'last_price': 0,
                'bid': 0,
                'ask': 0,
                'volume': 0,
                'open_interest': 0,
                'oi_change': 0,
                'oi_pct_change': 0
            })
    
    return jsonify({'options': results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
