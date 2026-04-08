# Déploiement sur Raspberry Pi 5

## Architecture réseau

Le Raspberry Pi 5 crée un hotspot Wi-Fi (mode AP, WPA2 uniquement).
Le Pi Pico W s'y connecte comme client Wi-Fi classique (mode STA).

| Nœud           | Rôle                                     | IP            |
| -------------- | ---------------------------------------- | ------------- |
| Raspberry Pi 5 | Hotspot + Broker MQTT + Backend + UI web | 192.168.4.1   |
| Pi Pico W      | Capteurs + actionneur vélo               | 192.168.4.118 |

## Procédure d'installation

### 1. Mettre à jour le système

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install git python3 python3-pip python3-venv mosquitto mosquitto-clients -y
```

### 2. Créer le hotspot Wi-Fi (WPA2 uniquement)

```bash
sudo nmcli connection add \
  type wifi \
  con-name "VeloBike" \
  ifname wlan0 \
  ssid "VeloBike" \
  mode ap \
  ipv4.method shared \
  ipv4.addresses 192.168.4.1/24 \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "velotfe2026" \
  wifi-sec.proto rsn \
  wifi-sec.pairwise ccmp \
  wifi-sec.group ccmp

sudo nmcli connection up VeloBike
sudo nmcli connection modify VeloBike connection.autoconnect yes
```

Le forçage en WPA2 (RSN/CCMP) est nécessaire pour que le Pico W puisse se connecter. Sans ces paramètres, la négociation de sécurité échoue.

### 3. Vérifier que le hotspot est actif

```bash
nmcli connection show --active
ip addr show wlan0   # doit afficher 192.168.4.1
```

### 4. Configurer Mosquitto

Créer `/etc/mosquitto/conf.d/local.conf` :

```text
listener 1883
allow_anonymous true
```

```bash
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
```

Vérification :

```bash
ss -tlnp | grep 1883
# attendu : LISTEN 0 128 0.0.0.0:1883
```

### 5. Cloner le repo et installer les dépendances

```bash
git clone https://github.com/DelimeThibault/TFE.git tfe-velo
cd tfe-velo
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Lancer l'application

```bash
./start.sh
```

Interface web accessible depuis le Pico ou tout appareil connecté au hotspot :
`http://192.168.4.1:2500`
