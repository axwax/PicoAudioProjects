import machine
import ustruct
import SimpleMIDIDecoder
from OLEDDisplay import *

# set up global variables
calibration = 35500    # calibration offset for reference voltage
lowest_note = 40   # which MIDI note number corresponds to 0V CV

# set up gate pin
gate = machine.Pin(27, machine.Pin.OUT)
gate.value(0)

# initialise serial MIDI ports
uart = machine.UART(0,31250,tx=machine.Pin(12),rx=machine.Pin(13)) # UART0 on pins 12,13


# Calculate the control voltage
def noteToVoltage(note):
    reference_voltage = (4.5 + (calibration / 65536)) # from 4.5V to 5.5V
    mv = 4096 / reference_voltage / 1000 # value for one mV
    semitone = 83.33 * mv # one semitone is 1V/12 = 83.33mV
    if(note == 0):
        dacV = 0
    else:
        dacV = int((note-lowest_note)*semitone)
    return dacV

# output control voltage for note on CV1
def playNote(note):
    global start_envelope, dac
    dacV = noteToVoltage(note)
    dac.update(dacV, 0) # blue
    return dacV

# MIDI Thru
def midi_send(cmd, ch, b1, b2):
    if (b2 == -1):
        uart.write(ustruct.pack("bb",cmd+ch,b1))
    else:
        uart.write(ustruct.pack("bbb",cmd+ch,b1,b2))
        
# MIDI callback routines
def doMidiNoteOn(ch, cmd, note, vel):
    global note_on, current_note, env
    dacV = playNote(note)
    gate.value(1)
    note_on = True
    current_note = note
    env.trigger()
    #print("note:",note)
    midi_send(cmd, ch, note, vel)

def doMidiNoteOff(ch, cmd, note, vel):
    global note_on,stop_envelope, env   
    gate.value(0)
    note_on = False
    stop_envelope = True
    env.stop()
    midi_send(cmd, ch, note, vel)

def doMidiThru(ch, cmd, d1, d2):
    midi_send(cmd, ch, d1, d2)
    if (cmd == 0xf8):
        calculate_bpm()
    if(cmd > 0xf8):
        transport_control(cmd)
    return


adc = ADCRead()
i2c = machine.I2C(0,sda=machine.Pin(8), scl=machine.Pin(9), freq=400000), machine.I2C(1,sda=machine.Pin(2), scl=machine.Pin(3), freq=400000) # set up I2C bus 0 and 1
dac = DACWrite(i2c)
oled = OLEDDisplay(machine.Timer(), 100, adc, i2c[0])
env = ADSREnvelope(machine.Timer(), 10, adc, dac) #2
env.trigger()
env.stop()

# initialise MIDI decoder and set up callbacks
md = SimpleMIDIDecoder.SimpleMIDIDecoder()
md.cbNoteOn (doMidiNoteOn)
md.cbNoteOff (doMidiNoteOff)
md.cbThru (doMidiThru)
print("start")
# the loop
while True:
    # Check for MIDI messages
    if (uart.any()):
        md.read(uart.read(1)[0])
