"""Small Flask API exposing real state and manual onboarding only."""
import os
import sqlite3
from flask import Flask, jsonify, request

from manual_onboarding import onboarding_status, save_account
from manual_provider_registry import list_supported_providers, provider_status

app = Flask(__name__)
DB_PATH = os.environ.get("CG_DB_PATH", "data/cyberguard.db")


def agent_count():
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT COUNT(*) FROM agents").fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except (OSError, sqlite3.Error):
        return None


@app.get("/")
def index():
    return jsonify({"status": "online", "mode": "manual_only"})


@app.get("/api/status")
def status():
    return jsonify({
        "status": "online",
        "mode": "manual_only",
        "agents": agent_count(),
        "providers": len(list_supported_providers()),
    })


@app.get("/api/providers")
def providers():
    return jsonify({name: provider_status(name) for name in list_supported_providers()})


@app.get("/api/onboarding")
def onboarding():
    return jsonify(onboarding_status())


@app.post("/api/onboarding")
def record_onboarding():
    payload = request.get_json(silent=True) or {}
    return jsonify(save_account(
        payload.get("provider", ""),
        payload.get("email", ""),
        payload.get("account_url", ""),
        payload.get("notes", ""),
    )), 201


@app.post("/api/emails/create")
def no_email_creation():
    return jsonify({
        "status": "disabled",
        "reason": "automated_email_creation_disabled",
        "message": "استخدم بريدًا حقيقيًا مملوكًا لك وسجله يدويًا.",
    }), 403


@app.get("/api/logs")
def logs():
    return jsonify({"status": "not_configured", "logs": []})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
