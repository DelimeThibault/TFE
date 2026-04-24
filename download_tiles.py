import math, os, urllib.request, time


def deg2tile(lat, lon, zoom):
    n = 2**zoom
    x = int((lon + 180) / 360 * n)
    y = int(
        (
            1
            - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat)))
            / math.pi
        )
        / 2
        * n
    )
    return x, y


LAT_MIN, LAT_MAX = 50.60, 50.75
LON_MIN, LON_MAX = 4.52, 4.72
TILE_DIR = "./backend/static/tiles"
headers = {"User-Agent": "VeloLLN-TFE/1.0"}

total_done = 0
for zoom in range(13, 18):
    x_min, y_max = deg2tile(LAT_MIN, LON_MIN, zoom)
    x_max, y_min = deg2tile(LAT_MAX, LON_MAX, zoom)
    count = (x_max - x_min + 1) * (y_max - y_min + 1)
    print(f"\nZoom {zoom} : {count} tuiles à télécharger")
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            path = f"{TILE_DIR}/{zoom}/{x}/{y}.png"
            if os.path.exists(path):
                continue
            os.makedirs(f"{TILE_DIR}/{zoom}/{x}", exist_ok=True)
            url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as r:
                    with open(path, "wb") as f:
                        f.write(r.read())
                total_done += 1
                print(f"  ✓ {zoom}/{x}/{y}", end="\r")
                time.sleep(0.1)
            except Exception as e:
                print(f"  ✗ Erreur {zoom}/{x}/{y}: {e}")

print(f"\n\nTerminé — {total_done} tuiles téléchargées dans {TILE_DIR}")
