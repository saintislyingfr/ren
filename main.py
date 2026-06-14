# main.py - Render RVG Gateway with Red/Black Theme
import os
import json
import uuid
import qrcode
import threading
import time
from datetime import datetime, timedelta
from io import BytesIO
import base64
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# Configuration
PORT = int(os.environ.get('PORT', 8080))
RENDER_PUBLIC_DOMAIN = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost:8080')
RENDER_PUBLIC_URL = f"https://{RENDER_PUBLIC_DOMAIN}" if 'onrender.com' in RENDER_PUBLIC_DOMAIN else f"http://{RENDER_PUBLIC_DOMAIN}"

# In-memory storage (will reset on restart)
links = {}
traffic_stats = {}
active_connections = {}

# Default VLESS config (you can modify this)
DEFAULT_VLESS_CONFIG = {
    "v": "2",
    "ps": "Render-Gateway-Default",
    "add": RENDER_PUBLIC_DOMAIN,
    "port": "443",
    "id": str(uuid.uuid4()),
    "aid": "0",
    "scy": "auto",
    "net": "ws",
    "type": "none",
    "host": RENDER_PUBLIC_DOMAIN,
    "path": "/vless",
    "tls": "tls"
}

# HTML Template with Red/Black Theme
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Render Gateway | VLESS Management Panel</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', 'Poppins', 'Courier New', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a0000 50%, #0a0505 100%);
            color: #ff3333;
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated Background */
        .bg-animation {
            position: fixed;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }

        .bg-animation::before {
            content: '';
            position: absolute;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,0,0,0.1) 1%, transparent 1%);
            background-size: 50px 50px;
            animation: bgMove 20s linear infinite;
        }

        @keyframes bgMove {
            0% { transform: translate(0, 0); }
            100% { transform: translate(50px, 50px); }
        }

        /* Glassmorphism Container */
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Header */
        .header {
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(10px);
            border-bottom: 3px solid #ff0000;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 0 30px rgba(255, 0, 0, 0.3);
            animation: glowPulse 2s infinite;
        }

        @keyframes glowPulse {
            0%, 100% { box-shadow: 0 0 20px rgba(255, 0, 0, 0.3); }
            50% { box-shadow: 0 0 40px rgba(255, 0, 0, 0.6); }
        }

        .header h1 {
            font-size: 2.5em;
            text-shadow: 0 0 10px #ff0000, 0 0 20px #ff0000;
            letter-spacing: 3px;
        }

        .header .badge {
            display: inline-block;
            background: #ff0000;
            color: #000;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin-top: 10px;
        }

        /* Stats Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: linear-gradient(135deg, rgba(0,0,0,0.8), rgba(30,0,0,0.8));
            backdrop-filter: blur(10px);
            border: 1px solid #ff0000;
            border-radius: 15px;
            padding: 20px;
            transition: transform 0.3s, box-shadow 0.3s;
            animation: slideIn 0.5s ease-out;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(255, 0, 0, 0.3);
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .stat-card h3 {
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #ff6666;
            margin-bottom: 10px;
        }

        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            color: #ff0000;
            text-shadow: 0 0 5px #ff0000;
        }

        /* Tables & Cards */
        .section {
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(10px);
            border: 1px solid #ff0000;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
        }

        .section-title {
            font-size: 1.8em;
            border-left: 5px solid #ff0000;
            padding-left: 15px;
            margin-bottom: 20px;
            text-shadow: 0 0 5px #ff0000;
        }

        .link-table {
            width: 100%;
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #330000;
        }

        th {
            background: rgba(255, 0, 0, 0.2);
            color: #ff6666;
            font-weight: bold;
        }

        tr:hover {
            background: rgba(255, 0, 0, 0.1);
        }

        /* Buttons */
        .btn {
            background: linear-gradient(135deg, #ff0000, #990000);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.2s, box-shadow 0.2s;
            margin: 5px;
        }

        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 0 15px rgba(255, 0, 0, 0.5);
        }

        .btn-danger {
            background: linear-gradient(135deg, #660000, #330000);
        }

        .btn-success {
            background: linear-gradient(135deg, #00cc00, #006600);
        }

        .btn-info {
            background: linear-gradient(135deg, #0066cc, #003366);
        }

        /* Form */
        .form-group {
            margin-bottom: 15px;
        }

        input, select {
            width: 100%;
            padding: 10px;
            background: rgba(0, 0, 0, 0.7);
            border: 1px solid #ff0000;
            color: #ff3333;
            border-radius: 5px;
            font-size: 1em;
        }

        input:focus, select:focus {
            outline: none;
            border-color: #ff6666;
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.3);
        }

        /* Modal */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            backdrop-filter: blur(5px);
        }

        .modal-content {
            background: linear-gradient(135deg, #1a0000, #0a0000);
            margin: 5% auto;
            padding: 30px;
            border: 2px solid #ff0000;
            border-radius: 20px;
            width: 90%;
            max-width: 500px;
            text-align: center;
            animation: modalSlide 0.3s ease-out;
        }

        @keyframes modalSlide {
            from {
                transform: translateY(-100px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .close {
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            color: #ff0000;
        }

        .close:hover {
            color: #ff6666;
        }

        /* QR Code */
        .qrcode {
            margin: 20px auto;
            padding: 20px;
            background: white;
            display: inline-block;
            border-radius: 10px;
        }

        /* Alerts */
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
            animation: fadeIn 0.3s;
        }

        .alert-success {
            background: rgba(0, 255, 0, 0.2);
            border: 1px solid #00ff00;
            color: #00ff00;
        }

        .alert-error {
            background: rgba(255, 0, 0, 0.2);
            border: 1px solid #ff0000;
            color: #ff6666;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        /* Responsive */
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            th, td {
                font-size: 0.8em;
                padding: 8px;
            }
            
            .section-title {
                font-size: 1.3em;
            }
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }

        ::-webkit-scrollbar-track {
            background: #1a0000;
        }

        ::-webkit-scrollbar-thumb {
            background: #ff0000;
            border-radius: 5px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #ff6666;
        }

        /* Loading Animation */
        .loader {
            border: 3px solid #330000;
            border-top: 3px solid #ff0000;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            display: inline-block;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="bg-animation"></div>
    
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>⚡ RENDER GATEWAY</h1>
            <div class="badge">VLESS + WebSocket | Premium Tunnel</div>
            <div style="margin-top: 10px; font-size: 0.9em; color: #ff6666;">
                🔥 Deployed on Render.com | Red/Black Edition
            </div>
        </div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📊 Total Links</h3>
                <div class="value" id="totalLinks">0</div>
            </div>
            <div class="stat-card">
                <h3>📈 Active Links</h3>
                <div class="value" id="activeLinks">0</div>
            </div>
            <div class="stat-card">
                <h3>📡 Total Traffic</h3>
                <div class="value" id="totalTraffic">0 MB</div>
            </div>
            <div class="stat-card">
                <h3>🟢 Active Connections</h3>
                <div class="value" id="activeConns">0</div>
            </div>
        </div>

        <!-- Create Link Form -->
        <div class="section">
            <div class="section-title">🔗 Create New Link</div>
            <div style="display: grid; grid-template-columns: 1fr auto auto auto; gap: 10px; align-items: end;">
                <div class="form-group">
                    <label>Link Name:</label>
                    <input type="text" id="linkName" placeholder="e.g., My Server Link">
                </div>
                <div class="form-group">
                    <label>Traffic Limit (MB):</label>
                    <input type="number" id="trafficLimit" placeholder="0 = unlimited" value="0">
                </div>
                <div class="form-group">
                    <label>Expiry (days):</label>
                    <input type="number" id="expiryDays" placeholder="0 = never" value="30">
                </div>
                <div>
                    <button class="btn" onclick="createLink()">🚀 CREATE LINK</button>
                </div>
            </div>
        </div>

        <!-- Links Table -->
        <div class="section">
            <div class="section-title">📋 Active Links</div>
            <div class="link-table">
                <table id="linksTable">
                    <thead>
                        <tr><th>Name</th><th>Link ID</th><th>Traffic Used</th><th>Traffic Limit</th><th>Status</th><th>Created</th><th>Expires</th><th>Actions</th></tr>
                    </thead>
                    <tbody id="linksBody">
                        <tr><td colspan="8" style="text-align: center;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- QR Code Modal -->
    <div id="qrModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2>📱 QR Code</h2>
            <div id="qrcodeContainer"></div>
            <div id="vlessLink" style="margin: 15px; word-break: break-all;"></div>
            <button class="btn" onclick="copyLink()">📋 Copy Link</button>
        </div>
    </div>

    <script>
        let currentLink = '';
        
        // Fetch stats and links
        async function fetchData() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                document.getElementById('totalLinks').textContent = data.total_links;
                document.getElementById('activeLinks').textContent = data.active_links;
                document.getElementById('totalTraffic').textContent = data.total_traffic + ' MB';
                document.getElementById('activeConns').textContent = data.active_connections;
                
                const linksResponse = await fetch('/api/links');
                const links = await linksResponse.json();
                renderLinks(links);
            } catch(e) {
                console.error('Error fetching data:', e);
            }
        }
        
        function renderLinks(links) {
            const tbody = document.getElementById('linksBody');
            if (links.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No links created yet</td></tr>';
                return;
            }
            
            tbody.innerHTML = links.map(link => `
                <tr>
                    <td>${escapeHtml(link.name)}</td>
                    <td><code>${link.id.substring(0, 8)}...</code></td>
                    <td>${link.traffic_used} MB</td>
                    <td>${link.traffic_limit === 0 ? '∞' : link.traffic_limit + ' MB'}</td>
                    <td>${link.active ? '<span style="color: #00ff00;">✅ Active</span>' : '<span style="color: #ff0000;">❌ Disabled</span>'}</td>
                    <td>${new Date(link.created_at).toLocaleDateString()}</td>
                    <td>${link.expires_at ? new Date(link.expires_at).toLocaleDateString() : 'Never'}</td>
                    <td>
                        <button class="btn btn-info" onclick="showQR('${link.id}')">📱 QR</button>
                        <button class="btn ${link.active ? 'btn-danger' : 'btn-success'}" onclick="toggleLink('${link.id}')">
                            ${link.active ? '🔴 Disable' : '🟢 Enable'}
                        </button>
                        <button class="btn btn-danger" onclick="deleteLink('${link.id}')">🗑️ Delete</button>
                    </td>
                </tr>
            `).join('');
        }
        
        async function createLink() {
            const name = document.getElementById('linkName').value;
            const trafficLimit = parseInt(document.getElementById('trafficLimit').value);
            const expiryDays = parseInt(document.getElementById('expiryDays').value);
            
            if (!name) {
                alert('Please enter a link name');
                return;
            }
            
            const response = await fetch('/api/links', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, traffic_limit: trafficLimit, expiry_days: expiryDays})
            });
            
            if (response.ok) {
                document.getElementById('linkName').value = '';
                document.getElementById('trafficLimit').value = '0';
                document.getElementById('expiryDays').value = '30';
                fetchData();
                showAlert('Link created successfully!', 'success');
            }
        }
        
        async function toggleLink(linkId) {
            const response = await fetch(`/api/links/${linkId}/toggle`, {method: 'POST'});
            if (response.ok) {
                fetchData();
                showAlert('Link status toggled', 'success');
            }
        }
        
        async function deleteLink(linkId) {
            if (confirm('Are you sure you want to delete this link?')) {
                const response = await fetch(`/api/links/${linkId}`, {method: 'DELETE'});
                if (response.ok) {
                    fetchData();
                    showAlert('Link deleted', 'success');
                }
            }
        }
        
        async function showQR(linkId) {
            const response = await fetch(`/api/links/${linkId}/vless`);
            const data = await response.json();
            currentLink = data.vless_link;
            
            document.getElementById('vlessLink').innerHTML = `<strong>VLESS Link:</strong><br>${currentLink.substring(0, 100)}...`;
            document.getElementById('qrcodeContainer').innerHTML = `<img src="${data.qr_code}" class="qrcode">`;
            document.getElementById('qrModal').style.display = 'block';
        }
        
        function copyLink() {
            navigator.clipboard.writeText(currentLink);
            alert('Link copied to clipboard!');
        }
        
        function closeModal() {
            document.getElementById('qrModal').style.display = 'none';
        }
        
        function showAlert(message, type) {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type}`;
            alertDiv.innerHTML = message;
            alertDiv.style.position = 'fixed';
            alertDiv.style.top = '20px';
            alertDiv.style.right = '20px';
            alertDiv.style.zIndex = '10000';
            document.body.appendChild(alertDiv);
            setTimeout(() => alertDiv.remove(), 3000);
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Auto-refresh every 5 seconds
        setInterval(fetchData, 5000);
        fetchData();
        
        // Close modal on outside click
        window.onclick = function(event) {
            const modal = document.getElementById('qrModal');
            if (event.target === modal) {
                closeModal();
            }
        }
    </script>
</body>
</html>
"""

# API Routes
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/dashboard')
def dashboard():
    return redirect('/')

@app.route('/api/stats')
def get_stats():
    return jsonify({
        'total_links': len(links),
        'active_links': sum(1 for l in links.values() if l.get('active', True)),
        'total_traffic': round(sum(traffic_stats.values()), 2),
        'active_connections': len(active_connections)
    })

@app.route('/api/links')
def get_links():
    links_list = []
    for link_id, link_data in links.items():
        # Check expiry
        if link_data.get('expires_at') and datetime.now() > datetime.fromisoformat(link_data['expires_at']):
            link_data['active'] = False
        
        links_list.append({
            'id': link_id,
            'name': link_data['name'],
            'traffic_used': round(link_data.get('traffic_used', 0), 2),
            'traffic_limit': link_data.get('traffic_limit', 0),
            'active': link_data.get('active', True),
            'created_at': link_data.get('created_at', datetime.now().isoformat()),
            'expires_at': link_data.get('expires_at')
        })
    return jsonify(links_list)

@app.route('/api/links', methods=['POST'])
def create_link():
    data = request.json
    link_id = str(uuid.uuid4())
    
    expiry_date = None
    if data.get('expiry_days', 0) > 0:
        expiry_date = (datetime.now() + timedelta(days=data['expiry_days'])).isoformat()
    
    links[link_id] = {
        'name': data['name'],
        'traffic_limit': data.get('traffic_limit', 0),
        'traffic_used': 0,
        'active': True,
        'created_at': datetime.now().isoformat(),
        'expires_at': expiry_date
    }
    
    return jsonify({'id': link_id, 'message': 'Link created successfully'})

@app.route('/api/links/<link_id>/toggle', methods=['POST'])
def toggle_link(link_id):
    if link_id in links:
        links[link_id]['active'] = not links[link_id].get('active', True)
        return jsonify({'message': 'Link toggled successfully'})
    return jsonify({'error': 'Link not found'}), 404

@app.route('/api/links/<link_id>', methods=['DELETE'])
def delete_link(link_id):
    if link_id in links:
        del links[link_id]
        return jsonify({'message': 'Link deleted successfully'})
    return jsonify({'error': 'Link not found'}), 404

@app.route('/api/links/<link_id>/vless')
def get_vless_link(link_id):
    if link_id not in links:
        return jsonify({'error': 'Link not found'}), 404
    
    # Generate VLESS config
    config = DEFAULT_VLESS_CONFIG.copy()
    config['ps'] = links[link_id]['name']
    config['id'] = link_id
    
    # Build VLESS link
    vless_link = f"vless://{config['id']}@{config['add']}:{config['port']}?encryption=none&security=tls&sni={config['host']}&type=ws&host={config['host']}&path={config['path']}#{config['ps']}"
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(vless_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        'vless_link': vless_link,
        'qr_code': f'data:image/png;base64,{qr_base64}'
    })

if __name__ == '__main__':
    print(f"""
    ╔═══════════════════════════════════════════════════════╗
    ║     🔥 RENDER GATEWAY - RED/BLACK EDITION 🔥          ║
    ║                                                       ║
    ║     🚀 Server running on port: {PORT}                  ║
    ║     🌐 Access at: {RENDER_PUBLIC_URL}                  ║
    ║     📊 Dashboard: {RENDER_PUBLIC_URL}/dashboard        ║
    ║                                                       ║
    ║     ⚡ VLESS + WebSocket Gateway Active              ║
    ║     🎨 Red/Black Theme by Codebox                    ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=PORT, debug=False)