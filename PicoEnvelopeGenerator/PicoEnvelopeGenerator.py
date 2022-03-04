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
from ulab import numpy as np
import sys
np.set_printoptions(threshold=sys.maxsize)
from mcp3008 import MCP3008

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

# set up 10-bit analogue inputs
spi = machine.SPI(0, sck=machine.Pin(18),mosi=machine.Pin(19),miso=machine.Pin(16), baudrate=100000)
cs = machine.Pin(17, machine.Pin.OUT)
chip = MCP3008(spi, cs)

# set up gate pin
gate = machine.Pin(21, machine.Pin.OUT)
gate.value(0)

# set up I2C bus 0 and 1
i2c = [machine.I2C(0,sda=machine.Pin(8), scl=machine.Pin(9), freq=400000), machine.I2C(1,sda=machine.Pin(2), scl=machine.Pin(3), freq=400000)]

# initialise serial MIDI ports
uart = machine.UART(0,31250,tx=machine.Pin(12),rx=machine.Pin(13)) # UART0 on pins 12,13

envelope_pos = 0
do_envelope = False
start_envelope = False
stop_envelope = False
note_on = False # is a note played at the moment?
sustain_level = 0
release_length = 0
#env = [1,2,4,8,16,12,10,8,8,8,8,6,4,2,2,1]
ad_array = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000, 2925, 2850, 2775, 2700, 2625, 2550, 2475, 2400, 2325, 2250, 2175, 2100, 2025, 1950, 1875, 1800, 1725, 1650, 1575, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1461, 1423, 1384, 1346, 1307, 1269, 1230, 1192, 1153, 1115, 1076, 1038, 999, 961, 923, 884, 846, 807, 769, 730, 692, 653, 615, 576, 538, 499, 461, 423, 384, 346, 307, 269, 230, 192, 153, 115, 76, 38, 0]
rel_array = []

# timer callback functions:

# calibration
def check_calibration_pot(t):
    global calibration
    calibration = analog0_value.read_u16()

# distance sensor
def check_distance_sensor(t):
    distance = analog1_value.read_u16() / 16  
    writeToDac(int(distance),0x63,1)
    #convert to number from 0 - 16
    numLEDs = 16 - int(distance / 256)
    neopixelDraw(numLEDs, 10)

# envelope generator functions
def attack_decay(attack_length = 30, decay_length = 20, sustain_level = 1500, full_level = 4000):
    if(attack_length<2):
        attack_arr = np.full((1, ), full_level, dtype=np.uint16)
    else:
        attack_arr = np.linspace(0, full_level, attack_length, endpoint = False, dtype=np.uint16)
    if(decay_length<2):
        decay_arr = np.full((1, ), sustain_level, dtype=np.uint16)
    else:
        decay_arr = np.linspace(full_level, sustain_level, decay_length, endpoint = False, dtype=np.uint16)
    ad = np.concatenate((attack_arr, decay_arr), axis=0)
    return ad

def release (current_level = 1500, release_length = 40):
    if(release_length<2):
        release_arr = np.full((1, ), 0, dtype=np.uint16)
    else:
        release_arr = np.linspace(sustain_level, 0, release_length, dtype=np.uint16)
    return release_arr

# envelope
def envelope(t):
    global start_envelope
    global stop_envelope
    global do_envelope
    global envelope_pos
    global release_pos
    global ad_array
    global rel_array
    global release_length
    global sustain_level
    if (start_envelope):
        
        envelope_pos = 0
        release_pos = 0
        
        attack_length  = int(chip.read(7) / 4)
        decay_length   = int(chip.read(6) / 4)
        sustain_level  = int(chip.read(5) * 4)
        release_length = int(chip.read(4) / 4 )
        
        ad_array = attack_decay(attack_length, decay_length,sustain_level)
        
        print("attack",attack_length,"decay",decay_length,"sustain",sustain_level,"release",release_length)
        do_envelope = True
        start_envelope = False
        
    if (do_envelope):
        if (note_on):
            if (envelope_pos<len(ad_array)): # we're in the attack/decay section
                envelope_pos = envelope_pos + 1
                out = int(ad_array[envelope_pos-1])
            else:
                out = sustain_level # we're in the sustain section
            
        else: # we're in the release section
            if(stop_envelope):
                stop_envelope = False
                rel_array = release(ad_array[envelope_pos-1],release_length)
            if (release_pos<len(rel_array)-1):
                release_pos = release_pos + 1
                out = int(rel_array[release_pos])
            else:
                out = 0
                do_envelope = False
        writeToDac(out,0x60,0)
        

# set up timers
#distance_timer = machine.Timer()
#distance_timer.init (period = 50, mode = machine.Timer.PERIODIC, callback = check_distance_sensor)
if (not calibration): # only check the calibration pot if there isn't a hard coded calibration value
    calibration_timer = machine.Timer()
    calibration_timer.init (period = 100, mode = machine.Timer.PERIODIC, callback = check_calibration_pot)
envelope_timer = machine.Timer()
envelope_timer.init (period = 2, mode = machine.Timer.PERIODIC, callback = envelope)

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
def writeToDac(value,addr, i2cBus):
    buf=bytearray(2)
    buf[0]=(value >> 8) & 0xFF
    buf[1]=value & 0xFF
    i2c[i2cBus].writeto(addr,buf)
    
# Calculate the control voltage
def noteToVoltage(note):
    reference_voltage = (4.5 + (calibration / 65536)) # from 4.5V to 5.5V
    mv = 4096 / reference_voltage / 1000 # value for one mV
    semitone = 83.33 * mv # one semitone is 1V/12 = 83.33mV
    if(note == 0):
        dacV = 0
    else:
        dacV = int((note-lowest_note)*semitone)
    print("Vref:",(4.5 + (calibration / 65536)), " note:",note, " note V:",dacV)
    return dacV

# output control voltage for note on CV1
def playNote(note):
    global start_envelope
    dacV = noteToVoltage(note)
    writeToDac(dacV,0x62,1)
    start_envelope = True
    return dacV

# MIDI callback routines
def doMidiNoteOn(ch, cmd, note, vel):
    global note_on    
    dacV = playNote(note)
    gate.value(1)
    note_on = True

def doMidiNoteOff(ch, cmd, note, vel):
    global note_on,stop_envelope
    gate.value(0)
    note_on = False
    stop_envelope = True
    #playNote(0)

def doMidiThru(ch, cmd, d1, d2):
    return

# initialise MIDI decoder and set up callbacks
md = SimpleMIDIDecoder.SimpleMIDIDecoder()
md.cbNoteOn (doMidiNoteOn)
md.cbNoteOff (doMidiNoteOff)
md.cbThru (doMidiThru)

# the loop
while True:
    # Check for MIDI messages
    if (uart.any()):
        md.read(uart.read(1)[0])
