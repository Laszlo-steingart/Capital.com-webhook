from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import time
import base64
import pyotp

app = Flask(__name__)

# === Capital.com Zugangsdaten ===
API_KEY = "mV5fieaBA6qmRQBV"
API_USERNAME = "l.steingart@icloud.com"
API_PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

# === TOTP generieren ===
def get_totp(secret):
    totp = pyotp.TOTP(secret)
    return totp.now()

# === Capital.com Session aufbauen ===
def get_session():
    url = f"{BASE_URL}/api/v1/session"
    payload = {
        "identifier": API_USERNAME,
        "password": API_PASSWORD,
        "encrypted": False,
        "totpCode": get_totp(TOTP_SECRET)
    }

    headers = {
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return {
        "CST": response.headers.get("CST"),
        "X-SECURITY-TOKEN": response.headers.get("X-SECURITY-TOKEN")
    }

# === Order senden ===
def place_order(direction, epic, price, size):
    session = get_session()

    headers = {
        "X-CAP-API-KEY": API_KEY,
        "CST": session["CST"],
        "X-SECURITY-TOKEN": session["X-SECURITY-TOKEN"],
        "Content-Type": "application/json"
    }

    order_data = {
        "epic": epic,
        "direction": direction.upper(),
        "size": round(size, 2),
        "orderType": "MARKET",
        "currencyCode": "USD",
        "forceOpen": True,
        "guaranteedStop": False
    }

    response = requests.post(f"{BASE_URL}/api/v1/positions/otc", json=order_data, headers=headers)
    response.raise_for_status()
    return response.json()

# === Webhook Endpoint ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("Received Webhook:", data)

    try:
        action = data["action"]
        symbol = data["symbol"].replace("/", "")  # z.B. EURUSD
        price = float(data["price"])
        size = float(data["size"])

        # MAPPING zu einem echten Epic von Capital.com (Beispielhaft!)
        symbol_map = {
            "EURUSD": "CS.D.EURUSD.CFD.IP",
            "USDJPY": "CS.D.USDJPY.CFD.IP",
            # Füge weitere hinzu
        }

        epic = symbol_map.get(symbol.upper())
        if not epic:
            return jsonify({"status": "error", "message": f"Unbekanntes Symbol: {symbol}"}), 400

        result = place_order(action, epic, price, size)
        return jsonify({"status": "success", "details": result})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# === Startpunkt für lokale Tests (optional) ===
if __name__ == '__main__':
    app.run(port=5000, debug=True)

