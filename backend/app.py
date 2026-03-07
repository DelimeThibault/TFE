import os
import sqlite3
from datetime import datetime
import json  # Ajoute ça si pas déjà là

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO

# ---------- Config ----------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_PATH = os.path.join(os.path.dirname(__file__), "cadence.db")

# ---------- Init DB ----------
def init_db():
    db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS cadence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cadence INTEGER NOT NULL,
            total_pulses INTEGER NOT NULL,
            sensor_ts_ms INTEGER NOT NULL,
            gateway_ts REAL,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()
    print(f"✅ DB initialisée : {DB_PATH}")

init_db()

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/cadence", methods=["POST"])
def api_cadence():
    if not request.is_json:
        return jsonify({"error": "JSON requis"}), 400

    data = request.get_json(silent=True) or {}
    try:
        cadence = int(data.get("cadence", 0))
        total_pulses = int(data.get("total_pulses", 0))
        sensor_ts_ms = int(data.get("timestamp", 0))
        gateway_ts = data.get("gateway_ts", None)
    except (TypeError, ValueError):
        return jsonify({"error": "Champs invalides"}), 400

    # DB directe
    db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    created_at = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
    db.execute(
        "INSERT INTO cadence_events (cadence, total_pulses, sensor_ts_ms, gateway_ts, created_at) VALUES (?, ?, ?, ?, ?)",
        (cadence, total_pulses, sensor_ts_ms, gateway_ts, created_at)
    )
    db.commit()
    db.close()

    payload = {
        "cadence": cadence,
        "total_pulses": total_pulses,
        "sensor_ts_ms": sensor_ts_ms,
        "gateway_ts": gateway_ts,
        "created_at": created_at,
    }
    socketio.emit("cadence_update", payload)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 2500))
    # En prod : debug=False
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)

