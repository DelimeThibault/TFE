# type: ignore
from machine import I2C, SoftI2C, ADC, Pin, Timer, PWM
import sys
import utime
import network
import ubinascii
import machine

# --- Import modules affichage existants (inchangés) ---
# import lin_gauge
# import rad_gauge
# import tm1637_7_seg as tm1637
# from lcd_api import LcdApi
# from pico_i2c_lcd import I2cLcd

# --- Import MQTT ---
from umqtt.simple import MQTTClient

# --- Import config Wi-Fi + HiveMQ (à créer : config.py) ---
import config

# =============================================================
# INITIALISATION MATÉRIEL (CODE ORIGINAL - INCHANGÉ)
# =============================================================

utime.sleep(1)

SDA_PIN = 16
SCL_PIN = 17
I2C_ADDR = 0x26
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

sda = Pin(SDA_PIN)
scl = Pin(SCL_PIN)
i2c = SoftI2C(sda=sda, scl=scl, freq=400000)
# lcd  = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

# Displays 7 segments (inchangés)
# p_out_num_disp  = tm1637.TM1637(clk=Pin(2, Pin.OUT), dio=Pin(3, Pin.OUT))
# p_in_num_disp   = tm1637.TM1637(clk=Pin(0, Pin.OUT), dio=Pin(3, Pin.OUT))
# energy_num_disp = tm1637.TM1637(clk=Pin(1, Pin.OUT), dio=Pin(3, Pin.OUT))
# p_out_num_disp.show('out ')
# p_in_num_disp.show('in ')
# energy_num_disp.show('enrj')

# Boutons et contrôle résistance (inchangés)
btn1 = Pin(13, Pin.IN, Pin.PULL_DOWN)
btn2 = Pin(14, Pin.IN, Pin.PULL_DOWN)
bike_btn1 = Pin(19, Pin.IN, Pin.PULL_UP)
bike_btn2 = Pin(20, Pin.IN, Pin.PULL_UP)
bike_r_dir = Pin(22, Pin.OUT)
bike_r_en = PWM(Pin(21), freq=1000)

# Relais alimentation (inchangé)
relay_pin = Pin(15, Pin.OUT)
relay_pin.value(1)  # Allumé au démarrage

utime.sleep(3)
# p_out_num_disp.show(' ')
# p_in_num_disp.show(' ')
# energy_num_disp.show(' ')

# ADC courant (inchangé)
LSB_TO_AMPS = 0.008171500
F_ECH_HS = 786
F_ECH_LS = 1
max_bat = 20  # Wh


def get_current_u16():
    adc = ADC(Pin(28))
    return adc.read_u16() >> 4


# =============================================================
# ADC RÉSISTANCE (depuis meca_res.py - partagé)
# On réutilise get_res_pot() de meca_res pour lire la position
# de l'aimant en Volts (0.40 → 1.41)
# =============================================================
adc_resistance = ADC(Pin(26))


def get_res_pot():
    """
    Lit le potentiomètre de résistance (GP26).
    Retourne la position aimant en Volts : 0.40 (facile) → 1.41 (difficile).
    Identique à la fonction de meca_res.py.
    """
    return (adc_resistance.read_u16() * 3.3) / 65535


# =============================================================
# VARIABLES GLOBALES
# =============================================================
last_time = 0
T_rotation = 0  # Période rotation en µs
speed = 0  # Vitesse km/h
speed_rpm = 0  # Cadence RPM
wheel_circ = 1.85  # Circonférence roue (m)
debounce_time = 75000

i_sum = 0
i_sum_of_squares = 0
int_count = 0
i_rms = 0
p_out = 0
p_in = 0
since_last_turn = 0
debounce = 1
energy = max_bat  # Wh

# Position aimant (set_point partagé avec meca_res via boutons)
# On lit directement get_res_pot() → valeur réelle mesurée
bike_r_set_points = [400, 600, 800]
bike_r_set_point_index = 0
bike_r_set_point = bike_r_set_points[bike_r_set_point_index]

mqtt_seq = 0

# =============================================================
# NOUVEAUTÉ TFE : COEFFICIENTS PUISSANCE PAR POSITION AIMANT
# Source : régression P = a1*c + a2*c² (fit_intercept=False)
# Mesurée empiriquement sur le vélo avec différentes positions
# =============================================================
POWER_COEFFS = {
    0.40: (0.5093, 0.003693),
    0.60: (0.6383, 0.005740),
    0.80: (1.0239, 0.009450),
    1.00: (1.4186, 0.016663),
    1.22: (1.7624, 0.034600),
    1.41: (3.5368, 0.036075),
}
POSITIONS = sorted(POWER_COEFFS.keys())  # [0.40, 0.60, 0.80, 1.00, 1.22, 1.41]


