from threading import Lock
from time import time_ns

_lock = Lock()

_state = {
    "session_id": None,
    "last_realtime": None,
    "last_status": None,
    "last_update_ns": None,
    # [NOUVEAU] parcours virtuel
    "distance_sim_m": 0.0,
    "slope_pct": 0.0,
    "current_lat": 50.66609,
    "current_lon": 4.61852,
    "current_ele": 140.0,
    "total_dist_m": 4009.73,
}


def update_realtime(payload: dict) -> dict:
    with _lock:
        _state["session_id"] = payload.get("session_id", _state["session_id"])
        _state["last_realtime"] = payload
        _state["last_update_ns"] = time_ns()

        # Intégration distance_sim_m depuis speed_sim_kmh
        # Le Pico publie ~1x/s → on intègre sur 1 seconde
        speed_sim_kmh = payload.get("speed_sim_kmh", 0.0) or 0.0
        speed_sim_ms = speed_sim_kmh / 3.6
        _state["distance_sim_m"] = (
            _state["distance_sim_m"] + speed_sim_ms * 1.0
        ) % _state["total_dist_m"]

        return dict(_state)


def update_status(payload: dict) -> dict:
    with _lock:
        _state["session_id"] = payload.get("session_id", _state["session_id"])
        _state["last_status"] = payload
        _state["last_update_ns"] = time_ns()
        return dict(_state)


def get_state() -> dict:
    with _lock:
        return dict(_state)


# Appelé par SlopeController pour mettre à jour position/pente
def update_slope(slope_pct: float, lat: float, lon: float, ele: float) -> None:
    with _lock:
        _state["slope_pct"] = slope_pct
        _state["current_lat"] = lat
        _state["current_lon"] = lon
        _state["current_ele"] = ele
