# type:ignore
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
        pulse_times.append(time.ticks_ms())
        debounce_active = True
        Timer().init(mode=Timer.ONE_SHOT, period=50, callback=debounce_end)

button.irq(trigger=Pin.IRQ_FALLING, handler=pulse_captured)

print("🚴 Compteur cadence vélo - JSON série USB")
print("GP15 (pin20). RPM 5s fenêtre. Ctrl+C stop.")

def calc_rpm():
    now = time.ticks_ms()
    recent = [t for t in pulse_times if time.ticks_diff(now, t) < 5000]
    return len(recent) * 12  # *12 pour RPM (1 pulse = 1/2 tour)

try:
    last_print = 0
    last_json = 0
    while True:
        now = time.ticks_ms()
        
        # Console live (5x/sec pour debug)
        if time.ticks_diff(now, last_print) > 200:
            rpm = calc_rpm()
            print(f"CADENCE: {rpm:4.0f} RPM | Pulses total: {len(pulse_times):4d}   ", end='\r')
            last_print = now
        
        # JSON série (toutes les 200ms pour passerelle)
        if time.ticks_diff(now, last_json) > 200:
            rpm = calc_rpm()
            total_pulses = len(pulse_times)
            json_data = f'{{"cadence": {rpm:.0f}, "timestamp": {now}, "total_pulses": {total_pulses}}}'
            print(json_data)  # Sortie série lisible par pySerial
            last_json = now
        
        time.sleep(0.05)
        
except KeyboardInterrupt:
    rpm = calc_rpm()
    print(f"\n✅ FIN | RPM: {rpm} | Total pulses: {len(pulse_times)}")
