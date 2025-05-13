from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

API_KEY = "bpSjrmwlN3zbTloa"
BASE_URL = "https://api-capital.backend-capital.com"

# Session erstellen
def create_session():
    session = requests.Session()
    session.headers.update({"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"})
    return session

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return "No data", 400

    symbol = data.get("symbol")
    action = data.get("action")
    price = data.get("price")

    if not all([symbol, action, price]):
        return "Missing fields", 400

    session = create_session()

    # Produkt-ID abrufen
    resp = session.get(f"{BASE_URL}/products?query={symbol}")
    if resp.status_code != 200:
        return "Market lookup failed", 500

    products = resp.json().get("products", [])
    if not products:
        return "Product not found", 404

    product_id = products[0]["id"]

    # Orderdaten
    order_data = {
        "market": product_id,
        "direction": "BUY" if action.lower() == "buy" else "SELL",
        "orderType": "MARKET",
        "quantity": 1
    }

    order_resp = session.post(f"{BASE_URL}/positions", json=order_data)
    if order_resp.status_code != 201:
        return f"Order failed: {order_resp.text}", 500

    return jsonify({"status": "ok", "message": "Order placed"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
