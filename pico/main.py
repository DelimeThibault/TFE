from machine import I2C, SoftI2C, ADC, Pin, Timer, PWM
import sys
import time
import utime
import network
import ubinascii
import machine


import lin_gauge
import rad_gauge
import tm1637_7_seg as tm1637
import power_model


from lcd_api import LcdApi
from pico_i2c_lcd import I2cLcd


from umqtt.simple import MQTTClient
import config


time.sleep(1)


# =============================================================
# I2C / LCD
# =============================================================
SDA_PIN = 16
SCL_PIN = 17
I2C_NUMMER = 0


sda = Pin(SDA_PIN)
scl = Pin(SCL_PIN)
i2c = I2C(I2C_NUMMER, sda=sda, scl=scl, freq=400000)
i2c = SoftI2C(sda=sda, scl=scl, freq=400000)
print("I2C address:")
print(i2c.scan(), " (decimal)")
if len(i2c.scan()) > 0:
    print(hex(i2c.scan()[0]), " (hex)")


I2C_ADDR = 0x26
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16


lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)


# =============================================================
# AFFICHEURS 7 SEGMENTS
# =============================================================
p_out_num_disp = tm1637.TM1637(clk=Pin(2, Pin.OUT), dio=Pin(3, Pin.OUT))
p_in_num_disp = tm1637.TM1637(clk=Pin(0, Pin.OUT), dio=Pin(1, Pin.OUT))
energy_num_disp = tm1637.TM1637(clk=Pin(1, Pin.OUT), dio=Pin(3, Pin.OUT))
p_out_num_disp.show("out ")
p_in_num_disp.show("in  ")
energy_num_disp.show("enrj")


# =============================================================
# BOUTONS
# =============================================================
btn1 = Pin(13, Pin.IN, Pin.PULL_DOWN)
btn2 = Pin(14, Pin.IN, Pin.PULL_DOWN)


bike_btn1 = Pin(19, Pin.IN, Pin.PULL_UP)
bike_btn2 = Pin(20, Pin.IN, Pin.PULL_UP)


# =============================================================
# MOTEUR RESISTANCE
# =============================================================
dir = Pin(22, Pin.OUT)
en = PWM(21, freq=50)


prev_res_pot = 1.1
duty = 0
set_point_ok = 0
sum_of_errors = 0


# =============================================================
# ADC RESISTANCE — lecture initiale avant tout
# On lit la position physique du potentiomètre au démarrage
# pour éviter que le PID force le moteur dès le boot.
# =============================================================
adc = ADC(Pin(26))


def get_res_pot():
    return (adc.read_u16() * 3.3) / 65535


_boot_pot = get_res_pot()
gear_setpoint = round(max(0.4, min(1.1, round(_boot_pot / 0.1) * 0.1)), 1)


# =============================================================
# BRAQUET / PENTE / VITESSE SIMULEE
# =============================================================
slope_pct = 0.0
slope_source = "none"
slope_offset = 0.0
speed_sim = 0.0


SLOPE_RES_COEFF = 0.025
SLOPE_RES_MAX = 0.35


GEAR_MIN = 0.4
GEAR_MAX = 1.1
set_point = gear_setpoint


# Modèle simplifié de vitesse simulée.
# K_SPEED  : vitesse de base — augmenter si trop lente, diminuer si trop rapide.
# K_SLOPE  : réduction par % de pente (ex: 0.8 = -0.8% de vitesse par % de pente).
# K_INERTIE: réactivité de la vitesse (0.3 = souple, 0.7 = réponse rapide).
# DECEL    : décélération en km/h par seconde quand le cycliste s'arrête.
K_SPEED = 3.20
K_SLOPE = 5.0
K_INERTIE = 0.30
DECEL = 1.5


# =============================================================
# GAINS PI
# =============================================================
kp = 100000
ki = 7000
MAX_DUTY = 52000
F_ECH_LS = 2
MAX_SUM_ERRORS = (65000 / ki) / F_ECH_LS


# Filtre EMA sur la cadence — lisse les oscillations dues aux
# irrégularités mécaniques du pédalage (un seul aimant sur le pédalier).
EMA_CADENCE = 0.70
_ema_cadence = 0.0


