from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

from gateway.mqtt_client import start_mqtt, set_message_handler
from gateway.session_store import get_state

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-local-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/session")
def api_session():
    return jsonify(get_state())


def forward_to_ui(event_name, payload, state):
    socketio.emit(event_name, payload)
    socketio.emit("session_snapshot", state)


if __name__ == "__main__":
    set_message_handler(forward_to_ui)
    start_mqtt()
    socketio.run(app, host="0.0.0.0", port=2500, debug=True)
