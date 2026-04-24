import tm1637_7_seg as tm1637
from machine import I2C, SoftI2C, ADC, Pin, Timer


p_out_num_disp = tm1637.TM1637(clk=Pin(0,Pin.OUT), dio=Pin(3,Pin.OUT))
p_in_num_disp = tm1637.TM1637(clk=Pin(1,Pin.OUT), dio=Pin(3,Pin.OUT))
energy_num_disp = tm1637.TM1637(clk=Pin(2,Pin.OUT), dio=Pin(3,Pin.OUT))


p_out_num_disp.number(1851)
p_in_num_disp.number(1)
energy_num_disp.number(352)

RELAY_PIN = 15

relay_pin = Pin(RELAY_PIN,Pin.OUT)

def power_on_off(on_off):
    relay_pin.value(on_off)



from machine import Pin
import time
btn1 = Pin(19,Pin.IN,Pin.PULL_DOWN)
btn2 = Pin(20,Pin.IN,Pin.PULL_DOWN)
btn1_bike = Pin(21,Pin.IN,Pin.PULL_UP)
btn2_bike = Pin(22,Pin.IN,Pin.PULL_UP)

while 1:
    print("bt1 : {} bt2 : {}  btn1_bike : {}  btn2_bike : {}\n\r".format(btn1.value(),btn2.value(),btn1_bike.value(),btn2_bike.value()))
    print('lk')
    time.sleep(1)
