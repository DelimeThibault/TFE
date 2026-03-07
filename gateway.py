import json
import time
import requests
import serial
from serial.tools import list_ports

API_URL = "http://127.0.0.1:2500/api/cadence"  # Étape 3 : Flask écoutera ici

# ---------- Détection du port Pico sur Mac ----------

def find_pico_port():
    """
    Essaie de trouver automatiquement le port série du Pico.
    Affiche les ports trouvés si rien de clair.
    """
    ports = list(list_ports.comports())
    pico_candidates = []

    for p in ports:
        name = p.device  # ex: /dev/tty.usbmodem1101
        desc = p.description or ""
        hwid = p.hwid or ""

        # Heuristiques: usbmodem, Pico, BOOTSEL, etc.
        if "usbmodem" in name or "Pico" in desc or "RP2040" in hwid:
            pico_candidates.append(p)

    if len(pico_candidates) == 1:
        print(f"✅ Pico détecté sur : {pico_candidates[0].device}")
        return pico_candidates[0].device

    print("⚠ Impossible de détecter automatiquement le Pico.")
    print("Ports disponibles :")
    for p in ports:
        print(f"  - {p.device} | {p.description}")

    # Fallback : saisir manuellement
    manual = input("👉 Indique le port série du Pico (ex: /dev/tty.usbmodem1101) : ").strip()
    return manual

# ---------- Boucle principale ----------

def main():
    port = find_pico_port()

    # MicroPython via USB CDC est généralement à 115200 bauds sur Mac
    # timeout=1s pour ne pas bloquer indéfiniment sur readline.[web:27][web:18]
    ser = serial.Serial(port=port, baudrate=115200, timeout=1)
    print(f"🔌 Connecté au Pico sur {ser.port}")

    session = requests.Session()
    print(f"🌐 Passerelle active → POST vers {API_URL}")
    print("Ctrl+C pour arrêter.\n")

    while True:
        try:
            line_bytes = ser.readline()
            if not line_bytes:
                continue

            # bytes -> str, on garde seulement la partie JSON complète
            raw = line_bytes.decode(errors="ignore")

            # Exemple de raw possible :
            # 'CADENCE:  0 RPM ...\r{"cadence": 0, "timestamp": 160257, "total_pulses": 27}\r\n'
            start = raw.find('{')
            end = raw.rfind('}')

            if start == -1 or end == -1 or end <= start:
                # Pas de JSON complet dans cette ligne → on ignore
                continue

            line = raw[start:end+1].strip()

            # On ne garde que les lignes JSON bien formées
            if not (line.startswith("{") and line.endswith("}")):
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"❌ JSON invalide après extraction : {line} | Erreur: {e}")
                continue

            data["gateway_ts"] = time.time()

            try:
                resp = session.post(API_URL, json=data, timeout=0.5)
                if resp.status_code != 200:
                    print(f"⚠ Erreur HTTP {resp.status_code} → {resp.text}")
                else:
                    print(f"➡ POST ok : {data}")
            except requests.RequestException as e:
                print(f"🌐 Erreur de connexion API : {e}")


        except KeyboardInterrupt:
            print("\n🛑 Arrêt demandé par l'utilisateur.")
            break
        except Exception as e:
            print(f"🔥 Erreur inattendue : {e}")
            time.sleep(1)  # évite boucle folle en cas de bug

    ser.close()
    print("🔌 Port série fermé. Bye.")

if __name__ == "__main__":
    main()
