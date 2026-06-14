# main.py - Render RVG Gateway (No Pillow dependency)
import os
import json
import uuid
import threading
import time
from datetime import datetime, timedelta
from io import BytesIO
import base64
from flask import Flask, request, jsonify, render_template_string, redirect, url_for

# Try to import qrcode with PIL, but provide fallback
try:
    import qrcode
    from qrcode.image.pil import PilImage
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    print("Warning: qrcode with PIL not available, QR codes will use API")

app = Flask(__name__)

# Configuration
PORT = int(os.environ.get('PORT', 8080))
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
RENDER_PUBLIC_URL = f"https://{RENDER_EXTERNAL_HOSTNAME}" if 'onrender.com' in RENDER_EXTERNAL_HOSTNAME else f"http://{RENDER_EXTERNAL_HOSTNAME}:{PORT}"

# In-memory storage
links = {}
traffic_stats = {}
active_connections = {}

# Default VLESS config
DEFAULT_VLESS_CONFIG = {
    "v": "2",
    "ps": "Render-Gateway-Default",
    "add": RENDER_EXTERNAL_HOSTNAME,
    "port": "443",
    "id": str(uuid.uuid4()),
    "aid": "0",
    "scy": "auto",
    "net": "ws",
    "type": "none",
    "host": RENDER_EXTERNAL_HOSTNAME,
    "path": "/vless",
    "tls": "tls"
}

