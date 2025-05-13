from flask import Flask, request, jsonify
import requests
import traceback

app = Flask(__name__)

API_KEY = "bpSjrmwlN3zbTloa"
BASE_URL = "https://api-capital.backend-capital.com"

# Session erstellen
def create_session():
    session = requests.Session()
    session.headers.update({
        "X-CAP-API-KEY": API_KEY,
        "Content-Type": "application/json"
    })
    return session

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # JSON einlesen
        try:
            data = request.get_json(force=True)
        except Exception as json_error:
            print("❌ JSON-Fehler:", str(json_error))
            return "Invalid JSON", 400

        print("✅ Webhook empfangen:", data)

        if not data:
            print("❌ Kein JSON empfangen")
            return "No data", 400

        symbol = data.get("symbol")
        action = data.get("action")
        price = data.get("price")

        if not all([symbol, action, price]):
            print("❌ Fehlende Felder im Request:", data)
            return "Missing fields", 400

        print(f"➡ Symbol: {symbol}, Action: {action}, Price: {price}")

        session = create_session()

        # Produkt abrufen
        resp = session.get(f"{BASE_URL}/products?query={symbol}")
        print("🔎 Produkt-Suche Antwort:", resp.status_code, resp.text)

        if resp.status_code != 200:
            print("❌ Produkt-Suche fehlgeschlagen")
            return "Market lookup failed", 500

        products = resp.json().get("products", [])
        if not products:
            print("❌ Kein Produkt gefunden für:", symbol)
            return "Product not found", 404

        product_id = products[0]["id"]
        print("✅ Produkt-ID gefunden:", product_id)

        # Order vorbereiten
        order_data = {
            "market": product_id,
            "direction": "BUY" if action.lower() == "buy" else "SELL",
            "orderType": "MARKET",
            "quantity": 1
        }

        print("📤 Sende Order:", order_data)

        order_resp = session.post(f"{BASE_URL}/positions", json=order_data)
        print("📨 Order-Antwort:", order_resp.status_code, order_resp.text)

        if order_resp.status_code != 201:
            print("❌ Order fehlgeschlagen:", order_resp.text)
            return f"Order failed: {order_resp.text}", 500

        print("✅ Order erfolgreich ausgeführt")
        return jsonify({"status": "ok", "message": "Order placed"}), 200

    except Exception as e:
        print("❌ Allgemeiner Fehler:", str(e))
        traceback.print_exc()
        return "Server error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
