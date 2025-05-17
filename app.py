from flask import Flask, request, jsonify
import requests
import logging
import pyotp

app = Flask(__name__)

# >>>>>>>> ZUGANGSDATEN <<<<<<<<
API_KEY = "mV5fieaBA6qmRQBV"
API_USERNAME = "l.steingart@icloud.com"
API_PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

logging.basicConfig(level=logging.INFO)

def login():
    otp = pyotp.TOTP(TOTP_SECRET).now()
    logging.info(f"🔐 Generierter OTP: {otp}")

    headers = {
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "identifier": API_USERNAME,
        "password": API_PASSWORD,
        "oneTimePassword": otp
    }

    resp = requests.post(f"{BASE_URL}/api/v1/session", headers=headers, json=payload)
    if resp.status_code != 200:
        logging.error("❌ Login fehlgeschlagen: %s", resp.text)
        return None, None

    cst = resp.headers.get("CST")
    token = resp.headers.get("X-SECURITY-TOKEN")

    if not cst or not token:
        logging.error("❌ Tokens fehlen im Header: %s", resp.headers)
        return None, None

    logging.info("✅ Login erfolgreich")
    return cst, token

def close_all_positions(headers):
    """Schließt ALLE offenen Positionen, egal welches Symbol."""
    resp = requests.get(f"{BASE_URL}/api/v1/positions", headers=headers)
    if resp.status_code != 200:
        logging.error("❌ Fehler beim Abrufen offener Positionen")
        return

    for pos in resp.json().get("positions", []):
        deal_id = pos["position"]["dealId"]
        direction = pos["position"]["direction"]
        size = pos["position"]["size"]

        close_data = {
            "dealId": deal_id,
            "direction": "SELL" if direction == "BUY" else "BUY",
            "orderType": "MARKET",
            "size": size
        }

        logging.info(f"🔁 Schließe Position: {deal_id} ({direction}, Größe: {size})")
        close_resp = requests.post(f"{BASE_URL}/api/v1/positions/otc", headers=headers, json=close_data)
        if close_resp.status_code == 200:
            logging.info("✅ Position geschlossen")
        else:
            logging.warning("⚠️ Fehler beim Schließen: %s", close_resp.text)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        logging.info("📩 Webhook empfangen: %s", data)

        symbol = data.get("symbol")
        position = data.get("position")
        size = float(data.get("size", 0.1))

        if position not in ("long", "short") or not symbol:
            return jsonify({"error": "Ungültige Daten"}), 400

        action = "BUY" if position == "long" else "SELL"

        cst, token = login()
        if not cst or not token:
            return jsonify({"error": "Login fehlgeschlagen"}), 500

        headers = {
            "X-CAP-API-KEY": API_KEY,
            "CST": cst,
            "X-SECURITY-TOKEN": token,
            "Content-Type": "application/json"
        }

        # Zuerst alle Positionen schließen
        logging.info("🧹 Schließe alle offenen Positionen...")
        close_all_positions(headers)

        # Produkt suchen
        market_resp = requests.get(f"{BASE_URL}/api/v1/markets?searchTerm={symbol}", headers=headers)
        if market_resp.status_code != 200:
            return jsonify({"error": "Produktsuche fehlgeschlagen"}), 500

        markets = market_resp.json().get("markets", [])
        if not markets:
            return jsonify({"error": "Produkt nicht gefunden"}), 404

        epic = markets[0]["epic"]
        logging.info("🎯 EPIC gefunden: %s", epic)

        # Neue Position eröffnen
        order_data = {
            "epic": epic,
            "direction": action,
            "orderType": "MARKET",
            "size": size,
            "currencyCode": "EUR",
            "forceOpen": True,
            "guaranteedStop": False
        }

        order_resp = requests.post(f"{BASE_URL}/api/v1/positions", headers=headers, json=order_data)
        if order_resp.status_code != 200:
            return jsonify({"error": "Order fehlgeschlagen", "details": order_resp.text}), 500

        deal_ref = order_resp.json().get("dealReference")
        if not deal_ref:
            return jsonify({"error": "Keine Deal-Referenz erhalten"}), 500

        confirm_resp = requests.get(f"{BASE_URL}/api/v1/confirms/{deal_ref}", headers=headers)
        if confirm_resp.status_code != 200:
            return jsonify({"error": "Orderbestätigung fehlgeschlagen"}), 500

        confirm_data = confirm_resp.json()
        if confirm_data.get("dealStatus", "").upper() == "ACCEPTED":
            logging.info("✅ Order akzeptiert")
            return jsonify({"status": "ok", "message": "Order erfolgreich", "details": confirm_data}), 200
        else:
            return jsonify({"error": "Order abgelehnt", "details": confirm_data}), 400

    except Exception as e:
        logging.exception("❌ Ausnahme im Webhook")
        return jsonify({"error": "Serverfehler"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
