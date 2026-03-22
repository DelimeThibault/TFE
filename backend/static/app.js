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

function setConnected(isConnected) {
  statusBadge.textContent = isConnected ? "Connecté" : "Déconnecté";
  statusBadge.classList.toggle("ok", isConnected);
  statusBadge.classList.toggle("err", !isConnected);
}

socket.on("connect", () => {
  setConnected(true);
});

socket.on("disconnect", () => {
  setConnected(false);
});

socket.on("realtime_update", (data) => {
  const now = Date.now();

  sessionIdEl.textContent = data.session_id ?? "--";
  cadenceEl.textContent = data.cadence_rpm ?? "--";
  speedEl.textContent = data.speed_kmh ?? "--";
  powerEl.textContent = data.power_w ?? "--";
  resistanceEl.textContent = data.resistance_v ?? "--";
  energyEl.textContent = data.energy_wh ?? "--";
  systemStateEl.textContent = data.system_state ?? "--";

  if (data.ts_sensor_ms && data.ts_app_rx_ms) {
    latAppEl.textContent = `${data.ts_app_rx_ms - data.ts_sensor_ms} ms`;
    latE2EEl.textContent = `${now - data.ts_sensor_ms} ms`;
  } else {
    latAppEl.textContent = "--";
    latE2EEl.textContent = "--";
  }
});
