from flask import Flask, request, jsonify
import requests
import pyotp
import os

app = Flask(__name__)

# === Zugangsdaten ===
API_KEY = "mV5fieaBA6qmRQBV"
API_USERNAME = "l.steingart@icloud.com"
API_PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

def get_totp(secret):
    totp = pyotp.TOTP(secret)
    return totp.now()

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

def get_open_positions(session):
    headers = {
        "X-CAP-API-KEY": API_KEY,
        "CST": session["CST"],
        "X-SECURITY-TOKEN": session["X-SECURITY-TOKEN"]
    }
    r = requests.get(f"{BASE_URL}/api/v1/positions", headers=headers)
    r.raise_for_status()
    return r.json()["positions"]

def close_position(session, deal_id, direction, size):
    close_dir = "SELL" if direction.upper() == "BUY" else "BUY"
    headers = {
        "X-CAP-API-KEY": API_KEY,
        "CST": session["CST"],
        "X-SECURITY-TOKEN": session["X-SECURITY-TOKEN"],
        "Content-Type": "application/json"
    }
    payload = {
        "dealId": deal_id,
        "size": size,
        "direction": close_dir,
        "orderType": "MARKET"
    }
    r = requests.post(f"{BASE_URL}/api/v1/positions/otc/close", json=payload, headers=headers)
    r.raise_for_status()
    print("🛑 Alte Position geschlossen")

def close_opposite_positions(session, epic, new_dir):
    positions = get_open_positions(session)
    for pos in positions:
        p = pos["position"]
        if p["epic"] == epic and p["direction"].lower() != new_dir.lower():
            close_position(session, p["dealId"], p["direction"], float(p["size"]))

def place_order(session, direction, epic, size):
    headers = {
        "X-CAP-API-KEY": API_KEY,
        "CST": session["CST"],
        "X-SECURITY-TOKEN": session["X-SECURITY-TOKEN"],
        "Content-Type": "application/json"
    }
    payload = {
        "epic": epic,
        "direction": direction.upper(),
        "size": round(size, 2),
        "orderType": "MARKET",
        "currencyCode": "USD",
        "forceOpen": True,
        "guaranteedStop": False
    }
    r = requests.post(f"{BASE_URL}/api/v1/positions/otc", json=payload, headers=headers)
    r.raise_for_status()
    print("✅ Neue Position geöffnet")
    return r.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print("📩 Webhook empfangen:", data)

        if not data:
            return jsonify({"error": "Kein oder ungültiges JSON"}), 400

        action = data.get("action")
        symbol = data.get("symbol", "").replace("/", "")
        price = float(data.get("price", 0))
        size = float(data.get("size", 0))

        if not all([action, symbol, price, size]):
            return jsonify({"error": "Fehlende Felder"}), 400

        symbol_map = {
            "EURUSD": "CS.D.EURUSD.CFD.IP"
        }

        epic = symbol_map.get(symbol.upper())
        if not epic:
            return jsonify({"error": f"Unbekanntes Symbol: {symbol}"}), 400

        session = get_session()
        close_opposite_positions(session, epic, action)
        result = place_order(session, action, epic, size)

        return jsonify({"status": "success", "details": result})

    except Exception as e:
        print("❌ Fehler:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
