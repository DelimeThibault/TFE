from threading import Lock
from time import time_ns

_lock = Lock()

_state = {
    "session_id": None,
    "last_realtime": None,
    "last_status": None,
    "last_update_ns": None,
}


def update_realtime(payload: dict) -> dict:
    with _lock:
        _state["session_id"] = payload.get("session_id", _state["session_id"])
        _state["last_realtime"] = payload
        _state["last_update_ns"] = time_ns()
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
