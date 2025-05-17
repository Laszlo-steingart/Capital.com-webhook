from flask import Flask, request, jsonify
import requests
import logging
import pyotp

app = Flask(__name__)

# >>>>>>>> ZUGANGSDATEN <<<<<<<<
API_KEY = "mV5fieaBA6qmRQBV"
API_USERNAME = "l.steingart@icloud.com"  # <-- wichtig: kein @, das ist der API-Login
API_PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

logging.basicConfig(level=logging.DEBUG)

def login():
    otp = pyotp.TOTP(TOTP_SECRET).now()
    logging.info(f"🔐 Generierter OTP: {otp}")

    url = f"{BASE_URL}/api/v1/session"
    headers = {
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "identifier": API_USERNAME,
        "password": API_PASSWORD,
        "oneTimePassword": otp
    }

    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        logging.error("❌ Login fehlgeschlagen: %s", resp.text)
        return None, None

    cst = resp.headers.get("CST")
    security_token = resp.headers.get("X-SECURITY-TOKEN")

    if not cst or not security_token:
        logging.error("❌ Token fehlen im Header")
        return None, None

    logging.info("✅ Login erfolgreich mit 2FA")
    return cst, security_token

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        logging.info("📩 Webhook empfangen: %s", data)

        symbol = data.get("symbol")
        action = data.get("action")
        size = float(data.get("size", 0.03))

        if not all([symbol, action, size]):
            return "Fehlende Felder", 400

        # Login
        cst, security_token = login()
        if not cst or not security_token:
            return "Login fehlgeschlagen", 500

        # Produkt suchen
        headers = {
            "X-CAP-API-KEY": API_KEY,
            "CST": cst,
            "X-SECURITY-TOKEN": security_token,
            "Content-Type": "application/json"
        }

        market_resp = requests.get(f"{BASE_URL}/api/v1/markets?searchTerm={symbol}", headers=headers)
        if market_resp.status_code != 200:
            logging.error("❌ Produktsuche fehlgeschlagen: %s", market_resp.text)
            return "Produktsuche fehlgeschlagen", 500

        markets = market_resp.json().get("markets", [])
        if not markets:
            logging.error("❌ Kein Markt gefunden")
            return "Produkt nicht gefunden", 404

        epic = markets[0]["epic"]
        logging.info("✅ Gefundener EPIC: %s", epic)

        # Order senden
        order_data = {
            "epic": epic,
            "direction": action.upper(),
            "orderType": "MARKET",
            "size": size,
            "currencyCode": "EUR",
            "forceOpen": True,
            "guaranteedStop": False
        }

        order_resp = requests.post(f"{BASE_URL}/api/v1/positions", json=order_data, headers=headers)
        if order_resp.status_code != 201:
            logging.error("❌ Order fehlgeschlagen: %s", order_resp.text)
            return "Order fehlgeschlagen", 500

        logging.info("✅ Order erfolgreich ausgeführt")
        return jsonify({"status": "ok", "message": "Order ausgeführt"}), 200

    except Exception as e:
        logging.exception("❌ Fehler im Webhook")
        return "Serverfehler", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
