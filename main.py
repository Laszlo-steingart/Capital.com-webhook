from flask import Flask, request, jsonify
import requests
import pyotp
import os

app = Flask(__name__)

# === CAPITAL.COM API-ZUGANGSDATEN ===
API_KEY = "mV5fieaBA6qmRQBV"
USERNAME = "l.steingart@icloud.com"
PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

session = requests.Session()

def get_totp_code(secret):
    return pyotp.TOTP(secret).now()

def login():
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

    print("🟡 Login wird versucht mit 2FA-Code:", code)
    response = session.post(f"{BASE_URL}/api/v1/session", json=payload, headers=headers)
    print("🔵 Login-Antwort:", response.status_code, response.text)

    if response.status_code != 200:
        raise Exception(f"Login fehlgeschlagen: {response.text}")

    session.headers.update({
        "CST": response.headers["CST"],
        "X-SECURITY-TOKEN": response.headers["X-SECURITY-TOKEN"],
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    })
    print("✅ Login erfolgreich!")

def get_epic_by_name(name="Bitcoin"):
    print("🔍 Suche Epic für:", name)
    response = session.get(f"{BASE_URL}/api/v1/markets/{name}")
    if response.status_code == 200:
        markets = response.json().get("markets", [])
        for market in markets:
            if "Bitcoin" in market["instrumentName"]:
                print("✅ Gefundener Epic:", market["epic"])
                return market["epic"]
        print("⚠️ Kein passender Epic gefunden")
    else:
        print("❌ Fehler bei Market-Suche:", response.status_code, response.text)
    return None

@app.route("/webhook", methods=["POST"])
def webhook():
    print("📥 Rohdaten:", request.data)

    try:
        data = request.get_json(force=True)
        print("📨 Empfangenes JSON:", data)
    except Exception as e:
        print("❌ Fehler beim JSON lesen:", str(e))
        return jsonify({"error": "Ungültiges JSON"}), 400

    action = data.get("action")
    symbol_input = data.get("symbol", "Bitcoin")
    size = data.get("size")

    if action not in ["buy", "sell"] or not symbol_input or not size:
        print("⚠️ Ungültige Daten:", data)
        return jsonify({"error": "Fehlende oder ungültige Felder"}), 400

    try:
        login()
    except Exception as e:
        print("❌ Login-Fehler:", str(e))
        return jsonify({"error": str(e)}), 401

    # 🔁 Symbol-Mapping mit .upper()
    symbol_map = {
        "BTCUSD": "Bitcoin"
    }
    symbol_key = symbol_input.upper()
    search_term = symbol_map.get(symbol_key, symbol_key)
    print("🔎 Suche Epic für:", search_term)

    epic = get_epic_by_name(search_term)
    if not epic:
        return jsonify({"error": f"Kein Epic gefunden für {symbol_input}"}), 400

    opposite = "SELL" if action == "buy" else "BUY"

    close_payload = {
        "epic": epic,
        "direction": opposite,
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "forceOpen": False,
        "currencyCode": "USD"
    }
    print("🔁 Sende Close-Order:", close_payload)
    close_response = session.post(f"{BASE_URL}/api/v1/positions/otc", json=close_payload)
    print("🔁 Antwort Close:", close_response.status_code, close_response.text)

    open_payload = {
        "epic": epic,
        "direction": action.upper(),
        "size": size,
        "orderType": "MARKET",
        "guaranteedStop": False,
        "forceOpen": True,
        "currencyCode": "USD"
    }
    print("🟢 Sende Open-Order:", open_payload)
    response = session.post(f"{BASE_URL}/api/v1/positions/otc", json=open_payload)
    print("🟢 Antwort Open:", response.status_code, response.text)

    if response.status_code == 200:
        return jsonify({"status": "Trade erfolgreich"}), 200
    else:
        return jsonify({"error": response.text}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