# =============================================================
# VARIABLES MQTT
# =============================================================
mqtt_active = False
mqtt_client = None
mqtt_seq = 0
epoch_offset_ms = None
last_timebase_seq = 0
last_timebase_rx_ms = 0


dernier_temps_appui = 0


# =============================================================
# INTERRUPTIONS BOUTONS VELO
# =============================================================
def increase_bike_r(pin):
    global gear_setpoint, dernier_temps_appui, set_point_ok, sum_of_errors
    temps_actuel = time.ticks_ms()
    set_point_ok = 0
    if time.ticks_diff(temps_actuel, dernier_temps_appui) > 400:
        if gear_setpoint < GEAR_MAX:
            gear_setpoint = round(gear_setpoint + 0.1, 1)
            sum_of_errors = 0
        dernier_temps_appui = temps_actuel


def decrease_bike_r(pin):
    global gear_setpoint, dernier_temps_appui, set_point_ok, sum_of_errors
    temps_actuel = time.ticks_ms()
    set_point_ok = 0
    if time.ticks_diff(temps_actuel, dernier_temps_appui) > 400:
        if gear_setpoint > GEAR_MIN:
            gear_setpoint = round(gear_setpoint - 0.1, 1)
            sum_of_errors = 0
        dernier_temps_appui = temps_actuel


bike_btn1.irq(trigger=Pin.IRQ_FALLING, handler=increase_bike_r)
bike_btn2.irq(trigger=Pin.IRQ_FALLING, handler=decrease_bike_r)


# =============================================================
# RELAIS
# =============================================================
relay_pin = Pin(15, Pin.OUT)


def power_on_off(on_off):
    relay_pin.value(on_off)


power_on_off(1)
time.sleep(3)


p_out_num_disp.show("    ")
p_in_num_disp.show("    ")
energy_num_disp.show("    ")


# =============================================================
# MESURE COURANT / ENERGIE
# =============================================================
LSB_TO_AMPS = 0.008171500
F_ECH_HS = 786
max_bat = 20


def get_current_u16():
    adc = ADC(Pin(28))
    return adc.read_u16() >> 4


timer1 = Timer()
timer2 = Timer()


# Initialisé au temps courant pour éviter un faux T_rotation au démarrage.
last_time = time.ticks_us()
T_rotation = 0
speed = 0
speed_rpm = 0
wheel_circ = 1.85


i_sum = 0
i_sum_of_squares = 0
int_count = 0
i_rms = 0
p_out = 0
p_in = 0
since_last_turn = 0
debounce = 1
energy = max_bat


# =============================================================
# INTERRUPTION HAUTE FREQUENCE — 786 Hz
# =============================================================
def hs_interrupt(timer):
    global int_count, i_sum, i_sum_of_squares
    i_inst = get_current_u16()
    i_sum += i_inst
    i_sum_of_squares += i_inst**2
    int_count += 1


def print_7_seg(display, value):
    display.number(int(value))


