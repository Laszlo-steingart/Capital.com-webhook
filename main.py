from flask import Flask, request, jsonify
import requests, pyotp

app = Flask(__name__)

# --- Capital.com Zugangsdaten ---
API_KEY = "mV5fieaBA6qmRQBV"
USERNAME = "l.steingart@icloud.com"
PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

# Nutze Session für Cookies, Token usw.
session = requests.Session()

def get_totp_code(secret):
    """Erzeuge 2FA Code (gültig 30 Sekunden)"""
    return pyotp.TOTP(secret).now()

def login():
    """Meldet dich bei Capital.com API mit 2FA an"""
    code = get_totp_code(TOTP_SECRET)
    payload = {
        "identifier": USERNAME,
        "password": PASSWORD,
        "encrypted": False,
        "2FA_CODE": code
    }
    headers = {
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    r = session.post(f"{BASE_URL}/api/v1/session", json=payload, headers=headers)
    if r.status_code != 200:
        raise Exception(f"Login fehlgeschlagen: {r.text}")
    session.headers.update({
        "CST": r.headers["CST"],
        "X-SECURITY-TOKEN": r.headers["X-SECURITY-TOKEN"],
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    })

@app.route("/", methods=["POST"])
def webhook():
    """Empfängt das Webhook von TradingView"""
    data = request.get_json()
    action = data.get("action")  # "buy" oder "sell"
    symbol = data.get("symbol")  # Ticker z. B. "AAPL"
    size = float(data.get("size"))

    if action not in ["buy", "sell"]:
        return jsonify({"error": "Ungültige Aktion"}), 400

    try:
        login()
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    # Bestehende Position schließen
    opposite = "SELL" if action == "buy" else "BUY"
    session.post(f"{BASE_URL}/api/v1/positions/otc", json={
        "epic": symbol,
        "direction": opposite,
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "forceOpen": False,
        "currencyCode": "USD"
    })

    # Neue Position öffnen
    r = session.post(f"{BASE_URL}/api/v1/positions/otc", json={
        "epic": symbol,
        "direction": action.upper(),
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "forceOpen": True,
        "currencyCode": "USD"
    })

    if r.status_code == 200:
        return jsonify({"status": "Trade erfolgreich"}), 200
    else:
        return jsonify({"error": r.text}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
