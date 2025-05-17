from flask import Flask, request, jsonify
import requests
import logging
import pyotp

app = Flask(__name__)

# >>>>>>>> ZUGANGSDATEN <<<<<<<<
API_KEY = "mV5fieaBA6qmRQBV"
API_USERNAME = "DEIN_API_LOGIN_NAME"  # <-- HIER richtigen API-Benutzernamen eintragen
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
    token = resp.headers.get("X-SECURITY-TOKEN")

    if not cst or not token:
        logging.error("❌ Token fehlen im Header")
        return None, None

    logging.info("✅ Login erfolgreich mit 2FA")
    return cst, token

def get_current_position(epic, headers):
    resp = requests.get(f"{BASE_URL}/api/v1/positions", headers=headers)
    if resp.status_code != 200:
        return None

    positions = resp.json().get("positions", [])
    for pos in positions:
        if pos["market"]["epic"] == epic:
            return {
                "direction": pos["position"]["direction"],
                "dealId": pos["position"]["dealId"],
                "size": pos["position"]["size"]
            }
    return None

def close_position(deal_id, direction, size, headers):
    close_data = {
        "dealId": deal_id,
        "direction": "SELL" if direction == "BUY" else "BUY",
        "orderType": "MARKET",
        "size": size
    }
    resp = requests.post(f"{BASE_URL}/api/v1/positions/otc", json=close_data, headers=headers)
    if resp.status_code == 200:
        logging.info("🔁 Alte Position geschlossen")
    else:
        logging.warning("⚠️ Fehler beim Schließen der Position: %s", resp.text)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        logging.info("📩 Webhook empfangen: %s", data)

        symbol = data.get("symbol")
        position = data.get("position")  # "long" oder "short"
        size = float(data.get("size", 0.03))

        if not all([symbol, position, size]):
            return "Fehlende Felder", 400

        if position == "long":
            action = "BUY"
        elif position == "short":
            action = "SELL"
        else:
            return "Ungültige Positionsangabe", 400

        # Login
        cst, token = login()
        if not cst or not token:
            return "Login fehlgeschlagen", 500

        headers = {
            "X-CAP-API-KEY": API_KEY,
            "CST": cst,
            "X-SECURITY-TOKEN": token,
            "Content-Type": "application/json"
        }

        # Produkt suchen
        market_resp = requests.get(f"{BASE_URL}/api/v1/markets?searchTerm={symbol}", headers=headers)
        if market_resp.status_code != 200:
            return "Produktsuche fehlgeschlagen", 500

        markets = market_resp.json().get("markets", [])
        if not markets:
            return "Produkt nicht gefunden", 404

        epic = markets[0]["epic"]
        logging.info("✅ Gefundener EPIC: %s", epic)

        # Aktuelle Position prüfen
        current = get_current_position(epic, headers)
        if current:
            if current["direction"] == action:
                logging.info("⏸ Bereits in Position (%s), keine Aktion nötig", action)
                return jsonify({"status": "ok", "message": "Bereits in Position – keine Aktion"}), 200
            else:
                logging.info("🔁 Schließe Gegenposition (%s)", current["direction"])
                close_position(current["dealId"], current["direction"], current["size"], headers)

        # Neue Order senden
        order_data = {
            "epic": epic,
            "direction": action,
            "orderType": "MARKET",
            "size": size,
            "currencyCode": "EUR",
            "forceOpen": True,
            "guaranteedStop": False
        }

        order_resp = requests.post(f"{BASE_URL}/api/v1/positions", json=order_data, headers=headers)
        deal_ref = order_resp.json().get("dealReference")

        if not deal_ref:
            return jsonify({"status": "error", "message": "Order fehlgeschlagen (keine Referenz)"}), 500

        confirm_resp = requests.get(f"{BASE_URL}/api/v1/confirms/{deal_ref}", headers=headers)
        if confirm_resp.status_code != 200:
            return jsonify({"status": "error", "message": "Orderbestätigung fehlgeschlagen"}), 500

        confirm_data = confirm_resp.json()
        if confirm_data.get("dealStatus", "").upper() == "ACCEPTED":
            logging.info("✅ Order erfolgreich: %s", confirm_data)
            return jsonify({"status": "ok", "message": "Order akzeptiert", "details": confirm_data}), 200
        else:
            return jsonify({"status": "error", "message": "Order abgelehnt", "details": confirm_data}), 400

    except Exception as e:
        logging.exception("❌ Fehler im Webhook")
        return "Serverfehler", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
