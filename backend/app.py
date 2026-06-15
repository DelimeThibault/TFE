from flask import Flask, render_template, jsonify, send_from_directory, Response
from flask_socketio import SocketIO
import os
import base64

from gateway.mqtt_client import start_mqtt, set_message_handler
from gateway.session_store import get_state, reset_dashboard_state, pause_session, resume_session, is_session_running
from gateway.slope_controller import SlopeController

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-local-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GPX_PATH = os.path.join(BASE_DIR, "static", "lln_24h.gpx")

EMPTY_TILE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

slope_ctrl = None

WORKOUT_IDS = {"easy-5", "mid-10", "hard-15"}


# ── Routes pages ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/parcours")
def parcours():
    return render_template("parcours.html")


@app.route("/entrainements")
def entrainements():
    return render_template("entrainements.html")


@app.route("/entrainements/session/<workout_id>")
def entrainement_session(workout_id):
    if workout_id not in WORKOUT_IDS:
        return render_template("entrainements.html"), 404
    return render_template("entrainement_session.html", workout_id=workout_id)


# ── Routes API données ─────────────────────────────────────────────────────────

@app.route("/api/session")
def api_session():
    return jsonify(get_state())


@app.route("/api/state")
def api_state():
    return jsonify(get_state())


@app.route("/api/parcours/lln")
def api_parcours_lln():
    if slope_ctrl is None:
        return jsonify({"name": "24h Vélo de LLN", "total_dist": 0.0, "points": []})

    return jsonify(
        {
            "name": "24h Vélo de LLN",
            "total_dist": slope_ctrl.total_dist,
            "points": slope_ctrl.get_route_data(),
        }
    )


# ── Routes API contrôle parcours ───────────────────────────────────────────────

@app.route("/api/parcours/start", methods=["POST"])
def api_parcours_start():
    if slope_ctrl is None:
        return jsonify({"status": "unavailable", "running": False}), 503

    slope_ctrl.start_parcours()
    return jsonify({"status": "started", "running": True})


@app.route("/api/parcours/stop", methods=["POST"])
def api_parcours_stop():
    if slope_ctrl is None:
        return jsonify({"status": "unavailable", "running": False}), 503

    slope_ctrl.stop_parcours()
    return jsonify({"status": "stopped", "running": False})


@app.route("/api/parcours/reset", methods=["POST"])
def api_parcours_reset():
    if slope_ctrl is None:
        return jsonify({"status": "unavailable"}), 503

    slope_ctrl.reset_parcours()
    socketio.emit("parcours_reset", {})
    return jsonify({"status": "reset", "scope": "parcours"})


@app.route("/api/parcours/status")
def api_parcours_status():
    state = get_state()

    return jsonify(
        {
            "running": slope_ctrl.parcours_actif if slope_ctrl is not None else False,
            "distance_m": state.get("distance_sim_m", 0.0),
            "distance_session_m": state.get("distance_session_m", 0.0),
            "slope_pct": state.get("slope_pct", 0.0),
            "lat": state.get("current_lat"),
            "lon": state.get("current_lon"),
            "ele": state.get("current_ele"),
            "speed_sim_kmh": (state.get("last_realtime") or {}).get("speed_sim_kmh", 0.0),
        }
    )


# ── Routes API contrôle dashboard ──────────────────────────────────────────────

@app.route("/api/dashboard/reset", methods=["POST"])
def api_dashboard_reset():
    state = reset_dashboard_state()
    socketio.emit("dashboard_reset", state)
    socketio.emit("session_snapshot", state)
    return jsonify({"status": "reset", "scope": "dashboard"})

@app.route("/api/session/status")
def api_session_status():
    state = get_state()
    return jsonify(
        {
            "running": is_session_running(),
            "session_id": state.get("session_id"),
            "last_update_ns": state.get("last_update_ns"),
        }
    )


@app.route("/api/session/pause", methods=["POST"])
def api_session_pause():
    state = pause_session()
    socketio.emit("session_snapshot", state)
    return jsonify(
        {
            "status": "paused",
            "running": False,
            "session_id": state.get("session_id"),
        }
    )


@app.route("/api/session/resume", methods=["POST"])
def api_session_resume():
    state = resume_session()
    socketio.emit("session_snapshot", state)
    return jsonify(
        {
            "status": "running",
            "running": True,
            "session_id": state.get("session_id"),
        }
    )

# ── Tuiles hors ligne ──────────────────────────────────────────────────────────

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def serve_tile(z, x, y):
    tile_path = os.path.join(BASE_DIR, "static", "tiles", str(z), str(x))
    tile_file = f"{y}.png"
    if not os.path.exists(os.path.join(tile_path, tile_file)):
        return Response(EMPTY_TILE, mimetype="image/png")
    return send_from_directory(tile_path, tile_file, mimetype="image/png")


# ── Handler MQTT → Socket.IO ───────────────────────────────────────────────────

def forward_to_ui(event_name, payload, state):
    if event_name == "realtime_update" and state.get("last_realtime"):
        payload = dict(payload)
        payload["energy_session_wh"] = state.get("energy_session_wh", 0)
        payload["distance_session_m"] = state.get("distance_session_m", 0)
        payload["parcours_distance_m"] = state.get("parcours_distance_m", 0)
        payload["session_duration_s"] = state.get("session_duration_s", 0)
    socketio.emit(event_name, payload)
    socketio.emit("session_snapshot", state)


# ── Callback SlopeController → Socket.IO ──────────────────────────────────────

def emit_position(slope_pct, lat, lon, ele, distance_m):
    socketio.emit(
        "position_update",
        {
            "slope_pct": slope_pct,
            "lat": lat,
            "lon": lon,
            "ele": ele,
            "distance_m": distance_m,
        },
    )


# ── Initialisation ─────────────────────────────────────────────────────────────

def init_services():
    global slope_ctrl

    set_message_handler(forward_to_ui)
    start_mqtt()

    slope_ctrl = SlopeController(GPX_PATH, emit_callback=emit_position)
    if os.path.exists(GPX_PATH):
        slope_ctrl.start()
    else:
        print(f"[WARN] GPX introuvable : {GPX_PATH} — SlopeController non démarré")


init_services()


# ── Lancement ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=2500, debug=False,
                 allow_unsafe_werkzeug=True)