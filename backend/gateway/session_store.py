from threading import Lock
from time import time_ns

lock = Lock()

state = {
    "session_id": None,
    "last_realtime": None,
    "last_status": None,
    "last_update_ns": None,
    "distance_sim_m": 0.0,
    "slope_pct": 0.0,
    "current_lat": 50.66609,
    "current_lon": 4.61852,
    "current_ele": 140.0,
    "total_dist_m": 4009.73,
}


def update_realtime(payload: dict) -> dict:
    with lock:
        state["session_id"] = payload.get("session_id", state["session_id"])
        state["last_realtime"] = payload
        state["last_update_ns"] = time_ns()

        # Pico publie toutes les 200ms → dt = 0.2s
        speed_sim_kmh = payload.get("speed_sim_kmh", 0.0) or 0.0
        speed_sim_ms = speed_sim_kmh / 3.6
        state["distance_sim_m"] += speed_sim_ms * 0.2  # ← était 1.0, corrigé

        return dict(state)


def update_status(payload: dict) -> dict:
    with lock:
        state["session_id"] = payload.get("session_id", state["session_id"])
        state["last_status"] = payload
        state["last_update_ns"] = time_ns()
        return dict(state)


def get_state() -> dict:
    with lock:
        return dict(state)


def update_slope(slope_pct: float, lat: float, lon: float, ele: float) -> None:
    with lock:
        state["slope_pct"] = slope_pct
        state["current_lat"] = lat
        state["current_lon"] = lon
        state["current_ele"] = ele


def reset_distance() -> None:
    with lock:
        state["distance_sim_m"] = 0.0
        state["current_lat"] = 50.66609
        state["current_lon"] = 4.61852
        state["current_ele"] = 140.0
