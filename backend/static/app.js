const socket = io();

const statusBadge = document.getElementById("status-badge");
const sessionIdEl = document.getElementById("session-id");
const cadenceEl = document.getElementById("cadence");
const speedEl = document.getElementById("speed");
const powerEl = document.getElementById("power");
const resistanceEl = document.getElementById("resistance");
const energyEl = document.getElementById("energy");
const systemStateEl = document.getElementById("system-state");
const latAppEl = document.getElementById("lat-app");
const latE2EEl = document.getElementById("lat-e2e");

// Dernières valeurs reçues — mises à jour à chaque message MQTT (200ms)
let lastData = null;

// Throttle d'affichage : on ne rafraîchit l'écran qu'une fois par seconde
const DISPLAY_INTERVAL_MS = 1000;

function setConnected(isConnected) {
  statusBadge.textContent = isConnected ? "Connecté" : "Déconnecté";
  statusBadge.classList.toggle("ok", isConnected);
  statusBadge.classList.toggle("err", !isConnected);
}

function updateDisplay() {
  if (!lastData) return;
  const data = lastData;

  sessionIdEl.textContent = data.session_id ?? "--";
  cadenceEl.textContent =
    data.cadence_rpm !== undefined ? Math.round(data.cadence_rpm) : "--";
  speedEl.textContent =
    data.speed_sim_kmh !== undefined ? data.speed_sim_kmh.toFixed(1) : "--";
  powerEl.textContent =
    data.power_w !== undefined ? Math.round(data.power_w) : "--";
  resistanceEl.textContent =
    data.resistance_v !== undefined ? data.resistance_v.toFixed(2) : "--";
  energyEl.textContent =
    data.energy_wh !== undefined ? data.energy_wh.toFixed(2) : "--";
  systemStateEl.textContent = data.system_state ?? "--";

  if (data.ts_sensor_epoch_ms && data.ts_app_rx_ms) {
    latAppEl.textContent = `${data.ts_app_rx_ms - data.ts_sensor_epoch_ms} ms`;
    latE2EEl.textContent = `${Date.now() - data.ts_sensor_epoch_ms} ms`;
  } else {
    latAppEl.textContent = "--";
    latE2EEl.textContent = "--";
  }
}

// Réception des données : stockage uniquement, pas d'affichage direct
socket.on("realtime_update", (data) => {
  lastData = data;
});

socket.on("connect", () => setConnected(true));
socket.on("disconnect", () => setConnected(false));

// Rafraîchissement de l'affichage à intervalle fixe
setInterval(updateDisplay, DISPLAY_INTERVAL_MS);