# =============================================================
# NOUVEAUTÉ TFE : INTERPOLATION LINÉAIRE DES COEFFICIENTS
# Si la position aimant est entre deux valeurs du tableau,
# on interpole a1 et a2 proportionnellement.
# =============================================================
def interpolate_coeffs(pos):
    """
    Retourne (a1, a2) interpolés selon la position aimant.
    Clamp aux bornes si hors plage [0.40, 1.41].
    """
    if pos <= POSITIONS[0]:
        return POWER_COEFFS[POSITIONS[0]]
    if pos >= POSITIONS[-1]:
        return POWER_COEFFS[POSITIONS[-1]]
    for i in range(len(POSITIONS) - 1):
        p_low = POSITIONS[i]
        p_high = POSITIONS[i + 1]
        if p_low <= pos <= p_high:
            a1_low, a2_low = POWER_COEFFS[p_low]
            a1_high, a2_high = POWER_COEFFS[p_high]
            t = (pos - p_low) / (p_high - p_low)
            a1 = a1_low + t * (a1_high - a1_low)
            a2 = a2_low + t * (a2_high - a2_low)
            return (a1, a2)


# =============================================================
# NOUVEAUTÉ TFE : CALCUL PUISSANCE ESTIMÉE
# Formule : P = a1 * cadence + a2 * cadence²
# =============================================================
def calc_puissance(cadence_rpm, pos):
    """
    Calcule la puissance en Watts selon le modèle de régression.
    - cadence_rpm : RPM mesuré par le reed switch
    - pos         : position aimant en Volts (lue par get_res_pot)
    """
    a1, a2 = interpolate_coeffs(pos)
    return round(a1 * cadence_rpm + a2 * (cadence_rpm**2), 1)


# =============================================================
# INTERRUPTIONS ORIGINALES (INCHANGÉES)
# =============================================================
timer1 = Timer()
timer2 = Timer()


def hs_interrupt(timer):
    """
    Interruption haute fréquence (F_ECH_HS Hz).
    Mesure courant RMS, calcule p_out et énergie.
    Code original conservé intacte.
    """
    global int_count, i_sum, i_sum_of_squares, i_rms
    global p_out, p_in, energy, since_last_turn, debounce

    i_inst = get_current_u16()
    i_sum += i_inst
    i_sum_of_squares += i_inst**2
    int_count += 1

    if reed_switch_pin.value():
        since_last_turn = 0
    else:
        since_last_turn += 1
        if since_last_turn > 10:
            debounce = 1


def ls_interrupt(timer):
    """
    Interruption basse fréquence (F_ECH_LS Hz).
    Calcule vitesse, puissance, énergie.
    Code original conservé intact.
    """
    global speed, speed_rpm, p_in, p_out, energy
    global i_rms, i_sum, i_sum_of_squares, int_count

    if T_rotation > 0:
        if T_rotation > 5000000:
            speed = 0
            speed_rpm = 0
            p_in = 0
        else:
            speed = wheel_circ / (T_rotation / 1e6) * 3.6  # km/h
            speed_rpm = 60e6 / T_rotation  # RPM
            p_in = (2.47862037 * speed + 0.10765438 * speed**2) * 9

    if int_count > 0:
        i_dc = i_sum / int_count
        i_av_sum_sq = i_sum_of_squares / int_count
        int_count = 0
        i_sum = 0
        i_sum_of_squares = 0

        i_rms = (abs(i_av_sum_sq - i_dc**2)) ** 0.5 * LSB_TO_AMPS
        if i_rms < 0.015:
            i_rms = 0

        p_out = i_rms * 230
        energy += (p_in - p_out) / 3600 / F_ECH_LS
        if energy <= 0:
            energy = 0
            relay_pin.value(0)
            p_out = 0
        else:
            relay_pin.value(1)


def reed_switch_callback(pin):
    """
    Callback reed switch : mesure T_rotation en µs.
    Code original conservé intact.
    """
    global last_time, T_rotation, debounce
    current_time_cb = utime.ticks_us()
    if debounce and reed_switch_pin.value():
        T_rotation = current_time_cb - last_time
        last_time = current_time_cb
        debounce = 0


