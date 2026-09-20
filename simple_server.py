from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"status": "Simple server running"})

@app.route('/api/agents/deploy', methods=['POST'])
def deploy_agents():
    count = request.json.get('count', 100)
    cloud = request.json.get('cloud', 'auto')
    
    return jsonify({
        "status": "success",
        "deployed": count,
        "cloud": cloud
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

# ═══════════════════════════════════════════════════════════════
# ADD ALL ENDPOINTS
# ═══════════════════════════════════════════════════════════════

import sqlite3
import time
import random
import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_db():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect('data/marsad.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    os.makedirs('data', exist_ok=True)
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id SERIAL PRIMARY KEY,
                agent_id TEXT UNIQUE,
                cloud_provider TEXT,
                status TEXT DEFAULT 'active',
                created_at REAL
            )
        """)
        conn.commit()
        cur.close()
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY,
                agent_id TEXT UNIQUE,
                cloud_provider TEXT,
                status TEXT DEFAULT 'active',
                created_at REAL
            )
        """)
        conn.commit()
    conn.close()

init_db()

@app.route('/api/status')
def status():
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM agents")
        count = cur.fetchone()[0]
        cur.close()
    else:
        count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    conn.close()
    
    return jsonify({
        "status": "online",
        "agents": count,
        "mode": "REAL"
    })

@app.route('/api/logs')
def logs():
    return jsonify({"logs": [{"time": "now", "msg": "System running"}]})

@app.route('/api/emails/create', methods=['POST'])
def create_email():
    return jsonify({"status": "success", "email": f"test_{int(time.time())}@example.com"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

# ═══════════════════════════════════════════════════════════════
# LIBRARY INTEGRATION
# ═══════════════════════════════════════════════════════════════

import sys
sys.path.insert(0, '.')

@app.route('/api/workflow/run', methods=['POST'])
def run_workflow():
    from marsad import Workflow
    wf = Workflow(num_workers=5)
    result = wf.run_full_workflow()
    return jsonify(result)

@app.route('/api/swarm/deploy', methods=['POST'])
def deploy_swarm():
    from marsad import AgentSwarm
    count = request.json.get('count', 1000000)
    swarm = AgentSwarm(count=count)
    return jsonify(swarm.deploy())

@app.route('/api/ip/rotate', methods=['POST'])
def rotate_ip():
    from marsad import SmartRequest
    smart = SmartRequest()
    smart.rotator.rotate_ip()
    return jsonify({"status": "rotated", "ip": smart.rotator.get_current_ip()})

@app.route('/api/vault/keys', methods=['GET'])
def list_keys():
    from marsad import KeyVault
    vault = KeyVault()
    return jsonify({"platforms": vault.list_platforms()})
