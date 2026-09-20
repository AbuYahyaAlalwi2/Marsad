from flask import Flask, jsonify

class Dashboard:
    def __init__(self, port=5000):
        self.port = port
        self.app = Flask(__name__)
        
        @self.app.route("/")
        def index():
            return jsonify({"status": "Marsad Dashboard"})
    
    def run(self):
        self.app.run(host="0.0.0.0", port=self.port)
