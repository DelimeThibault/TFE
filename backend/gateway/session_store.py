from threading import Lock
from time import time_ns

lock = Lock()

state = {
    "session_id": None,
    "last_realtime": None,
    "last_status": None,
    "last_update_ns": None,

    # données brutes / système
    "distance_sim_m": 0.0,
    "slope_pct": 0.0,
    "current_lat": 50.66609,
    "current_lon": 4.61852,
    "current_ele": 140.0,
    "total_dist_m": 4009.73,

    # session dashboard
    "session_started_ns": time_ns(),
    "distance_offset_m": 0.0,
    "energy_offset_wh": 0.0,
    "session_running": True,
    "paused_at_ns": None,
    "paused_accumulated_ns": 0,
}

def _build_public_state() -> dict:
    snapshot = dict(state)

    now_ns = time_ns()
    session_started_ns = snapshot.get("session_started_ns") or now_ns
    distance_total_m = snapshot.get("distance_sim_m", 0.0) or 0.0
    distance_offset_m = snapshot.get("distance_offset_m", 0.0) or 0.0

    last_realtime = dict(snapshot.get("last_realtime") or {})
    energy_total_wh = last_realtime.get("energy_wh", 0.0) or 0.0
    energy_offset_wh = snapshot.get("energy_offset_wh", 0.0) or 0.0

    paused_accumulated_ns = snapshot.get("paused_accumulated_ns", 0) or 0
    paused_at_ns = snapshot.get("paused_at_ns")
    session_running = bool(snapshot.get("session_running", True))

    current_pause_ns = 0
    if not session_running and paused_at_ns:
        current_pause_ns = max(0, now_ns - paused_at_ns)

    effective_elapsed_ns = max(
        0,
        now_ns - session_started_ns - paused_accumulated_ns - current_pause_ns
    )

    distance_session_m = max(0.0, distance_total_m - distance_offset_m)
    energy_session_wh = max(0.0, energy_total_wh - energy_offset_wh)
    session_duration_s = effective_elapsed_ns // 1_000_000_000

    last_realtime["energy_session_wh"] = round(energy_session_wh, 2)

    snapshot["last_realtime"] = last_realtime
    snapshot["distance_session_m"] = round(distance_session_m, 2)
    snapshot["session_duration_s"] = int(session_duration_s)
    snapshot["session_running"] = session_running

    return snapshot

def update_realtime(payload: dict) -> dict:
    with lock:
        state["session_id"] = payload.get("session_id", state["session_id"])
        state["last_update_ns"] = time_ns()

        if not state.get("session_running", True):
            return _build_public_state()

        state["last_realtime"] = payload

        speed_sim_kmh = payload.get("speed_sim_kmh", 0.0) or 0.0
        speed_sim_ms = speed_sim_kmh / 3.6

        # Pico publie toutes les 200 ms
        state["distance_sim_m"] += speed_sim_ms * 0.2

        return _build_public_state()

def update_status(payload: dict) -> dict:
    with lock:
        state["session_id"] = payload.get("session_id", state["session_id"])
        state["last_status"] = payload
        state["last_update_ns"] = time_ns()
        return _build_public_state()

def get_state() -> dict:
    with lock:
        return _build_public_state()

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

def reset_dashboard_state() -> dict:
    with lock:
        current_energy_wh = 0.0
        if state["last_realtime"]:
            current_energy_wh = state["last_realtime"].get("energy_wh", 0.0) or 0.0

        state["session_started_ns"] = time_ns()
        state["distance_offset_m"] = state.get("distance_sim_m", 0.0) or 0.0
        state["energy_offset_wh"] = current_energy_wh
        state["session_running"] = True
        state["paused_at_ns"] = None
        state["paused_accumulated_ns"] = 0

        return _build_public_state()

def pause_session() -> dict:
    with lock:
        if state.get("session_running", True):
            state["session_running"] = False
            state["paused_at_ns"] = time_ns()
            state["last_update_ns"] = time_ns()
        return _build_public_state()

def resume_session() -> dict:
    with lock:
        if not state.get("session_running", True):
            paused_at_ns = state.get("paused_at_ns")
            if paused_at_ns:
                state["paused_accumulated_ns"] += max(0, time_ns() - paused_at_ns)

            state["paused_at_ns"] = None
            state["session_running"] = True
            state["last_update_ns"] = time_ns()

        return _build_public_state()

def is_session_running() -> bool:
    with lock:
        return bool(state.get("session_running", True))