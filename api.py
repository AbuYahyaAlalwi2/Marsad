from flask import Flask, request, jsonify
import os, time, random, requests
from datetime import datetime

app = Flask(__name__)

# Statistics
stats = {
    "emails": 0, "data": 0, "models": 0, "tasks": 0,
    "clouds": 30, "accounts": 90,
    "healthy": True, "start_time": time.time()
}

# Telegram
class Notifier:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
    
    def send(self, msg):
        if not self.enabled:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            requests.post(url, json={"chat_id": self.chat_id, "text": msg}, timeout=10)
            return True
        except:
            return False

notifier = Notifier()

@app.route('/')
def index():
    return jsonify({
        "status": "Marsad Running",
        "version": "4.0.0",
        "clouds": 30,
        "accounts": 90,
        "telegram": notifier.enabled
    })

@app.route('/api/status')
def status():
    return jsonify({
        "version": "4.0.0",
        "uptime": int(time.time() - stats["start_time"]),
        "stats": stats
    })

@app.route('/api/emails/create', methods=['POST'])
def create_emails():
    count = request.json.get('count', 5)
    for _ in range(count):
        stats["emails"] += 1
    return jsonify({"status": "success", "created": count, "total": stats["emails"]})

@app.route('/api/train', methods=['POST'])
def train():
    stats["models"] += 1
    time.sleep(2)
    notifier.send(f"✅ Model #{stats['models']} trained!")
    return jsonify({"status": "success", "model": f"marsad-v{stats['models']}"})

@app.route('/api/notify', methods=['POST'])
def notify():
    msg = request.json.get('message', 'Test')
    success = notifier.send(msg)
    return jsonify({"sent": success})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Marsad on port {port}")
    app.run(host='0.0.0.0', port=port)
