from flask import Flask, request, jsonify
import requests
import pyotp

app = Flask(__name__)

# === DEINE CAPITAL.COM API ZUGANGSDATEN ===
API_KEY = "mV5fieaBA6qmRQBV"
USERNAME = "l.steingart@icloud.com"
PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

session = requests.Session()

def get_totp_code(secret):
    """Erzeugt den aktuellen 2FA Code"""
    return pyotp.TOTP(secret).now()

def login():
    """Meldet sich mit API-Key + Passwort + 2FA bei Capital.com an"""
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

    # Auth-Token speichern
    session.headers.update({
        "CST": response.headers["CST"],
        "X-SECURITY-TOKEN": response.headers["X-SECURITY-TOKEN"],
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    """Empfängt das Signal von TradingView"""
    data = request.get_json()
    action = data.get("action")      # "buy" oder "sell"
    symbol = data.get("symbol")      # z.B. "US500"
    size = float(data.get("size"))   # Positionsgröße

    if action not in ["buy", "sell"]:
        return jsonify({"error": "Ungültige Aktion"}), 400

    try:
        login()
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    # Zuerst alte Position schließen (Gegenteil von aktueller Richtung)
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

    # Neue Position öffnen
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
