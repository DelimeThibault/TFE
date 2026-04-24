import json
import time
import threading
import paho.mqtt.client as mqtt

from gateway.session_store import update_realtime, update_status

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
TOPIC_REALTIME = "bike/pico/telemetry/realtime"
TOPIC_STATUS = "bike/pico/status"
TOPIC_TIMEBASE = "bike/pi/system/timebase"
TOPIC_SLOPE = "bike/pi/control/slope"

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

_message_handler = None
_timebase_seq = 0


def set_message_handler(handler):
    global _message_handler
    _message_handler = handler


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Connecté au broker local avec code={reason_code}")
    client.subscribe(TOPIC_REALTIME, qos=0)
    client.subscribe(TOPIC_STATUS, qos=1)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception as exc:
        print(f"[MQTT] Payload invalide sur {msg.topic}: {exc}")
        return

    ts_app_rx_ms = int(time.time() * 1000)

    if msg.topic == TOPIC_REALTIME:
        payload["ts_app_rx_ms"] = ts_app_rx_ms
        state = update_realtime(payload)
        event_name = "realtime_update"
    elif msg.topic == TOPIC_STATUS:
        payload["ts_app_rx_ms"] = ts_app_rx_ms
        state = update_status(payload)
        event_name = "status_update"
    else:
        return

    if _message_handler:
        _message_handler(event_name, payload, state)


def publish_timebase():
    global _timebase_seq
    while True:
        try:
            _timebase_seq += 1
            payload = {"ts_app_ms": int(time.time() * 1000), "seq": _timebase_seq}
            mqtt_client.publish(TOPIC_TIMEBASE, json.dumps(payload), qos=0)
        except Exception as exc:
            print(f"[MQTT] Erreur publication timebase: {exc}")
        time.sleep(1)


def publish_slope(slope_pct: float) -> None:
    """Publie la pente courante vers le Pico."""
    try:
        mqtt_client.publish(TOPIC_SLOPE, json.dumps({"slope_pct": slope_pct}), qos=0)
    except Exception as exc:
        print(f"[MQTT] Erreur publication slope: {exc}")


def start_mqtt():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()

    thread = threading.Thread(target=publish_timebase, daemon=True)
    thread.start()

    return mqtt_client