# =============================================================
# INTERRUPTION BASSE FREQUENCE — 2 Hz
# Ordre : cadence → énergie → set_point → speed_sim → PI résistance
# =============================================================
def ls_interrupt(timer):
    global int_count, i_sum, i_sum_of_squares, p_out, p_in, energy
    global last_time, T_rotation, speed, speed_rpm
    global prev_res_pot, sum_of_errors, duty, set_point_ok, set_point, i_rms
    global speed_sim, slope_offset
    global _ema_cadence

    dt = 1.0 / F_ECH_LS

    # --- 1. Cadence ---
    time_since_last_reed = time.ticks_diff(time.ticks_us(), last_time)

    if time_since_last_reed > 3000000:
        speed = 0
        speed_rpm = 0
        p_in = 0
        _ema_cadence = 0.0
    elif T_rotation > 0 and time_since_last_reed < T_rotation * 2:
        raw_rpm = 60.0 * 1e6 / T_rotation
        _ema_cadence = EMA_CADENCE * raw_rpm + (1.0 - EMA_CADENCE) * _ema_cadence
        speed_rpm = _ema_cadence
        speed = wheel_circ / (T_rotation / 1e6) * 3.6
        p_in = power_model.compute(prev_res_pot, speed_rpm)

    # --- 2. Courant / Energie ---
    if int_count > 0:
        i_dc = i_sum / int_count
        i_av_sum_of_squares = i_sum_of_squares / int_count
        int_count = 0
        i_sum = 0
        i_sum_of_squares = 0
        i_rms = (abs(i_av_sum_of_squares - i_dc**2)) ** 0.5 * LSB_TO_AMPS
        if i_rms < 0.050:
            i_rms = 0
        p_out = i_rms * 230
        energy += (p_in - p_out) / 3600 / F_ECH_LS
        if energy <= 0:
            energy = 0
            power_on_off(0)
            p_out = 0
        else:
            power_on_off(1)

    # --- 3. Consigne résistance = braquet utilisateur + offset pente ---
    slope_offset = min(slope_pct * SLOPE_RES_COEFF, SLOPE_RES_MAX)
    sp_raw = gear_setpoint + slope_offset
    if sp_raw > 1.3:
        sp_raw = 1.3
    if sp_raw < 0.4:
        sp_raw = 0.4
    set_point = sp_raw

    # --- 4. Vitesse simulée ---
    if p_in > 0:
        slope_factor = 1.0 + K_SLOPE * ((max(0.0, slope_pct) / 100.0) ** 0.7)
        speed_target = K_SPEED * (p_in**0.5) / slope_factor
        speed_sim = speed_sim + (speed_target - speed_sim) * K_INERTIE
    else:
        speed_sim = max(0.0, speed_sim - DECEL * dt)

    # --- 5. Boucle PI résistance ---
    res_pot = get_res_pot()
    duty = 0

    if set_point_ok > 3:
        en.duty_u16(0)
        sum_of_errors = 0
        print(
            f"m : {res_pot:3.3f} sp : {set_point:3.1f}  diff : {set_point - res_pot: 3.3f}  OK"
        )
    else:
        err = res_pot - set_point
        sum_of_errors += err
        if sum_of_errors > MAX_SUM_ERRORS:
            sum_of_errors = MAX_SUM_ERRORS
        if sum_of_errors < -MAX_SUM_ERRORS:
            sum_of_errors = -MAX_SUM_ERRORS

        if abs(err) < 0.02:
            set_point_ok += 1
            print(err)
        else:
            set_point_ok = 0
            P = err * kp
            I = sum_of_errors * ki
            if I > 65000:
                I = 65000
            if I < -65000:
                I = -65000
            command = P + I
            if abs(command) > 3000:
                duty = int(abs(command))
                if duty > MAX_DUTY:
                    duty = MAX_DUTY
                if command < 0:
                    en.duty_u16(0)
                    dir.value(1)
                    en.duty_u16(duty)
                if command > 0:
                    en.duty_u16(0)
                    dir.value(0)
                    en.duty_u16(duty)
            else:
                en.duty_u16(0)
            print(
                f"m : {res_pot:3.3f} sp : {set_point:3.1f}  diff : {set_point - res_pot: 3.3f},  "
                f"duty : {duty: 6.0f}  I: {I: 6.0f}  P: {P: 6.0f}  cmd: {command: 6.0f}  ok:{set_point_ok}"
            )

    prev_res_pot = res_pot


# =============================================================
# REED SWITCH — détection cadence pédalier
# =============================================================
def reed_switch_callback(pin):
    global last_time, T_rotation
    current_time_cb = time.ticks_us()

    delta = time.ticks_diff(current_time_cb, last_time)

    if delta < 80000:
        return

    if delta > 5000000:
        last_time = current_time_cb
        return

    T_rotation = delta
    last_time = current_time_cb


reed_switch_pin = Pin(18, Pin.IN, Pin.PULL_UP)
reed_switch_pin.irq(handler=reed_switch_callback, trigger=Pin.IRQ_RISING)

timer1.init(freq=F_ECH_HS, mode=Timer.PERIODIC, callback=hs_interrupt)
timer2.init(freq=F_ECH_LS, mode=Timer.PERIODIC, callback=ls_interrupt)


# =============================================================
# Wi-Fi / MQTT
# =============================================================
def try_connect_wifi(timeout_s=10):
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if wlan.isconnected():
            print(f"✅ Wi-Fi déjà connecté | IP: {wlan.ifconfig()[0]}")
            return True
        print("📶 Tentative Wi-Fi...")
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        timeout = timeout_s * 2
        while not wlan.isconnected() and timeout > 0:
            utime.sleep(0.5)
            timeout -= 1
        if wlan.isconnected():
            print(f"✅ Wi-Fi OK | IP: {wlan.ifconfig()[0]}")
            return True
        else:
            print("⚠️  Wi-Fi non disponible → mode standalone")
            wlan.active(False)
            return False
    except Exception as e:
        print(f"⚠️  Wi-Fi erreur ({e}) → mode standalone")
        return False


