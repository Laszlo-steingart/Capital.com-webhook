from flask import Flask, request, jsonify
import requests
import pyotp
import os
import json

app = Flask(__name__)

# === Capital.com Zugangsdaten ===
API_KEY = "mV5fieaBA6qmRQBV"
API_USERNAME = "l.steingart@icloud.com"
API_PASSWORD = "bE@u3kMaK879TfY"
TOTP_SECRET = "5USUDSPOGCQ3NMKB"
BASE_URL = "https://api-capital.backend-capital.com"

# === TOTP-Code erzeugen ===
def get_totp(secret):
    return pyotp.TOTP(secret).now()

# === Session starten ===
def get_session():
    response = requests.post(
        f"{BASE_URL}/api/v1/session",
        headers={
            "X-CAP-API-KEY": API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "identifier": API_USERNAME,
            "password": API_PASSWORD,
            "encrypted": False,
            "totpCode": get_totp(TOTP_SECRET),
        }
    )
    response.raise_for_status()
    return {
        "CST": response.headers["CST"],
        "X-SECURITY-TOKEN": response.headers["X-SECURITY-TOKEN"]
    }

# === Haupt-Webhook-Endpunkt ===
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Header und Body für Debug anzeigen
        print("📥 HEADERS:", dict(request.headers))
        raw_body = request.data.decode("utf-8")
        print("📦 BODY (raw):", raw_body)

        # Versuche JSON aus dem Body zu parsen
        try:
            data = request.get_json(force=True)
        except Exception:
            try:
                data = json.loads(raw_body)
            except Exception as e:
                return jsonify({"error": "Konnte Body nicht als JSON parsen", "details": str(e)}), 400

        if not data:
            return jsonify({"error": "Leerer oder ungültiger JSON-Body"}), 400

        print("📩 Geparstes JSON:", data)

        # Felder extrahieren
        action = data.get("action")
        symbol = data.get("symbol", "").replace("/", "")
        try:
            price = float(data.get("price", 0))
            size = float(data.get("size", 0))
        except ValueError:
            return jsonify({"error": "Preis oder Größe sind keine Zahlen"}), 400

        if not all([action, symbol, price, size]):
            return jsonify({"error": "Fehlende oder ungültige Felder"}), 400

        # Mapping zu Capital.com EPICs
        symbol_map = {
            "EURUSD": "CS.D.EURUSD.CFD.IP",
            "USDJPY": "CS.D.USDJPY.CFD.IP"
            # Weitere Symbole hier hinzufügen
        }
        epic = symbol_map.get(symbol.upper())
        if not epic:
            return jsonify({"error": f"Unbekanntes Symbol: {symbol}"}), 400

        # Session holen (Capital.com Login)
        session = get_session()

        # Ausgabe – Trade hier noch nicht ausgeführt
        print(f"✅ Trade empfangen → {action.upper()} {size}x {epic} @ {price}")
        return jsonify({"status": "ok", "info": "Trade empfangen und geprüft"})

    except Exception as e:
        print("❌ Fehler beim Verarbeiten:", str(e))
        return jsonify({"error": str(e)}), 500

# === Server starten ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
