from flask import Flask, request, jsonify
import requests
import traceback

app = Flask(__name__)

EMAIL = "l.steingart@icloud.com"
PASSWORD = "bE@u3kMaK879TfY"
API_KEY = "mV5fieaBA6qmRQBV"
BASE_URL = "https://api-capital.backend-capital.com"

def create_authenticated_session():
    session = requests.Session()
    session.headers.update({
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    })

    login_payload = {
        "identifier": EMAIL,
        "password": PASSWORD
    }

    login_resp = session.post(f"{BASE_URL}/api/v1/session", json=login_payload)
    if login_resp.status_code != 200:
        print("❌ Login fehlgeschlagen:", login_resp.text)
        return None

    tokens = login_resp.headers
    session.headers.update({
        "CST": tokens.get("CST"),
        "X-SECURITY-TOKEN": tokens.get("X-SECURITY-TOKEN")
    })

    print("✅ Login erfolgreich")
    return session

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Webhook empfangen:", data)

        symbol = data.get("symbol")
        action = data.get("action")
        size = data.get("size")

        if not all([symbol, action, size]):
            print("❌ Fehlende Daten:", data)
            return "Fehlende Felder", 400

        session = create_authenticated_session()
        if session is None:
            return "Login fehlgeschlagen", 500

        # Produkt-ID finden
        product_resp = session.get(f"{BASE_URL}/api/v1/products?searchTerm={symbol}")
        if product_resp.status_code != 200:
            print("❌ Produktsuche fehlgeschlagen:", product_resp.text)
            return "Produktsuche fehlgeschlagen", 500

        products = product_resp.json().get("markets", [])
        if not products:
            print("❌ Kein Produkt gefunden:", symbol)
            return "Kein Produkt gefunden", 404

        epic = products[0]["epic"]
        print("✅ Gefundener EPIC:", epic)

        # Orderdaten vorbereiten
        order_data = {
            "epic": epic,
            "direction": action.upper(),
            "orderType": "MARKET",
            "size": size,
            "currencyCode": "EUR",
            "forceOpen": True,
            "guaranteedStop": False
        }

        print("📤 Sende Order:", order_data)

        order_resp = session.post(f"{BASE_URL}/api/v1/positions", json=order_data)
        print("📨 Antwort:", order_resp.status_code, order_resp.text)

        if order_resp.status_code != 201:
            return f"Order fehlgeschlagen: {order_resp.text}", 500

        return jsonify({"status": "ok", "message": "Order erfolgreich"}), 200

    except Exception as e:
        print("❌ Ausnahme:", str(e))
        traceback.print_exc()
        return "Interner Fehler", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
