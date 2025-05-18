from flask import Flask, request, jsonify
import requests
import pyotp
import os  # NEU: Für dynamischen Port bei Render

app = Flask(__name__)

# === DEINE CAPITAL.COM API-ZUGANGSDATEN ===
API_KEY = "mV5fieaBA6qmRQBV"
USERNAME = "l.steingart@icloud.com"
PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

session = requests.Session()

def get_totp_code(secret):
    """Erzeuge den aktuellen TOTP 2FA-Code"""
    return pyotp.TOTP(secret).now()

def login():
    """Logge dich bei Capital.com API ein (inkl. 2FA)"""
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

    response = session.post(f"{BASE_URL}/api/v1/session", json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Login fehlgeschlagen: {response.text}")

    # Tokens setzen
    session.headers.update({
        "CST": response.headers["CST"],
        "X-SECURITY-TOKEN": response.headers["X-SECURITY-TOKEN"],
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    """Empfängt Webhook von TradingView"""
    data = request.get_json()
    action = data.get("action")
    symbol = data.get("symbol")
    size = float(data.get("size"))

    if action not in ["buy", "sell"]:
        return jsonify({"error": "Ungültige Aktion"}), 400

    try:
        login()
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    # Alte Position schließen
    opposite = "SELL" if action == "buy" else "BUY"
    close_payload = {
        "epic": symbol,
        "direction": opposite,
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "forceOpen": False,
        "currencyCode": "USD"
    }
    session.post(f"{BASE_URL}/api/v1/positions/otc", json=close_payload)

    # Neue Position eröffnen
    open_payload = {
        "epic": symbol,
        "direction": action.upper(),
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "forceOpen": True,
        "currencyCode": "USD"
    }
    response = session.post(f"{BASE_URL}/api/v1/positions/otc", json=open_payload)

    if response.status_code == 200:
        return jsonify({"status": "Trade erfolgreich"}), 200
    else:
        return jsonify({"error": response.text}), 400

# === Render braucht dynamischen Port ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