# HTML Template (same as before, but with QR code fallback)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Render Gateway | VLESS Management Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a0000 50%, #0a0505 100%);
            color: #ff3333;
            min-height: 100vh;
        }
        .bg-ananimation {
            position: fixed;
            width: 100%;
            height: 100%;
            z-index: -1;
            background: radial-gradient(circle, rgba(255,0,0,0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            animation: bgMove 20s linear infinite;
        }
        @keyframes bgMove {
            0% { transform: translate(0, 0); }
            100% { transform: translate(30px, 30px); }
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header {
            background: rgba(0,0,0,0.85);
            backdrop-filter: blur(10px);
            border-bottom: 3px solid #ff0000;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 0 30px rgba(255,0,0,0.3);
            animation: glowPulse 2s infinite;
        }
        @keyframes glowPulse {
            0%,100% { box-shadow: 0 0 20px rgba(255,0,0,0.3); }
            50% { box-shadow: 0 0 40px rgba(255,0,0,0.6); }
        }
        .header h1 { font-size: 2.5em; text-shadow: 0 0 10px #ff0000; letter-spacing: 3px; }
        .badge { display: inline-block; background: #ff0000; color: #000; padding: 5px 15px; border-radius: 20px; font-weight: bold; margin-top: 10px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px,1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card {
            background: linear-gradient(135deg, rgba(0,0,0,0.8), rgba(30,0,0,0.8));
            backdrop-filter: blur(10px);
            border: 1px solid #ff0000;
            border-radius: 15px;
            padding: 20px;
            transition: transform 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); box-shadow: 0 10px 30px rgba(255,0,0,0.3); }
        .stat-card h3 { font-size: 0.9em; text-transform: uppercase; color: #ff6666; margin-bottom: 10px; }
        .stat-card .value { font-size: 2.5em; font-weight: bold; color: #ff0000; text-shadow: 0 0 5px #ff0000; }
        .section {
            background: rgba(0,0,0,0.75);
            backdrop-filter: blur(10px);
            border: 1px solid #ff0000;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
        }
        .section-title { font-size: 1.8em; border-left: 5px solid #ff0000; padding-left: 15px; margin-bottom: 20px; }
        .link-table { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #330000; }
        th { background: rgba(255,0,0,0.2); color: #ff6666; }
        tr:hover { background: rgba(255,0,0,0.1); }
        .btn {
            background: linear-gradient(135deg, #ff0000, #990000);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.2s;
            margin: 5px;
        }
        .btn:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(255,0,0,0.5); }
        .btn-danger { background: linear-gradient(135deg, #660000, #330000); }
        .btn-success { background: linear-gradient(135deg, #00cc00, #006600); }
        .btn-info { background: linear-gradient(135deg, #0066cc, #003366); }
        .form-group { margin-bottom: 15px; }
        input, select {
            width: 100%;
            padding: 10px;
            background: rgba(0,0,0,0.7);
            border: 1px solid #ff0000;
            color: #ff3333;
            border-radius: 5px;
        }
        input:focus { outline: none; border-color: #ff6666; box-shadow: 0 0 10px rgba(255,0,0,0.3); }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
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
        }
        .close { float: right; font-size: 28px; cursor: pointer; color: #ff0000; }
        .qrcode { margin: 20px auto; padding: 20px; background: white; display: inline-block; border-radius: 10px; }
        .alert { padding: 12px; border-radius: 8px; margin-bottom: 15px; position: fixed; top: 20px; right: 20px; z-index: 10000; }
        .alert-success { background: rgba(0,255,0,0.2); border: 1px solid #00ff00; color: #00ff00; }
        @media (max-width: 768px) { th, td { font-size: 0.8em; padding: 8px; } .section-title { font-size: 1.3em; } }
        ::-webkit-scrollbar { width: 10px; }
        ::-webkit-scrollbar-track { background: #1a0000; }
        ::-webkit-scrollbar-thumb { background: #ff0000; border-radius: 5px; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
</head>
<body>
    <div class="bg-ananimation"></div>
    <div class="container">
        <div class="header">
            <h1>⚡ RENDER GATEWAY</h1>
            <div class="badge">VLESS + WebSocket | Premium Tunnel</div>
            <div style="margin-top: 10px; color: #ff6666;">🔥 Deployed on Render.com | Red/Black Edition</div>
        </div>
        <div class="stats-grid">
            <div class="stat-card"><h3>📊 Total Links</h3><div class="value" id="totalLinks">0</div></div>
            <div class="stat-card"><h3>📈 Active Links</h3><div class="value" id="activeLinks">0</div></div>
            <div class="stat-card"><h3>📡 Total Traffic</h3><div class="value" id="totalTraffic">0 MB</div></div>
            <div class="stat-card"><h3>🟢 Active Connections</h3><div class="value" id="activeConns">0</div></div>
        </div>
        <div class="section">
            <div class="section-title">🔗 Create New Link</div>
            <div style="display: grid; grid-template-columns: 1fr auto auto auto; gap: 10px; align-items: end;">
                <div class="form-group"><label>Link Name:</label><input type="text" id="linkName" placeholder="e.g., My Server Link"></div>
                <div class="form-group"><label>Traffic Limit (MB):</label><input type="number" id="trafficLimit" value="0"></div>
                <div class="form-group"><label>Expiry (days):</label><input type="number" id="expiryDays" value="30"></div>
                <div><button class="btn" onclick="createLink()">🚀 CREATE LINK</button></div>
            </div>
        </div>
        <div class="section">
            <div class="section-title">📋 Active Links</div>
            <div class="link-table">
                <table>
                    <thead><tr><th>Name</th><th>Link ID</th><th>Traffic Used</th><th>Traffic Limit</th><th>Status</th><th>Created</th><th>Expires</th><th>Actions</th></tr></thead>
                    <tbody id="linksBody"><tr><td colspan="8" style="text-align: center;">Loading...</td></tr></tbody>
                </table>
            </div>
        </div>
    </div>
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
        async function fetchData() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('totalLinks').textContent = data.total_links;
                document.getElementById('activeLinks').textContent = data.active_links;
                document.getElementById('totalTraffic').textContent = data.total_traffic + ' MB';
                document.getElementById('activeConns').textContent = data.active_connections;
                const linksRes = await fetch('/api/links');
                const links = await linksRes.json();
                renderLinks(links);
            } catch(e) { console.error(e); }
        }
        function renderLinks(links) {
            const tbody = document.getElementById('linksBody');
            if(links.length===0){ tbody.innerHTML='<tr><td colspan="8" style="text-align: center;">No links created yet</td></tr>'; return; }
            tbody.innerHTML = links.map(l => `<tr>
                <td>${escapeHtml(l.name)}</td>
                <td><code>${l.id.substring(0,8)}...</code></td>
                <td>${l.traffic_used} MB</td>
                <td>${l.traffic_limit===0?'∞':l.traffic_limit+' MB'}</td>
                <td>${l.active?'<span style="color:#00ff00;">✅ Active</span>':'<span style="color:#ff0000;">❌ Disabled</span>'}</td>
                <td>${new Date(l.created_at).toLocaleDateString()}</td>
                <td>${l.expires_at?new Date(l.expires_at).toLocaleDateString():'Never'}</td>
                <td>
                    <button class="btn btn-info" onclick="showQR('${l.id}')">📱 QR</button>
                    <button class="btn ${l.active?'btn-danger':'btn-success'}" onclick="toggleLink('${l.id}')">${l.active?'🔴 Disable':'🟢 Enable'}</button>
                    <button class="btn btn-danger" onclick="deleteLink('${l.id}')">🗑️ Delete</button>
                </td>
            </tr>`).join('');
        }
        async function createLink() {
            const name = document.getElementById('linkName').value;
            const trafficLimit = parseInt(document.getElementById('trafficLimit').value);
            const expiryDays = parseInt(document.getElementById('expiryDays').value);
            if(!name){ alert('Enter link name'); return; }
            const res = await fetch('/api/links', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,traffic_limit:trafficLimit,expiry_days:expiryDays})});
            if(res.ok){
                document.getElementById('linkName').value='';
                fetchData();
                showAlert('Link created!','success');
            }
        }
        async function toggleLink(id){ await fetch(`/api/links/${id}/toggle`,{method:'POST'}); fetchData(); }
        async function deleteLink(id){ if(confirm('Delete?')){ await fetch(`/api/links/${id}`,{method:'DELETE'}); fetchData(); } }
        async function showQR(id){
            const res = await fetch(`/api/links/${id}/vless`);
            const data = await res.json();
            currentLink = data.vless_link;
            document.getElementById('vlessLink').innerHTML = `<strong>VLESS Link:</strong><br>${currentLink.substring(0,100)}...`;
            document.getElementById('qrcodeContainer').innerHTML = `<div id="qrcode"></div>`;
            new QRCode(document.getElementById("qrcode"), { text: currentLink, width: 200, height: 200 });
            document.getElementById('qrModal').style.display = 'block';
        }
        function copyLink(){ navigator.clipboard.writeText(currentLink); alert('Copied!'); }
        function closeModal(){ document.getElementById('qrModal').style.display = 'none'; }
        function showAlert(msg,type){ const d=document.createElement('div'); d.className=`alert alert-${type}`; d.innerHTML=msg; document.body.appendChild(d); setTimeout(()=>d.remove(),3000); }
        function escapeHtml(t){ const d=document.createElement('div'); d.textContent=t; return d.innerHTML; }
        setInterval(fetchData,5000);
        fetchData();
        window.onclick = function(e){ if(e.target===document.getElementById('qrModal')) closeModal(); }
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
    config = DEFAULT_VLESS_CONFIG.copy()
    config['ps'] = links[link_id]['name']
    config['id'] = link_id
    vless_link = f"vless://{config['id']}@{config['add']}:{config['port']}?encryption=none&security=tls&sni={config['host']}&type=ws&host={config['host']}&path={config['path']}#{config['ps']}"
    return jsonify({'vless_link': vless_link, 'qr_code': ''})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print(f"""
    ╔═══════════════════════════════════════════════════════╗
    ║     🔥 RENDER GATEWAY - RED/BLACK EDITION 🔥          ║
    ║     🚀 Server running on port: {PORT}                  ║
    ║     🌐 Access at: {RENDER_PUBLIC_URL}                  ║
    ║     📊 Dashboard: {RENDER_PUBLIC_URL}/dashboard        ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=PORT, debug=False)