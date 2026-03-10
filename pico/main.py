# type: ignore
from machine import Pin, Timer
import time

button = Pin(15, Pin.IN, Pin.PULL_UP)
pulse_times = []
debounce_active = False


def debounce_end(t):
    global debounce_active
    debounce_active = False


def pulse_captured(pin):
    global debounce_active
    if not debounce_active:
        # On enregistre l'instant du pulse
        pulse_times.append(time.ticks_ms())
        debounce_active = True
        # Anti-rebond 50 ms
        Timer().init(mode=Timer.ONE_SHOT, period=50, callback=debounce_end)


# Interruption sur front descendant (bouton appuyé)
button.irq(trigger=Pin.IRQ_FALLING, handler=pulse_captured)

print("🚴 Compteur cadence vélo - JSON série USB")
print("GP15 (pin20). RPM fenêtre 5s. Ctrl+C pour arrêter.")


def calc_rpm():
    """Calcule le RPM sur une fenêtre glissante de 5 secondes."""
    now = time.ticks_ms()
    recent = [t for t in pulse_times if time.ticks_diff(now, t) < 5000]
    # 1 pulse = 1/2 tour -> 12 pulses pour 1 tour/s -> *12 pour RPM
    return len(recent) * 12


try:
    last_print = 0     # dernier affichage console
    last_json = 0      # dernier JSON envoyé sur USB

    while True:
        now = time.ticks_ms()

        # Console live (1x/sec pour debug)
        if time.ticks_diff(now, last_print) > 1000:
            rpm = calc_rpm()
            print(
                f"CADENCE: {rpm:4.0f} RPM | Pulses total: {len(pulse_times):4d} ",
                end="\r"
            )
            last_print = now

        # JSON série (toutes les 1000 ms pour la passerelle)
        if time.ticks_diff(now, last_json) > 1000:
            rpm = calc_rpm()
            total_pulses = len(pulse_times)
            json_data = (
                f'{{"cadence": {rpm:.0f}, '
                f'"timestamp": {now}, '
                f'"total_pulses": {total_pulses}}}'
            )
            print(json_data)  # Sortie série pour pySerial
            last_json = now

        time.sleep(0.05)

except KeyboardInterrupt:
    rpm = calc_rpm()
    print(f"\n✅ FIN | RPM: {rpm} | Total pulses: {len(pulse_times)}")
