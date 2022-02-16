# MIDI to CV converter for Raspberry Pi Pico and MCP4725 DAC by @AxWax
#
# Demo: https://www.youtube.com/watch?v=aGfQHL1jU4I
#
# This is heavily based on and requires
# the SimpleMIDIDecoder library by @diyelectromusic, which can be found at
# https://diyelectromusic.wordpress.com/2021/06/13/raspberry-pi-pico-midi-channel-router/
#
#
# Wiring:
# serial midi input on GP1 (UART0 RX)
# gate output: GP17
#
# MCP4725   Pico
# GND       GND
# VCC       VBUS (5V)
# SDA       GP6
# SCL       GP7
# VOUT is the CV output

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
    ####print ("LEDS:",numLEDs)
    #numLEDs = numLEDs+lowest_note+7
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
    
    #print(note_pixels)
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
    #drawNote(note,20)
    #print(dacV)
    cutoff = light_level/16
    if cutoff < 0:
        cutoff = 0
    writeToDac(int(cutoff),0x63)
    #print("note:",note," calibration:",calibration," filter:",cutoff )
    #filterV = 1000 - distance
    #writeToDac(int((filterV)*filterDepth),0x63)
    #print("V",(int((filterV)*filterDepth)))
    gate.value(1)

def doMidiNoteOff(ch, cmd, note, vel):
    gate.value(0)
    #drawNote(note,5)

def doMidiThru(ch, cmd, d1, d2):
    global filterDepth
    #if(cmd == 0xb0 and d1 == 74):
    if(cmd == 0xb0 and d1 == 102): # lfo speed
         #writeToDac(int(d2*32),0x63)
         filterDepth = d2/40
         print("filter",filterDepth)
    elif(cmd != 0xf8):
        print ("Thru ", ch, ":", hex(cmd), ":", d1, ":", d2)
    #if (d2 == -1):
        #uart.write(ustruct.pack("bb",cmd+ch,d1))
    #else:
        #uart.write(ustruct.pack("bbb",cmd+ch,d1,d2))
    

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
    light_level = analog1_value.read_u16()
    #calibration = analog0_value.read_u16()
    cutoff = light_level/16
    writeToDac(int(cutoff),0x63)