def try_connect_mqtt():
    try:
        client_id = ubinascii.hexlify(machine.unique_id())
        client = MQTTClient(
            client_id=client_id,
            server=config.MQTT_BROKER,
            port=config.MQTT_PORT,
            user=config.MQTT_USER,
            password=config.MQTT_PASSWORD,
            keepalive=60,
        )
        client.set_callback(mqtt_callback)
        client.connect()
        client.subscribe(config.MQTT_TOPIC_SLOPE.encode())
        print("✅ MQTT connecté au broker", config.MQTT_BROKER)
        return client
    except Exception as e:
        print(f"⚠️  MQTT non disponible ({e}) → mode standalone")
        return None


def publish_status(client, last_error=None):
    try:
        last_error_json = (
            "null"
            if last_error is None
            else '"' + str(last_error).replace('"', "'") + '"'
        )
        payload = (
            f'{{"session_id":"{config.SESSION_ID}",'
            f'"ts_pico_ms":{utime.ticks_ms()},'
            f'"wifi":"connected",'
            f'"mqtt":"connected",'
            f'"firmware":"{config.FIRMWARE_VERSION}",'
            f'"uptime_s":{utime.ticks_ms() // 1000},'
            f'"last_error":{last_error_json}}}'
        )
        client.publish(config.MQTT_TOPIC_STATUS, payload.encode(), qos=1)
    except Exception:
        pass


def mqtt_callback(topic, msg):
    global epoch_offset_ms, last_timebase_seq, last_timebase_rx_ms
    global slope_pct, slope_source
    try:
        topic = topic.decode()
        msg = msg.decode()
    except Exception:
        return
    try:
        import ujson as json
    except ImportError:
        import json

    if topic == config.MQTT_TOPIC_TIMEBASE:
        try:
            data = json.loads(msg)
            ts_app_ms = int(data.get("ts_app_ms", 0))
            seq = int(data.get("seq", 0))
            pico_now = utime.ticks_ms()
            epoch_offset_ms = ts_app_ms - pico_now
            last_timebase_seq = seq
            last_timebase_rx_ms = pico_now
            print("🕒 Timebase reçue | offset =", epoch_offset_ms)
        except Exception as e:
            print("❌ Erreur timebase:", e)

    elif topic == config.MQTT_TOPIC_SLOPE:
        try:
            data = json.loads(msg)
            slope_pct = float(data.get("slope_pct", 0.0))
            slope_source = "remote"
            print(f"⛰️  Pente reçue : {slope_pct:.1f}%")
        except Exception as e:
            print("❌ Erreur slope:", e)


# =============================================================
# BOUCLE PRINCIPALE
# =============================================================
lcd.backlight_on()
lcd.clear()
lcd.move_to(0, 0)

lcd.putstr("Connexion WiFi..")
wifi_ok = try_connect_wifi(timeout_s=10)
mqtt_client = try_connect_mqtt() if wifi_ok else None
mqtt_active = mqtt_client is not None

lcd.clear()
lcd.move_to(0, 0)
if mqtt_active:
    lcd.putstr("WiFi+MQTT OK    ")
    print("🚴 Mode connecté | MQTT actif")
else:
    lcd.putstr("Mode standalone ")
    print("🚴 Mode standalone | pas de MQTT")

utime.sleep(1)
lcd.clear()

last_mqtt_send = utime.ticks_ms()
last_status_send = utime.ticks_ms()
last_display_upd = utime.ticks_ms()
last_reconnect_attempt = 0
last_print_upd = utime.ticks_ms()
RECONNECT_INTERVAL_MS = 150000


