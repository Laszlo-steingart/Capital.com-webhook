from flask import Flask, request, jsonify
import requests
import traceback

app = Flask(__name__)

# Deine Zugangsdaten (HIER EINTRAGEN)
API_KEY = "mV5fieaBA6qmRQBV"
API_PASSWORD = "bE@u3kMaK879TfY"
USERNAME = "l.steingart@icloud.com"
BASE_URL = "https://api-capital.backend-capital.com"

# Login & Session-Tokens abrufen
def create_authenticated_session():
    session = requests.Session()
    session.headers.update({"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"})

    login_payload = {
        "identifier": USERNAME,
        "password": API_PASSWORD,
        "encryptedPassword": False
    }

    login_url = f"{BASE_URL}/session"
    login_response = session.post(login_url, json=login_payload)

    if login_response.status_code != 200:
        print("❌ Login fehlgeschlagen:", login_response.text)
        return None

    # Tokens aus Header extrahieren
    cst = login_response.headers.get("CST")
    xst = login_response.headers.get("X-SECURITY-TOKEN")

    session.headers.update({
        "CST": cst,
        "X-SECURITY-TOKEN": xst
    })

    return session

# Webhook-Endpunkt
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("✅ Webhook empfangen:", data)

        symbol = data.get("symbol", "BTC")
        action = data.get("action", "buy").lower()
        size = data.get("size", 1)

        if action not in ["buy", "sell"]:
            return "Ungültige Action", 400

        session = create_authenticated_session()
        if not session:
            return "Login fehlgeschlagen", 500

        # Markt suchen
        market_resp = session.get(f"{BASE_URL}/markets?searchTerm={symbol}")
        print("🔍 Marktsuche Antwort:", market_resp.status_code)

        if market_resp.status_code != 200:
            return "Marktsuche fehlgeschlagen", 500

        markets = market_resp.json().get("markets", [])
        if not markets:
            return "Kein Markt gefunden", 404

        epic = markets[0].get("epic")
        print("✅ Gefundener EPIC:", epic)

        # Order senden
        order_data = {
            "epic": epic,
            "direction": action.upper(),
            "orderType": "MARKET",
            "size": size
        }

        order_resp = session.post(f"{BASE_URL}/positions", json=order_data)
        print("📨 Order Antwort:", order_resp.status_code, order_resp.text)

        if order_resp.status_code != 201:
            return f"Order fehlgeschlagen: {order_resp.text}", 500

        return jsonify({"status": "ok", "message": "Order ausgeführt"}), 200

    except Exception as e:
        print("❌ Fehler im Webhook:", e)
        traceback.print_exc()
        return "Serverfehler", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
