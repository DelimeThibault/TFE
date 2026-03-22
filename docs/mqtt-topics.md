# Contrat MQTT

## Échange entre le Pico 2 W et le nœud applicatif local (Mac de test puis Pi 4-5).

## Topics

| Topic                          | Sens       | Description                             | Fréquence cible      | QoS |
| ------------------------------ | ---------- | --------------------------------------- | -------------------- | --- |
| `bike/pico/telemetry/realtime` | Pico -> Pi | Données temps réel du vélo              | 5 Hz                 | 0   |
| `bike/pico/status`             | Pico -> Pi | État système du Pico                    | 1 Hz                 | 1   |
| `bike/pico/debug`              | Pico -> Pi | Messages de debug                       | Événementiel         | 0   |
| `bike/pi/control/simulation`   | Pi -> Pico | Paramètres de simulation, pente simulée | 2 à 5 Hz             | 1   |
| `bike/pi/control/resistance`   | Pi -> Pico | Consigne de résistance                  | Événementiel ou 2 Hz | 1   |
| `bike/pi/control/session`      | Pi -> Pico | Start, stop, pause, reset               | Événementiel         | 1   |
| `bike/pi/system/ping`          | Pi -> Pico | Heartbeat applicatif                    | Toutes les 2 s       | 0   |
| `bike/pico/system/pong`        | Pico -> Pi | Heartbeat retour                        | Toutes les 2 s       | 0   |

## Fichiers d'exemple de payload

Les exemples de payload sont stockés dans `contracts/mqtt-examples/` :

- `telemetry-realtime.json`
- `pico-status.json`
- `control-simulation.json`
- `control-resistance.json`
- `control-session.json`

## Règles de conception

- La télémétrie rapide privilégie la faible latence plutôt que la livraison garantie.
- Les commandes importantes utilisent un niveau de fiabilité supérieur.
- Les messages descendants incluent un champ `ttl_ms` pour pouvoir ignorer une commande périmée côté Pico.
- Les messages incluent un `session_id` pour rattacher les échanges à la session courante.
- Les messages incluent un compteur `seq` quand l’ordre ou le suivi de réception est utile.
