import neopixel, machine, time

PIN_NUMBER = 6
NUM_PIX = 8
pixels = neopixel.NeoPixel(machine.Pin(PIN_NUMBER), NUM_PIX)
 
yellow = (255, 100, 0)
orange = (200, 100, 0)
green = (0, 200, 0)
blue = (0, 0, 255)
red = (200, 0, 0)
color0 = red
black = (0,0,0)


#pixels.brightness(50)
#pixels.fill(orange)
#pixels.set_pixel_line_gradient(3, 13, green, blue)
#pixels.set_pixel_line(14, 16, red)
#pixels.set_pixel(20, (255, 255, 255))



def set_value(x):
    if x>0:
        leds_to_turn_on = int(x/100*(NUM_PIX-1)) + 1
    else:
        leds_to_turn_on = 0
    c = green
    if x<55:
        c = yellow
    if x < 20:
        c = red
    for i in range(NUM_PIX): 
        
        
        if (i < leds_to_turn_on ):
            pixels[i] = c
        else:
            pixels[i] = black
    
    pixels.write()

def test():
    for s in range(0,101):

        print(100-s)
        set_value(100-s)
        time.sleep_ms(200)

def test_pot():
    from time import sleep

    pot = machine.ADC(machine.Pin(28))

    while True:
        pot_value = pot.read_u16() # read value, 0-65535 across voltage range 0.0v - 3.3v
        set_value(pot_value/65535*100)
        print(pot_value/65535*100)
        sleep(0.4)


# test()
