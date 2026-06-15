import math
import threading
import time
import xml.etree.ElementTree as ET

from gateway.session_store import get_state, update_slope
from gateway.mqtt_client import publish_slope


def _haversine(p1, p2):
    R = 6371000
    lat1, lon1 = math.radians(p1["lat"]), math.radians(p1["lon"])
    lat2, lon2 = math.radians(p2["lat"]), math.radians(p2["lon"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def load_gpx(filepath):
    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
    tree = ET.parse(filepath)
    root = tree.getroot()

    raw = []
    for trkpt in root.findall(".//gpx:trkpt", ns):
        raw.append(
            {
                "lat": float(trkpt.get("lat")),
                "lon": float(trkpt.get("lon")),
                "ele": float(trkpt.find("gpx:ele", ns).text),
            }
        )

    cum = 0.0
    for i, pt in enumerate(raw):
        pt["dist_m"] = 0.0 if i == 0 else round(cum + _haversine(raw[i - 1], pt), 2)
        if i > 0:
            cum = pt["dist_m"]

    slopes = [0.0]
    for i in range(1, len(raw)):
        d = _haversine(raw[i - 1], raw[i])
        dz = raw[i]["ele"] - raw[i - 1]["ele"]
        slopes.append(round((dz / d * 100) if d > 0.5 else 0.0, 2))

    for i, pt in enumerate(raw):
        if 0 < i < len(slopes) - 1:
            pt["slope_pct"] = round((slopes[i - 1] + slopes[i] + slopes[i + 1]) / 3, 2)
        else:
            pt["slope_pct"] = slopes[i]

    return raw


def get_slope_at_distance(points, dist_m):
    total = points[-1]["dist_m"]
    dist_m = dist_m % total
    for i in range(1, len(points)):
        if points[i]["dist_m"] >= dist_m:
            p0, p1 = points[i - 1], points[i]
            seg_len = p1["dist_m"] - p0["dist_m"]
            t = (dist_m - p0["dist_m"]) / seg_len if seg_len > 0 else 0
            return (
                round(p0["slope_pct"] + t * (p1["slope_pct"] - p0["slope_pct"]), 2),
                round(p0["lat"] + t * (p1["lat"] - p0["lat"]), 6),
                round(p0["lon"] + t * (p1["lon"] - p0["lon"]), 6),
                round(p0["ele"] + t * (p1["ele"] - p0["ele"]), 1),
            )
    return 0.0, points[-1]["lat"], points[-1]["lon"], points[-1]["ele"]


class SlopeController:

    PUBLISH_INTERVAL = 0.5  # secondes

    def __init__(self, gpx_path, emit_callback=None):
        self.points = load_gpx(gpx_path)
        self.total_dist = self.points[-1]["dist_m"]
        self._running = False
        self.parcours_actif = False
        self._parcours_offset_m = None
        # Callback facultatif → appelé à chaque cycle pour émettre via Socket.IO
        self._emit = emit_callback or (lambda *a: None)
        print(
            f"[SlopeController] {len(self.points)} points, {self.total_dist/1000:.2f} km"
        )

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()
        print("[SlopeController] Thread démarré")

    def stop(self):
        self._running = False

    def start_parcours(self):
        if self._parcours_offset_m is None:
            self._parcours_offset_m = get_state().get("distance_sim_m", 0.0) or 0.0
        self.parcours_actif = True
        print("[SlopeController] Parcours démarré")

    def stop_parcours(self):
        self.parcours_actif = False
        print("[SlopeController] Parcours arrêté")

    def reset_parcours(self):
        self._parcours_offset_m = get_state().get("distance_sim_m", 0.0) or 0.0
        print("[SlopeController] Parcours réinitialisé")

    def get_route_data(self):
        return [
            {
                "lat": p["lat"],
                "lon": p["lon"],
                "ele": p["ele"],
                "dist_m": p["dist_m"],
                "slope_pct": p["slope_pct"],
            }
            for p in self.points
        ]

    def _loop(self):
        while self._running:
            try:
                raw_dist_m = get_state().get("distance_sim_m", 0.0) or 0.0
                offset_m = self._parcours_offset_m or 0.0
                dist_m = max(0.0, raw_dist_m - offset_m)
                slope, lat, lon, ele = get_slope_at_distance(self.points, dist_m)

                if self.parcours_actif:
                    update_slope(dist_m, slope, lat, lon, ele)
                    publish_slope(slope)

                # Émet toujours la position (même en pause) pour que le front
                # affiche la position courante sur la carte et le profil
                self._emit(slope, lat, lon, ele, dist_m)

            except Exception as e:
                print(f"[SlopeController] Erreur : {e}")
            time.sleep(self.PUBLISH_INTERVAL)
