from machine import PWM, Pin
max_power_in = 500
max_power_out = 2500


# 180 : set_pulse_widths(0.70,0.66)
# 0 : set_pulse_widths(2.5,2.33)
max_pulse_width1 = 2.48
min_pulse_width1 = 0.72
max_pulse_width2 = 2.33
min_pulse_width2 = 0.65




# Configure the pin connected to the servo
servo1_pin_number = 7
servo2_pin_number = 8  # Change this to the pin number you're using
servo1 = PWM(Pin(servo1_pin_number), freq=50)  # 50Hz frequency for most servos
servo2 = PWM(Pin(servo2_pin_number), freq=50)  # 50Hz frequency for most servos


def set_pulse_widths(pulse_width1,pulse_width2):    
    duty1 = pulse_width1/20
    servo1.duty_u16(int(duty1*65535))
    duty2 = pulse_width2/20  
    servo2.duty_u16(int(duty2*65535))


def set_angles(angle1,angle2):
    pulse_width1 = (max_pulse_width1 - angle1/180*(max_pulse_width1-min_pulse_width1))
    pulse_width2 = (max_pulse_width2 - angle2/180*(max_pulse_width2-min_pulse_width2))
    set_pulse_widths(pulse_width1,pulse_width2)

def set_powers(power_in,power_out):
    angle1 = power_in/max_power_in*180
    angle2 = power_out/max_power_out*180
    if angle1<0:
        angle1 = 0
    if angle2<0:
        angle2 = 0
    if angle1>180:
        angle1=180
    if angle2>180:
        angle2=180
    set_angles(angle1,angle2)


