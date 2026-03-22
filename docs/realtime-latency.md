# Mesure de latence temps réel

## Afficher dans l’interface web la latence entre la production d’une donnée sur le vélo et sa réception dans l’interface.

## Chaîne de mesure

1. Le Pico ajoute `ts_sensor_ms` dans chaque message de télémétrie.
2. Le service applicatif local note `ts_app_rx_ms` lors de la réception MQTT.
3. L’interface web note `ts_ui_rx_ms` lorsqu’elle reçoit la donnée temps réel.

## Indicateurs affichés

- `latency_sensor_to_app_ms`
- `latency_end_to_end_ms`

## Calculs

- `latency_sensor_to_app_ms = ts_app_rx_ms - ts_sensor_ms`
- `latency_end_to_end_ms = ts_ui_rx_ms - ts_sensor_ms`

## Seuils d’affichage

- Vert : inférieur à 400 ms
- Orange : entre 400 ms et 1000 ms
- Rouge : supérieur à 1000 ms

## Hypothèses de départ

- Le Pico publie la télémétrie temps réel toutes les 200 ms.
- La session courante est uniquement maintenue en mémoire dans le service applicatif.
