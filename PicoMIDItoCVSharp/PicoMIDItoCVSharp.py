# MIDI to CV converter for Raspberry Pi Pico and MCP4725 DAC by @AxWax
#
# Demo: https://www.youtube.com/watch?v=aGfQHL1jU4I
#
# This is heavily based on and requires
# the SimpleMIDIDecoder library by @diyelectromusic, which can be found at
# https://diyelectromusic.wordpress.com/2021/06/13/raspberry-pi-pico-midi-channel-router/
#
# The NeoPixel code requires the pi_pico_neopixel library by Blaž Rolih
# which can be found at https://github.com/blaz-r/pi_pico_neopixel
#
#
# Wiring:
# serial midi input: GP13 (UART0 RX)
# neopixels:         GP16, GND, 3.3v
# gate output:       GP17
# calibration pot:   GP26 (A0), GND, 3.3v
# distance sensor:   GP27 (A1), 3.3V
#
# MCP4725 (CV1&2)    Pico
# GND:               GND
# VCC:               VBUS (5V)
# SDA:               GP2
# SCL:               GP3
# VOUT: CV output to synth

import machine
import time
import ustruct
import SimpleMIDIDecoder
from neopixel import Neopixel

# set up Neopixel ring
neopixel_count = 16
neopixel_pin = 16
strip = Neopixel(neopixel_count, 0, neopixel_pin, "GRB")
black = (0, 0, 0)
yellow = (255, 100, 0)
green = (0, 255, 0)
strip.brightness(50)
strip.fill(black)
strip.show()

# set up global variables
calibration = 0    # calibration offset for reference voltage
lowest_note = 40   # which MIDI note number corresponds to 0V CV
old_num_pixels = 0 # previous number of neopixels shown

# set up analogue inputs
analog0_value = machine.ADC(26)
analog1_value = machine.ADC(27)
analog2_value = machine.ADC(28)

# set up gate pin
gate = machine.Pin(17, machine.Pin.OUT)
gate.value(0)

# set up I2C bus 1
sda=machine.Pin(2)
scl=machine.Pin(3)
i2c = machine.I2C(1, scl=scl, sda=sda, freq=400000)


# timer callback functions:

# calibration
def check_calibration_pot(t):
    global calibration
    calibration = analog0_value.read_u16()

# distance sensor
def check_distance_sensor(t):
    distance = analog1_value.read_u16() / 16  
    writeToDac(int(distance),0x63)
    #convert to number from 0 - 16
    numLEDs = 16 - int(distance / 256)
    neopixelDraw(numLEDs, 10)
    
# set up timers
distance_timer = machine.Timer()
distance_timer.init (period = 50, mode = machine.Timer.PERIODIC, callback = check_distance_sensor)
calibration_timer = machine.Timer()
calibration_timer.init (period = 100, mode = machine.Timer.PERIODIC, callback = check_calibration_pot)

# draw to neopixel ring 
def neopixelDraw (num_pixels, bright):
    global old_num_pixels
    strip.brightness(bright)
    # only redraw if the value has changed
    if(num_pixels == old_num_pixels or num_pixels > neopixel_count):
        return
    old_num_pixels = num_pixels
    # draw the pixels
    strip.fill(black)
    if (num_pixels == 1):
        strip.set_pixel(0,green)
    elif (num_pixels > 1):
        strip.set_pixel_line_gradient(0, num_pixels-1, green, yellow)
    strip.show()  

# DAC function
def writeToDac(value,addr):
    buf=bytearray(2)
    buf[0]=(value >> 8) & 0xFF
    buf[1]=value & 0xFF
    i2c.writeto(addr,buf)
    
# Initialise the serial MIDI handling
uart = machine.UART(0,31250,tx=machine.Pin(12),rx=machine.Pin(13)) # UART0 on pins 12,13

# Calculate the control voltage
def noteToVoltage(note):
    global semitone,lowest_note
    mv = (4096+(calibration / 128)) / 5 / 1000
    semitone = 83.33 * mv
    dacV = int((note-lowest_note)*semitone)
    print("calib:",calibration, " V:",dacV)
    return dacV

def playNote(note):
    dacV = noteToVoltage(note)
    writeToDac(dacV,0x62)
    return dacV

# MIDI callback routines
def doMidiNoteOn(ch, cmd, note, vel):    
    dacV = playNote(note)
    gate.value(1)    

def doMidiNoteOff(ch, cmd, note, vel):
    gate.value(0)

# initialise MIDI decoder and set up callbacks
md = SimpleMIDIDecoder.SimpleMIDIDecoder()
md.cbNoteOn (doMidiNoteOn)
md.cbNoteOff (doMidiNoteOff)

# the loop
while True:
    # Check for MIDI messages
    if (uart.any()):
        md.read(uart.read(1)[0])