try:
    while 1:
        now = utime.ticks_ms()

        if mqtt_active:
            try:
                mqtt_client.check_msg()
            except Exception as e:
                print(f"❌ Réception MQTT erreur: {e} → MQTT désactivé")
                mqtt_active = False

        if (
            not mqtt_active
            and utime.ticks_diff(now, last_reconnect_attempt) >= RECONNECT_INTERVAL_MS
        ):
            print("🔄 Tentative reconnexion...")
            wifi_ok = try_connect_wifi(timeout_s=5)
            if wifi_ok:
                mqtt_client = try_connect_mqtt()
                mqtt_active = mqtt_client is not None
                if mqtt_active:
                    print("✅ Reconnexion réussie")
                    lcd.move_to(0, 0)
                    lcd.putstr("WiFi+MQTT OK    ")
                    utime.sleep_ms(800)
            last_reconnect_attempt = now

        if utime.ticks_diff(now, last_display_upd) >= 500:
            rad_gauge.set_powers(p_in, p_out)
            print_7_seg(p_out_num_disp, p_out)
            print_7_seg(p_in_num_disp, p_in)
            print_7_seg(energy_num_disp, energy)
            lin_gauge.set_value(energy / max_bat * 100 if max_bat > 0 else 0)

            if btn1.value() == 1:
                energy = 0
            if btn2.value() == 1:
                increase_to = (energy + 10) // 10 * 10
                if (increase_to - energy) < 1:
                    increase_to += 10
                energy = increase_to
                max_bat = energy

            lcd.move_to(0, 0)
            lcd.putstr("reste:{:4.2f} Wh".format(energy))
            lcd.move_to(0, 1)
            mode_str = "W" if mqtt_active else "S"
            lcd.putstr(
                "g:{:1.1f} {:4.1f}km/h {}".format(gear_setpoint, speed_sim, mode_str)[
                    :16
                ]
            )
            last_display_upd = now

        if mqtt_active and utime.ticks_diff(now, last_mqtt_send) >= 200:
            pos = get_res_pot()
            cadence = round(speed_rpm, 1)
            mqtt_seq += 1
            ts_epoch = (now + epoch_offset_ms) if epoch_offset_ms is not None else None

            payload = (
                f'{{"session_id":"{config.SESSION_ID}",'
                f'"seq":{mqtt_seq},'
                f'"ts_sensor_ms":{now},'
                f'"ts_sensor_epoch_ms":{("null" if ts_epoch is None else ts_epoch)},'
                f'"cadence_rpm":{cadence},'
                f'"speed_sim_kmh":{round(speed_sim, 1)},'
                f'"resistance_v":{round(pos, 3)},'
                f'"resistance_setpoint_v":{round(set_point, 3)},'
                f'"gear_setpoint_v":{round(gear_setpoint, 1)},'
                f'"slope_offset_v":{round(slope_offset, 3)},'
                f'"slope_pct":{round(slope_pct, 1)},'
                f'"slope_source":"{slope_source}",'
                f'"power_w":{round(p_in, 1)},'
                f'"p_out_w":{round(p_out, 1)},'
                f'"energy_wh":{round(energy, 2)},'
                f'"system_state":"running"}}'
            )

            try:
                mqtt_client.publish(config.MQTT_TOPIC_REALTIME, payload.encode(), qos=0)
                if utime.ticks_diff(now, last_print_upd) >= 1000:
                    print(
                        f"📡 {cadence}RPM | {round(pos, 2)}V sp:{round(set_point, 2)}V "
                        f"(g:{round(gear_setpoint,1)}+{round(slope_offset,2)}) | "
                        f"{round(p_in, 1)}W | sim:{round(speed_sim, 1)}km/h | "
                        f"pente:{slope_pct:.1f}%"
                    )
                    last_print_upd = now
            except Exception as e:
                print(f"❌ MQTT erreur télémétrie: {e} → MQTT désactivé")
                mqtt_active = False
            last_mqtt_send = now

        if mqtt_active and utime.ticks_diff(now, last_status_send) >= 5000:
            try:
                publish_status(mqtt_client)
            except Exception as e:
                print(f"❌ MQTT erreur statut: {e} → MQTT désactivé")
                mqtt_active = False
            last_status_send = now

        time.sleep_ms(50)

except Exception as e:
    print("\n-----------------------------------------")
    print("CRASH DÉTECTÉ ! Voici l'erreur :")
    sys.print_exception(e)
    print("-----------------------------------------\n")
    timer1.deinit()
    timer2.deinit()
    en.duty_u16(0)
    print("dinit")
