import json
import time
import requests
import serial
from serial.tools import list_ports

# URL de ton API en production
API_URL = "https://tfe-production-54d0.up.railway.app/api/cadence"


def find_pico_port():
    """Détecte automatiquement le port du Pico (usbmodem), sinon demande à l'utilisateur."""
    ports = list(list_ports.comports())
    for p in ports:
        if "usbmodem" in p.device:
            print(f"✅ Pico sur {p.device}")
            return p.device
    manual = input("Port Pico (ex: /dev/cu.usbmodem11301) : ").strip()
    return manual


def main():
    port = find_pico_port()
    ser = serial.Serial(port, baudrate=115200, timeout=0.1)

    session = requests.Session()

    # Pré-warm du backend (pour réveiller Railway)
    print("🔥 Pré-warm du serveur...")
    try:
        session.get(API_URL.replace("/api/cadence", "/"), timeout=5)
        print("✅ Pré-warm OK")
    except requests.RequestException as e:
        print(f"⚠️ Pré-warm échoué : {e}")

    buffer = ""
    print("🚀 Gateway live | limité en fréquence HTTP pour éviter la latence")

    last_http = 0.0         # timestamp du dernier POST HTTP
    min_http_interval = 0.35  # intervalle minimum entre deux POST (en secondes)

    while True:
        try:
            # Lecture non bloquante du port série
            chunk = ser.read(128) or b""
            if chunk:
                buffer += chunk.decode(errors="ignore")

            # Parsing robuste : extrait TOUS les JSON complets dans le buffer
            i = 0
            while i < len(buffer):
                if buffer[i] == "{":
                    try:
                        # Cherche la fin du JSON en comptant les accolades
                        depth = 1
                        j = i + 1
                        while j < len(buffer) and depth > 0:
                            if buffer[j] == "{":
                                depth += 1
                            elif buffer[j] == "}":
                                depth -= 1
                            j += 1

                        if depth == 0:
                            # JSON complet trouvé
                            json_str = buffer[i:j]
                            data = json.loads(json_str)

                            now = time.time()
                            # On ne POST que si le dernier POST est assez ancien
                            if now - last_http >= min_http_interval:
                                last_http = now
                                t_http = time.time()
                                try:
                                    resp = session.post(
                                        API_URL,
                                        json=data,
                                        timeout=2.0,
                                    )
                                    t_http_end = time.time()
                                    # Affichage local (RPM + temps HTTP)
                                    cadence = data.get("cadence", "?")
                                    print(
                                        f"✅ {cadence} RPM | "
                                        f"HTTP {(t_http_end - t_http):.2f}s | "
                                        f"Status {resp.status_code}"
                                    )
                                except requests.RequestException as e:
                                    print(f"⚠️ Erreur HTTP : {e}")

                            # Passe au JSON suivant (juste après j)
                            i = j
                        else:
                            # JSON incomplet, on attend plus de données
                            break

                    except json.JSONDecodeError:
                        # Caractère corrompu -> on avance d'un caractère
                        i += 1
                else:
                    i += 1

            # On garde seulement le reste non parsé dans le buffer
            buffer = buffer[i:]

            time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n🛑 Stop par l'utilisateur")
            break

    ser.close()


if __name__ == "__main__":
    main()