reed_switch_pin = Pin(12, Pin.IN, Pin.PULL_UP)  # Adapte le pin si différent
reed_switch_pin.irq(trigger=Pin.IRQ_RISING, handler=reed_switch_callback)

timer1.init(freq=F_ECH_HS, mode=Timer.PERIODIC, callback=hs_interrupt)
timer2.init(freq=F_ECH_LS, mode=Timer.PERIODIC, callback=ls_interrupt)


# =============================================================
# NOUVEAUTÉ TFE : CONNEXION WI-FI
# =============================================================
def connect_wifi():
    """
    Connecte le Pico 2 W au Wi-Fi défini dans config.py.
    Tente pendant 20 secondes avant de reset.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    print("📶 Connexion Wi-Fi...")
    for _ in range(20):
        if wlan.isconnected():
            print(f"✅ Wi-Fi OK | IP: {wlan.ifconfig()[0]}")
            return True
        utime.sleep(1)
    print("❌ Wi-Fi échec")
    return False


# =============================================================
# NOUVEAUTÉ TFE : CONNEXION MQTT (Sur Mac)
# =============================================================
def connect_mqtt():
    """
    Connecte le Pico au broker MQTT local Mosquitto.
    """
    client_id = ubinascii.hexlify(machine.unique_id())
    client = MQTTClient(
        client_id=client_id,
        server=config.MQTT_BROKER,
        port=config.MQTT_PORT,
        user=config.MQTT_USER if config.MQTT_USER else None,
        password=config.MQTT_PASSWORD if config.MQTT_PASSWORD else None,
        keepalive=60,
    )
    client.connect()
    print("✅ MQTT local connecté")
    return client


def publish_status(mqtt_client, last_error=None):
    payload = (
        f'{{"session_id":"{config.SESSION_ID}",'
        f'"ts_pico_ms":{utime.ticks_ms()},'
        f'"wifi":"connected",'
        f'"mqtt":"connected",'
        f'"firmware":"{config.FIRMWARE_VERSION}",'
        f'"uptime_s":{utime.ticks_ms() // 1000},'
        f'"last_error":{("null" if last_error is None else "\"" + str(last_error) + "\"")}}}'
    )
    mqtt_client.publish(config.MQTT_TOPIC_STATUS, payload.encode(), qos=1)


# =============================================================
# BOUCLE PRINCIPALE
# =============================================================
def main():
    global mqtt_seq

    # --- Connexion réseau ---
    if not connect_wifi():
        machine.reset()

    mqtt_client = connect_mqtt()
    last_mqtt_send = utime.ticks_ms()
    last_status_send = utime.ticks_ms()

    print("🚴 Session démarrée | MQTT actif")

    while True:
        now = utime.ticks_ms()

        # --- Publication télémétrie toutes les 200 ms ---
        # On ne bloque pas les interruptions : lecture simple des variables globales
        if utime.ticks_diff(now, last_mqtt_send) >= 200:
            pos = get_res_pot()
            cadence = round(speed_rpm, 1)
            puissance = calc_puissance(cadence, pos)

            mqtt_seq += 1

            payload = (
                f'{{"session_id":"{config.SESSION_ID}",'
                f'"seq":{mqtt_seq},'
                f'"ts_sensor_ms":{now},'
                f'"cadence_rpm":{cadence},'
                f'"speed_kmh":{round(speed, 1)},'
                f'"resistance_v":{round(pos, 3)},'
                f'"power_w":{puissance},'
                f'"energy_wh":{round(energy, 2)},'
                f'"system_state":"running"}}'
            )

            try:
                mqtt_client.publish(config.MQTT_TOPIC_REALTIME, payload.encode(), qos=0)
                print(
                    f"📡 {cadence}RPM | {round(pos, 2)}V | "
                    f"{puissance}W | {round(speed, 1)}km/h"
                )
            except Exception as e:
                print(f"❌ MQTT erreur télémétrie: {e} → reconnexion")
                try:
                    mqtt_client = connect_mqtt()
                except Exception:
                    machine.reset()

            last_mqtt_send = now

        # --- Publication statut toutes les 1000 ms ---
        if utime.ticks_diff(now, last_status_send) >= 1000:
            try:
                publish_status(mqtt_client)
            except Exception as e:
                print(f"❌ MQTT erreur statut: {e} → reconnexion")
                try:
                    mqtt_client = connect_mqtt()
                    publish_status(mqtt_client)
                except Exception:
                    machine.reset()

            last_status_send = now

        utime.sleep(0.05)  # 50 ms, laisse du temps CPU sans impacter les IRQ


if __name__ == "__main__":
    main()
