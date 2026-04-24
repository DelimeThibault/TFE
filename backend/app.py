from flask import Flask, render_template, jsonify, send_from_directory, abort
from flask_socketio import SocketIO
import os

from gateway.mqtt_client import start_mqtt, set_message_handler
from gateway.session_store import get_state
from gateway.slope_controller import SlopeController


app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-local-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


GPX_PATH = os.path.join(os.path.dirname(__file__), "static", "lln_24h.gpx")


# ── Routes ────────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/parcours")
def parcours():
    return render_template("parcours.html")


@app.route("/api/session")
def api_session():
    return jsonify(get_state())


@app.route("/api/parcours/lln")
def api_parcours_lln():
    return jsonify(
        {
            "name": "24h Vélo de LLN",
            "total_dist": slope_ctrl.total_dist,
            "points": slope_ctrl.get_route_data(),
        }
    )


@app.route("/api/state")
def api_state():
    return jsonify(get_state())


# ── Tuiles OpenStreetMap (mode hors ligne) ────────────────────────────────────


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def serve_tile(z, x, y):
    tile_path = os.path.join("static", "tiles", str(z), str(x))
    tile_file = f"{y}.png"
    if not os.path.exists(os.path.join(tile_path, tile_file)):
        abort(404)
    return send_from_directory(tile_path, tile_file, mimetype="image/png")


# ── Handler MQTT → Socket.IO ──────────────────────────────────────────────────


def forward_to_ui(event_name, payload, state):
    socketio.emit(event_name, payload)
    socketio.emit("session_snapshot", state)


# ── Lancement ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    set_message_handler(forward_to_ui)
    start_mqtt()

    slope_ctrl = SlopeController(GPX_PATH)
    if os.path.exists(GPX_PATH):
        slope_ctrl.start()
    else:
        print(f"[WARN] GPX introuvable : {GPX_PATH} — SlopeController non démarré")

    socketio.run(app, host="0.0.0.0", port=2500, debug=True)
