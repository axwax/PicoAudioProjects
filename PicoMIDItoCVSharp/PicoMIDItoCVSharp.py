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
# gate output: GP17
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
numpix = 16
neopin = 16
strip = Neopixel(numpix, 0, neopin, "GRB")

black = (0, 0, 0)
red = (255, 0, 0)
orange = (255, 50, 0)
yellow = (255, 100, 0)
green = (0, 255, 0)
blue = (0, 0, 255)
indigo = (100, 0, 90)
violet = (200, 0, 100)
colors_rgb = [red, orange, yellow, green, blue, indigo, violet]
colors = colors_rgb

strip.brightness(50)
strip.fill(black)
strip.set_pixel_line_gradient(0, 0, green, yellow)
strip.show()

analog0_value = machine.ADC(26)
analog1_value = machine.ADC(27)
analog2_value = machine.ADC(28)

# which MIDI note number corresponds to 0V CV
lowest_note = 40

filterDepth = 3

# create gate pin
gate = machine.Pin(17, machine.Pin.OUT)
gate.value(0)

#create an I2C bus
sda=machine.Pin(2)
scl=machine.Pin(3)
i2c = machine.I2C(1, scl=scl, sda=sda, freq=400000)

cutoff = 0
calibration = 13000

def drawCV2(ax):
    global cutoff
    numLEDs = int(cutoff / 256)
    drawCVNote(numLEDs, 10)

timer = machine.Timer()
timer.init (freq = 20, mode = machine.Timer.PERIODIC, callback = drawCV2)

def drawCVNote(note, bright):
    strip.brightness(bright)
    note_pixels = note
    if note_pixels < 0:
        note_pixels = 0
    if note_pixels > 15:
        note_pixels = note_pixels = 15
        
    note_pixels = 16-note_pixels    
    strip.fill(black)
    if (note_pixels == 0):
        strip.set_pixel(0,black)
    else:
        strip.set_pixel_line_gradient(0, note_pixels-1, green, yellow)
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

def drawNote(note, bright):
    strip.brightness(bright)
    note_pixels = note-lowest_note-12
    if note_pixels < 0:
        note_pixels = 0
    if note_pixels > 13:
        note_pixels = note_pixels - 12       
    #print(note_pixels)
    strip.fill(black)
    if (note_pixels == 0):
        strip.set_pixel(0,green)
    else:
        strip.set_pixel_line_gradient(0, note_pixels, green, yellow)
    strip.show()

# MIDI callback routines
def doMidiNoteOn(ch, cmd, note, vel):
    global light_level, filterDepth
    dacV = playNote(note)
    cutoff = light_level/16
    if cutoff < 0:
        cutoff = 0
    writeToDac(int(cutoff),0x63)
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
    light_level = analog1_value.read_u16()
    calibration = analog0_value.read_u16()
    cutoff = light_level/16
    writeToDac(int(cutoff),0x63)
