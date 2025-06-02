from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
CORS(app)

# Alpha Vantage API Key from environment variable
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_KEY', 'demo')

# Storage for tracking OI changes
watchlist = []
previous_oi_data = {}

# HTML template
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Options OI Tracker - Alpha Vantage</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; display: flex; align-items: center; gap: 10px; }
        .status { padding: 10px; background: #f0f8ff; border-radius: 5px; margin: 10px 0; }
        .controls { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; align-items: center; }
        input, select, button { padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
        button { background: #007bff; color: white; cursor: pointer; border: none; }
        button:hover { background: #0056b3; }
        button.remove { background: #dc3545; padding: 5px 10px; }
        button.remove:hover { background: #c82333; }
        .info { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: bold; color: #333; position: sticky; top: 0; }
        tr:hover { background: #f5f5f5; }
        .call { color: #28a745; font-weight: bold; }
        .put { color: #dc3545; font-weight: bold; }
        .positive { color: #28a745; }
        .negative { color: #dc3545; }
        .watchlist-item { background: #f8f9fa; padding: 8px; margin: 5px; border-radius: 5px; display: inline-block; }
        .loading { text-align: center; padding: 20px; }
        .error { color: #dc3545; padding: 10px; background: #f8d7da; border-radius: 5px; }
        .success { color: #155724; padding: 10px; background: #d4edda; border-radius: 5px; }
        .high-volume { background-color: #e3f2fd; }
        .high-oi-change { background-color: #f3e5f5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Options Open Interest Tracker</h1>
        <div class="info">
            <strong>Powered by Alpha Vantage</strong> - Free tier: 500 requests/day, 5/minute<br>
            Data is 15-minute delayed. OI changes appear after second refresh.
        </div>
        
        <div id="apiStatus" class="status">
            Checking API status...
        </div>
        
        <div class="controls">
            <input type="text" id="ticker" placeholder="Ticker (e.g., SPY)" style="text-transform: uppercase;">
            <select id="expiration">
                <option value="2024-12-20">Dec 20, 2024</option>
                <option value="2025-01-17">Jan 17, 2025</option>
                <option value="2025-02-21">Feb 21, 2025</option>
                <option value="2025-03-21">Mar 21, 2025</option>
                <option value="2025-04-18">Apr 18, 2025</option>
                <option value="2025-05-16">May 16, 2025</option>
                <option value="2025-06-20">Jun 20, 2025</option>
                <option value="2025-07-18">Jul 18, 2025</option>
                <option value="2025-08-15">Aug 15, 2025</option>
                <option value="2025-09-19">Sep 19, 2025</option>
            </select>
            <input type="number" id="strike" placeholder="Strike Price" step="0.5">
            <select id="optionType">
                <option value="Call">Call</option>
                <option value="Put">Put</option>
            </select>
            <button onclick="addToWatchlist()">+ Add to Watchlist</button>
            <button onclick="refreshAll()" style="background: #28a745;">🔄 Refresh All</button>
            <button onclick="clearWatchlist()" style="background: #dc3545;">Clear All</button>
        </div>
        
        <div id="watchlistDisplay"></div>
        
        <div id="results"></div>
        
        <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-radius: 5px;">
            <h4>Quick Start:</h4>
            <ol>
                <li>Enter a ticker symbol (e.g., SPY, AAPL, NVDA)</li>
                <li>Select an expiration date from the dropdown</li>
                <li>Enter a strike price</li>
                <li>Choose Call or Put</li>
                <li>Click "Add to Watchlist"</li>
                <li>Use "Refresh All" to update data and see OI changes</li>
            </ol>
        </div>
    </div>
    
    <script>
        async function checkAPIStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.api_working) {
                    document.getElementById('apiStatus').innerHTML = 
                        '<span class="success">✓ API Connected - ' + data.requests_remaining + ' requests remaining today</span>';
                } else {
                    document.getElementById('apiStatus').innerHTML = 
                        '<span class="error">✗ API Error: ' + data.error + '</span>';
                }
            } catch (error) {
                document.getElementById('apiStatus').innerHTML = 
                    '<span class="error">✗ Connection Error</span>';
            }
        }
        
        function formatDate(dateStr) {
            if (!dateStr || dateStr === 'Invalid Date') return 'Invalid Date';
            try {
                const date = new Date(dateStr + 'T12:00:00');
                if (isNaN(date.getTime())) return dateStr; // Return original if invalid
                return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
            } catch (e) {
                return dateStr; // Return original string if error
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
                // Clear strike input for easy adding of multiple strikes
                document.getElementById('strike').value = '';
                displayWatchlist();
                refreshAll();
            } else {
                const error = await response.json();
                alert('Error: ' + error.error);
            }
        }
        
        async function displayWatchlist() {
            const response = await fetch('/api/watchlist');
            const data = await response.json();
            
            let html = '<h3>Watchlist (' + data.watchlist.length + ' options):</h3>';
            if (data.watchlist.length === 0) {
                html += '<p>No options in watchlist. Add some above!</p>';
            } else {
                html += '<div>';
                data.watchlist.forEach((item, index) => {
                    html += `<span class="watchlist-item">
                        ${item.ticker} $${item.strike} ${item.optionType} (${formatDate(item.expiration)})
                        <button class="remove" onclick="removeFromWatchlist(${index})">×</button>
                    </span>`;
                });
                html += '</div>';
            }
            
            document.getElementById('watchlistDisplay').innerHTML = html;
        }
        
        async function removeFromWatchlist(index) {
            await fetch(`/api/watchlist/remove/${index}`, { method: 'DELETE' });
            displayWatchlist();
            refreshAll();
        }
        
        async function clearWatchlist() {
            if (confirm('Clear all options from watchlist?')) {
                await fetch('/api/watchlist/clear', { method: 'DELETE' });
                displayWatchlist();
                document.getElementById('results').innerHTML = '';
            }
        }
        
        async function refreshAll() {
            document.getElementById('results').innerHTML = '<div class="loading">Loading options data...</div>';
            
            const response = await fetch('/api/refresh');
            const data = await response.json();
            
            if (data.error) {
                document.getElementById('results').innerHTML = 
                    `<div class="error">Error: ${data.error}</div>`;
                return;
            }
            
            if (data.options.length === 0) {
                document.getElementById('results').innerHTML = 
                    '<p>No options data available. Add items to your watchlist.</p>';
                return;
            }
            
            let html = '<h3>Options Data:</h3>';
            html += '<table>';
            html += '<tr><th>Option</th><th>Last</th><th>Bid/Ask</th><th>Volume</th><th>Open Interest</th><th>OI Change</th><th>% Change</th><th>IV</th></tr>';
            
            data.options.forEach(opt => {
                const typeClass = opt.type === 'Call' ? 'call' : 'put';
                const oiChangeClass = opt.oi_change > 0 ? 'positive' : opt.oi_change < 0 ? 'negative' : '';
                const rowClass = opt.volume > 10000 ? 'high-volume' : (Math.abs(opt.oi_change) > 1000 ? 'high-oi-change' : '');
                
                html += `<tr class="${rowClass}">`;
                html += `<td><strong>${opt.ticker}</strong> $${opt.strike} <span class="${typeClass}">${opt.type}</span> ${formatDate(opt.expiration)}</td>`;
                html += `<td>$${opt.last.toFixed(2)}</td>`;
                html += `<td>$${opt.bid.toFixed(2)}/$${opt.ask.toFixed(2)}</td>`;
                html += `<td>${opt.volume.toLocaleString()}</td>`;
                html += `<td>${opt.open_interest.toLocaleString()}</td>`;
                html += `<td class="${oiChangeClass}">${opt.oi_change > 0 ? '+' : ''}${opt.oi_change.toLocaleString()}</td>`;
                html += `<td class="${oiChangeClass}">${opt.oi_pct_change.toFixed(1)}%</td>`;
                html += `<td>${(opt.implied_volatility * 100).toFixed(1)}%</td>`;
                html += '</tr>';
            });
            
            html += '</table>';
            html += `<p style="margin-top: 20px; color: #666;">Last updated: ${new Date().toLocaleTimeString()}</p>`;
            
            document.getElementById('results').innerHTML = html;
        }
        
        // Auto-refresh every 60 seconds
        setInterval(() => {
            checkAPIStatus();
            if (document.getElementById('watchlistDisplay').innerText.includes('options)')) {
                refreshAll();
            }
        }, 60000);
        
        // Initialize
        checkAPIStatus();
        displayWatchlist();
        
        // Set default ticker
        document.getElementById('ticker').value = 'SPY';
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/api/status')
def api_status():
    """Check API status and remaining requests"""
    try:
        # Test API with a simple quote request
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={ALPHA_VANTAGE_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if 'Error Message' in data:
            return jsonify({'api_working': False, 'error': 'Invalid API key'})
        elif 'Note' in data:
            return jsonify({'api_working': False, 'error': 'API limit reached', 'requests_remaining': 0})
        else:
            # Estimate remaining requests (Alpha Vantage doesn't provide exact count)
            return jsonify({'api_working': True, 'requests_remaining': '~500'})
    except Exception as e:
        return jsonify({'api_working': False, 'error': str(e)})

@app.route('/api/expirations/<ticker>')
def get_expirations(ticker):
    """Get available expiration dates for a ticker"""
    try:
        # First, let's provide some common expiration dates as fallback
        from datetime import datetime, timedelta
        today = datetime.now()
        
        # Generate standard monthly expiration dates (3rd Friday of each month)
        dates = []
        for i in range(6):  # Next 6 months
            # Get first day of the month
            if i == 0:
                month = today
            else:
                month = today + timedelta(days=30*i)
            
            # Find the third Friday
            first_day = month.replace(day=1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
            third_friday = first_friday + timedelta(weeks=2)
            
            dates.append(third_friday.strftime('%Y-%m-%d'))
        
        # Try to get real dates from Alpha Vantage
        url = f"https://www.alphavantage.co/query?function=REALTIME_OPTIONS&symbol={ticker}&apikey={ALPHA_VANTAGE_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if 'data' in data and len(data['data']) > 0:
            # Extract unique expiration dates
            api_dates = list(set(opt['expiration'] for opt in data['data'] if 'expiration' in opt))
            if api_dates:
                api_dates.sort()
                # Return API dates if available
                return jsonify({'dates': api_dates[:10]})
        
        # Return generated dates as fallback
        return jsonify({'dates': dates})
            
    except Exception as e:
        # If all fails, return some standard dates
        return jsonify({
            'dates': [
                '2024-12-20',  # December monthly
                '2025-01-17',  # January monthly
                '2025-02-21',  # February monthly
                '2025-03-21',  # March monthly
                '2025-04-18',  # April monthly
                '2025-05-16'   # May monthly
            ],
            'error': f'Using default dates. Error: {str(e)}'
        })

@app.route('/api/watchlist')
def get_watchlist():
    return jsonify({'watchlist': watchlist})

@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    data = request.json
    
    # Check if already in watchlist
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
    
    # Group by ticker for efficiency
    ticker_groups = defaultdict(list)
    for item in watchlist:
        ticker_groups[item['ticker']].append(item)
    
    for ticker, items in ticker_groups.items():
        try:
            # Fetch real-time options data
            url = f"https://www.alphavantage.co/query?function=REALTIME_OPTIONS&symbol={ticker}&apikey={ALPHA_VANTAGE_KEY}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if 'data' not in data:
                if 'Note' in data:
                    return jsonify({'error': 'API call limit reached. Please wait 1 minute.'})
                elif 'Error Message' in data:
                    return jsonify({'error': 'Invalid API key or symbol'})
                continue
            
            # Process each watchlist item
            for item in items:
                # Find matching option
                found = False
                for opt in data['data']:
                    if (opt['expiration'] == item['expiration'] and 
                        float(opt['strike']) == item['strike'] and
                        opt['type'].upper() == item['optionType'].upper()):
                        
                        # Calculate OI change
                        key = f"{ticker}_{item['expiration']}_{item['strike']}_{item['optionType']}"
                        current_oi = int(float(opt.get('open_interest', 0)))
                        
                        oi_change = 0
                        oi_pct_change = 0
                        
                        if key in previous_oi_data:
                            prev_oi = previous_oi_data[key]
                            oi_change = current_oi - prev_oi
                            if prev_oi > 0:
                                oi_pct_change = (oi_change / prev_oi) * 100
                        
                        previous_oi_data[key] = current_oi
                        
                        results.append({
                            'ticker': ticker,
                            'expiration': item['expiration'],
                            'strike': item['strike'],
                            'type': item['optionType'],
                            'last': float(opt.get('last', 0)),
                            'bid': float(opt.get('bid', 0)),
                            'ask': float(opt.get('ask', 0)),
                            'volume': int(float(opt.get('volume', 0))),
                            'open_interest': current_oi,
                            'oi_change': oi_change,
                            'oi_pct_change': oi_pct_change,
                            'implied_volatility': float(opt.get('implied_volatility', 0))
                        })
                        found = True
                        break
                
                if not found:
                    # Option not found in data - might be expired or invalid
                    results.append({
                        'ticker': ticker,
                        'expiration': item['expiration'],
                        'strike': item['strike'],
                        'type': item['optionType'],
                        'last': 0,
                        'bid': 0,
                        'ask': 0,
                        'volume': 0,
                        'open_interest': 0,
                        'oi_change': 0,
                        'oi_pct_change': 0,
                        'implied_volatility': 0
                    })
                        
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            continue
    
    return jsonify({'options': results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
