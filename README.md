# Transformation d’un vélo d’appartement en simulateur de parcours virtuels avec calcul de puissance.

## Description

Ce projet de TFE porte sur la conception d’un vélo d’appartement connecté basé sur une architecture locale embarquée.

L’architecture cible repose sur deux nœuds distincts :

- un **Raspberry Pi Pico 2 W**, chargé du temps réel embarqué, des mesures capteurs, de certains calculs locaux et du pilotage matériel ;
- un **Raspberry Pi 5**, chargé du broker MQTT local, de la logique applicative et de l’interface web.

## Structure du projet

- `pico/` : code embarqué MicroPython du Raspberry Pi Pico 2 W.
- `backend/` : service applicatif local et interface web temps réel.
- `contracts/` : exemples de payloads MQTT utilisés comme contrat d’échange.
- `docs/` : documentation technique de l’architecture, des topics MQTT et de la latence temps réel.
- `fichiers FIT/` : fichiers d’analyse et de calibration de la puissance.
- `Schémas/` : schémas d’architecture et de flux.

## Dépendances Python

Le projet utilise un environnement virtuel Python pour la partie backend locale.

### Création de l’environnement virtuel

```bash
python3 -m venv .venv
```

### Activation et installation

#### macOS

```bash
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Windows

```bash
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Dépendances système

Pour le broker MQTT local, le projet utilise **Mosquitto**.

### Installation sur macOS

Avec Homebrew :

```bash
brew update
brew install mosquitto
```

## Lancement du broker MQTT local

Dans un premier terminal :

```bash
mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf -v
```

Le broker écoute alors localement sur `localhost:1883`.

Pour écouter depuis le terminal (avec l'ip de l'host du broker MQTT) :

```bash
mosquitto_sub -h 172.20.10.2 -p 1883 -t "bike/#" -v
```

## Lancement de l’application locale

Dans un second terminal :

```bash
source .venv/bin/activate
python backend/app.py
```

L’interface web est ensuite accessible à l’adresse suivante :

```text
http://127.0.0.1:2500
```

## Test local sans Pico

Avant d’intégrer le Pico, il est possible de tester toute la chaîne locale en publiant manuellement un message MQTT.

Dans un troisième terminal :

```bash
mosquitto_pub -h localhost -p 1883 -t "bike/pico/telemetry/realtime" -m '{
  "session_id":"sess-001",
  "seq":1,
  "ts_sensor_ms":'"$(python3 -c 'import time; print(int(time.time()*1000))')"',
  "cadence_rpm":82.4,
  "speed_kmh":26.1,
  "resistance_v":0.812,
  "power_w":167.3,
  "energy_wh":14.82,
  "system_state":"running"
}'
```

Si tout fonctionne correctement :

- le backend reçoit le message via MQTT ;
- la session courante est mise à jour en mémoire ;
- l’interface web affiche immédiatement les valeurs ;
- la latence temps réel est calculée dans l’interface.

## Contrat MQTT

Les topics et les payloads de référence sont documentés dans :

- `docs/mqtt-topics.md`
- `docs/realtime-latency.md`
- `docs/architecture/mermaid-mqtt-flow.md`

Les exemples JSON sont stockés dans :

- `contracts/mqtt-examples/`

## Remarques d’architecture

- Le système fonctionne en **temps réel**.
- Aucune **base de données** n’est utilisée dans l’architecture actuelle.
- Aucune persistance durable n’est prévue pour les données de télémétrie.
- Seule la **session courante** est conservée en mémoire côté backend local.
- L’objectif est de maintenir une latence d’affichage inférieure à **1 seconde**.

## Calibration de la puissance

La puissance estimée utilisée côté Pico repose sur une calibration réalisée à partir de fichiers FIT.

Les scripts et fichiers associés se trouvent dans :

- `fichiers FIT/extract_fit.py`
- `fichiers FIT/minimal_extract_fit.py`

Cette calibration permet d’obtenir les coefficients utilisés dans le modèle de puissance embarqué.
