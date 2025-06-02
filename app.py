from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import time

app = Flask(__name__)
CORS(app)

# Polygon.io API Key - Get free at https://polygon.io or $9.99/month for basic
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', 'YOUR_KEY_HERE')

# Storage
watchlist = []
previous_oi_data = {}

# HTML template
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Options OI Tracker - Polygon.io</title>
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
        .info { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: bold; color: #333; }
        tr:hover { background: #f5f5f5; }
        .call { color: #28a745; font-weight: bold; }
        .put { color: #dc3545; font-weight: bold; }
        .positive { color: #28a745; }
        .negative { color: #dc3545; }
        .watchlist-item { background: #f8f9fa; padding: 8px 12px; margin: 5px; border-radius: 5px; display: inline-block; }
        .success { color: #155724; background: #d4edda; padding: 10px; border-radius: 5px; }
        .error { color: #721c24; background: #f8d7da; padding: 10px; border-radius: 5px; }
        .loading { text-align: center; padding: 20px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Options OI Tracker - Polygon.io</h1>
        
        <div class="info">
            <strong>Powered by Polygon.io</strong> - Real market data<br>
            Free tier: 5 calls/minute | Basic: $9.99/month unlimited<br>
            Get your API key at <a href="https://polygon.io" target="_blank">polygon.io</a>
        </div>
        
        <div id="apiStatus" class="status">Checking API...</div>
        
        <div class="controls">
            <input type="text" id="ticker" placeholder="Ticker (e.g., SPY)" style="text-transform: uppercase;" value="SPY">
            <select id="expiration">
                <option value="">Loading dates...</option>
            </select>
            <input type="number" id="strike" placeholder="Strike Price" step="0.5">
            <select id="optionType">
                <option value="call">Call</option>
                <option value="put">Put</option>
            </select>
            <button onclick="addToWatchlist()">+ Add to Watchlist</button>
            <button onclick="refreshAll()" style="background: #28a745;">🔄 Refresh All</button>
            <button onclick="clearWatchlist()" style="background: #dc3545;">Clear All</button>
        </div>
        
        <div id="watchlistDisplay"></div>
        
        <div id="results"></div>
    </div>
    
    <script>
        let currentExpirations = [];
        
        async function checkAPI() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.working) {
                    document.getElementById('apiStatus').innerHTML = 
                        '<div class="success">✓ API Connected - ' + data.tier + '</div>';
                } else {
                    document.getElementById('apiStatus').innerHTML = 
                        '<div class="error">✗ API Error: ' + data.error + '</div>';
                }
            } catch (error) {
                document.getElementById('apiStatus').innerHTML = 
                    '<div class="error">✗ Connection Error</div>';
            }
        }
        
        async function loadExpirations() {
            const ticker = document.getElementById('ticker').value.toUpperCase();
            if (!ticker) return;
            
            const select = document.getElementById('expiration');
            select.innerHTML = '<option value="">Loading...</option>';
            
            try {
                const response = await fetch(`/api/expirations/${ticker}`);
                const data = await response.json();
                
                if (data.expirations && data.expirations.length > 0) {
                    currentExpirations = data.expirations;
                    select.innerHTML = '';
                    
                    data.expirations.forEach(exp => {
                        const option = document.createElement('option');
                        option.value = exp;
                        const date = new Date(exp);
                        option.textContent = date.toLocaleDateString('en-US', { 
                            year: 'numeric', 
                            month: 'short', 
                            day: 'numeric',
                            weekday: 'short'
                        });
                        select.appendChild(option);
                    });
                } else {
                    select.innerHTML = '<option value="">No expirations found</option>';
                }
            } catch (error) {
                select.innerHTML = '<option value="">Error loading dates</option>';
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
                html += '<p>No options in watchlist. Add some above!</p>';
            } else {
                html += '<div>';
                data.watchlist.forEach((item, index) => {
                    const date = new Date(item.expiration);
                    const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    html += `<span class="watchlist-item">
                        ${item.ticker} $${item.strike} ${item.optionType} (${dateStr})
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
            if (document.querySelector('.watchlist-item')) {
                document.getElementById('results').innerHTML = '<div class="loading">Loading options data...</div>';
            }
            
            const response = await fetch('/api/refresh');
            const data = await response.json();
            
            if (data.error) {
                document.getElementById('results').innerHTML = 
                    `<div class="error">Error: ${data.error}</div>`;
                return;
            }
            
            if (data.options.length === 0) {
                document.getElementById('results').innerHTML = 
                    '<p>No options data available.</p>';
                return;
            }
            
            let html = '<h3>Options Data:</h3>';
            html += '<table>';
            html += '<tr><th>Option</th><th>Last</th><th>Bid/Ask</th><th>Volume</th><th>Open Interest</th><th>OI Change</th><th>% Change</th><th>IV</th></tr>';
            
            data.options.forEach(opt => {
                const typeClass = opt.type === 'call' ? 'call' : 'put';
                const oiChangeClass = opt.oi_change > 0 ? 'positive' : opt.oi_change < 0 ? 'negative' : '';
                const date = new Date(opt.expiration);
                const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                
                html += '<tr>';
                html += `<td><strong>${opt.ticker}</strong> $${opt.strike} <span class="${typeClass}">${opt.type}</span> ${dateStr}</td>`;
                html += `<td>$${opt.last_price.toFixed(2)}</td>`;
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
        
        // Initialize
        document.getElementById('ticker').addEventListener('change', loadExpirations);
