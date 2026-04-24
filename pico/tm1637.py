"""
MicroPython TM1637 quad 7-segment LED display driver - PIO OPTIMIZED VERSION
Basé sur la librairie originale de Mike Causer, optimisé avec rp2.StateMachine
"""

__version__ = '2.0.2-pio-final'

import rp2
from micropython import const
from machine import Pin
from time import sleep_ms

TM1637_CMD1 = const(64)  # 0x40 data command
TM1637_CMD2 = const(192) # 0xC0 address command
TM1637_CMD3 = const(128) # 0x80 display control command
TM1637_DSP_ON = const(8) # 0x08 display on
TM1637_MSB = const(128)  # msb is the decimal point or the colon depending on your display

_SEGMENTS = bytearray(b'\x3F\x06\x5B\x4F\x66\x6D\x7D\x07\x7F\x6F\x77\x7C\x39\x5E\x79\x71\x3D\x76\x06\x1E\x76\x38\x55\x54\x3F\x73\x67\x50\x6D\x78\x3E\x1C\x2A\x76\x6E\x5B\x00\x40\x63')

# -----------------------------------------------------------------------------
# PROGRAMME ASSEMBLEUR PIO
# -----------------------------------------------------------------------------
@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_HIGH, 
    set_init=rp2.PIO.OUT_HIGH, 
    out_init=rp2.PIO.OUT_HIGH, 
    out_shiftdir=rp2.PIO.SHIFT_RIGHT
)
def _tm1637_pio():
    pull()                          # Récupère les données
    
    # --- GESTION DU START ---
    out(x, 1)                       
    jmp(not_x, "no_start")          
    set(pins, 0)    .side(1) [1]    # DIO passe à 0, CLK reste à 1
    set(pins, 0)    .side(0) [1]    # CLK passe à 0
    label("no_start")
    
    # --- ENVOI DES 8 BITS ---
    set(x, 7)                       
    label("bitloop")
    out(pins, 1)    .side(0)        # Sort 1 bit sur DIO
    nop()           .side(1) [1]    # CLK passe à 1
    jmp(x_dec, "bitloop") .side(0) [1] # CLK passe à 0, on boucle
    
    # --- GESTION DU ACK (LA CORRECTION EST ICI) ---
    set(pindirs, 0) .side(0) [1]    # DIO devient une ENTRÉE (on relâche la ligne pour le TM1637)
    nop()           .side(1) [2]    # Coup d'horloge (CLK passe à 1)
    set(pindirs, 1) .side(0) [1]    # DIO redevient une SORTIE (CLK repasse à 0)
    
    # --- GESTION DU STOP ---
    out(x, 1)                       
    jmp(not_x, "no_stop")           
    set(pins, 0)    .side(0) [1]    # S'assure que DIO = 0 pendant CLK = 0
    set(pins, 0)    .side(1) [1]    # CLK passe à 1
    set(pins, 1)    .side(1) [1]    # DIO passe à 1 (Condition STOP)
    label("no_stop")


class TM1637(object):
    def __init__(self, clk, dio, brightness=7, sm_id=0):
        self.clk = clk
        self.dio = dio

        if not 0 <= brightness <= 7:
            raise ValueError("Brightness out of range")
        self._brightness = brightness

        # freq=50000 simule parfaitement les délais logiciels d'origine (10us)
        self.sm = rp2.StateMachine(
            sm_id, 
            _tm1637_pio, 
            freq=50000, 
            sideset_base=self.clk, 
            set_base=self.dio, 
            out_base=self.dio
        )
        self.sm.active(1)

        self._write_data_cmd()
        self._write_dsp_ctrl()

    def _send_pio(self, byte, start=False, stop=False):
        word = (1 if start else 0) | (byte << 1) | ((1 if stop else 0) << 9)
        self.sm.put(word)

    def _write_data_cmd(self):
        self._send_pio(TM1637_CMD1, start=True, stop=True)

    def _write_dsp_ctrl(self):
        self._send_pio(TM1637_CMD3 | TM1637_DSP_ON | self._brightness, start=True, stop=True)

    def brightness(self, val=None):
        if val is None:
            return self._brightness
        if not 0 <= val <= 7:
            raise ValueError("Brightness out of range")
        self._brightness = val
        self._write_data_cmd()
        self._write_dsp_ctrl()

    def write(self, segments, pos=0):
        if not 0 <= pos <= 5:
            raise ValueError("Position out of range")
        
        self._write_data_cmd()
        self._send_pio(TM1637_CMD2 | pos, start=True, stop=False)
        
        for i, seg in enumerate(segments):
            is_last = (i == len(segments) - 1)
            self._send_pio(seg, start=False, stop=is_last)
            
        self._write_dsp_ctrl()

    def encode_digit(self, digit):
        return _SEGMENTS[digit & 0x0f]

    def encode_string(self, string):
        segments = bytearray(len(string))
        for i in range(len(string)):
            segments[i] = self.encode_char(string[i])
        return segments

    def encode_char(self, char):
        o = ord(char)
        if o == 32: return _SEGMENTS[36]
        if o == 42: return _SEGMENTS[38]
        if o == 45: return _SEGMENTS[37]
        if o >= 65 and o <= 90: return _SEGMENTS[o-55]
        if o >= 97 and o <= 122: return _SEGMENTS[o-87]
        if o >= 48 and o <= 57: return _SEGMENTS[o-48]
        raise ValueError("Character out of range: {:d} '{:s}'".format(o, chr(o)))

    def hex(self, val):
        string = '{:04x}'.format(val & 0xffff)
        self.write(self.encode_string(string))

    def number(self, num):
        num = max(-999, min(num, 9999))
        string = '{0: >4d}'.format(num)
        self.write(self.encode_string(string))

    def numbers(self, num1, num2, colon=True):
        num1 = max(-9, min(num1, 99))
        num2 = max(-9, min(num2, 99))
        segments = self.encode_string('{0:0>2d}{1:0>2d}'.format(num1, num2))
        if colon:
            segments[1] |= 0x80
        self.write(segments)

    def temperature(self, num):
        if num < -9:
            self.show('lo')
        elif num > 99:
            self.show('hi')
        else:
            string = '{0: >2d}'.format(num)
            self.write(self.encode_string(string))
        self.write([_SEGMENTS[38], _SEGMENTS[12]], 2)

    def show(self, string, colon=False):
        segments = self.encode_string(string)
        if len(segments) > 1 and colon:
            segments[1] |= 128
        self.write(segments[:4])

    def scroll(self, string, delay=250):
        segments = string if isinstance(string, list) else self.encode_string(string)
        data = [0] * 8
        data[4:0] = list(segments)
        for i in range(len(segments) + 5):
            self.write(data[0+i:4+i])
            sleep_ms(delay)


class TM1637Decimal(TM1637):
    def encode_string(self, string):
        segments = bytearray(len(string.replace('.','')))
        j = 0
        for i in range(len(string)):
            if string[i] == '.' and j > 0:
                segments[j-1] |= TM1637_MSB
                continue
            segments[j] = self.encode_char(string[i])
            j += 1
        return segments
