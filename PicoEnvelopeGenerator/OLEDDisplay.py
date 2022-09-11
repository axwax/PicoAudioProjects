import machine
import time
from ulab import numpy as np
import sys
np.set_printoptions(threshold=sys.maxsize)
import ssd1306
from mcp3008 import MCP3008


class ADCRead:
    def __init__(self):
        self.a = 30
        self.d = 20
        self.s = 1500
        self.r = 5
        
        # set up 10-bit analogue inputs
        self.spi = machine.SPI(0, sck=machine.Pin(18),mosi=machine.Pin(19),miso=machine.Pin(16), baudrate=100000)
        self.cs = machine.Pin(17, machine.Pin.OUT)
        self.chip = MCP3008(self.spi, self.cs)
        
    def update(self):
        self.a  = int(self.chip.read(7) / 4)
        self.d   = int(self.chip.read(6) / 4)
        self.s  = int(self.chip.read(5) * 4)
        self.r = int(self.chip.read(4) / 4 )        

class DACWrite:
    def __init__(self, i2c, calibration = 35500, lowest_note = 40):
        self.calibration = calibration # calibration offset for reference voltage
        self.lowest_note = lowest_note   # which MIDI note number corresponds to 0V CV
        self.i2c = i2c
        self.dac = np.array([[0x62,1],  # blue
                             [0x63,1],  # green
                             [0x60,0],  # brown
                             [0x61,0]], dtype=np.uint8) # yellow        
    # write to dac
    def update(self, value, dac_number):
        buf=bytearray(2)
        buf[0]=(value >> 8) & 0xFF
        buf[1]=value & 0xFF
        self.i2c[self.dac[dac_number][1]].writeto(self.dac[dac_number][0], buf)
    # Calculate the control voltage
    def noteToVoltage(self, note):
        reference_voltage = (4.5 + (self.calibration / 65536)) # from 4.5V to 5.5V
        mv = 4096 / reference_voltage / 1000 # value for one mV
        semitone = 83.33 * mv # one semitone is 1V/12 = 83.33mV
        if(note == 0):
            dacV = 0
        else:
            dacV = int((note-self.lowest_note)*semitone)
        return dacV
    # output control voltage for note on CV1
    def playNote(self,note):
        dacV = self.noteToVoltage(note)
        self.update(dacV, 0) # blue
        return dacV


class ADSREnvelope:
    def __init__(self, timer, frequency, objADC, objDAC, full_level=4000):
        
        self.objADC = objADC
        self.objDAC = objDAC        
        self.full_level = full_level
        
        self.envelope_pos = 0
        self.release_pos = 0
        self.do_envelope = False
        self.stop_envelope = False
        self.note_on = False

        self.ad_array = []
        self.rel_array = []
        
        # set up timer
        timer.init(period = frequency, callback = self.update)        

    def attack_decay(self): # generate attack/decay array
        if(self.objADC.a<2):
            attack_arr = np.full((1, ), self.full_level, dtype=np.uint16)
        else:
            attack_arr = np.linspace(0, self.full_level, self.objADC.a, endpoint = False, dtype=np.uint16)
        if(self.objADC.d<2):
            decay_arr = np.full((1, ), self.objADC.s, dtype=np.uint16)
        else:
            decay_arr = np.linspace(self.full_level, self.objADC.s, self.objADC.d, endpoint = False, dtype=np.uint16)
        self.ad_array = np.concatenate((attack_arr, decay_arr), axis=0)

    def release(self): # generate release array
        global aLen, rLen
        if(self.objADC.r<2):
            self.rel_array = np.full((1, ), 0, dtype=np.uint16)
        else:
            self.rel_array = np.linspace(self.ad_array[self.envelope_pos-1], 0, self.objADC.r, dtype=np.uint16)
    
    def trigger(self): # trigger the envelope from the start
        self.envelope_pos = 0
        self.release_pos = 0
        self.do_envelope = True
        self.note_on = True
        self.objADC.update()
        self.attack_decay()
        
    def stop(self): # initiate release phase of the envelope
        self.note_on = False
        self.stop_envelope = True
        
    def update(self, tim): # must be run in the loop
        if (self.do_envelope):
            if (self.note_on): # we're playing a note, but where are we in the evelope?
                if (self.envelope_pos<len(self.ad_array)): # we're in the attack/decay section
                    self.envelope_pos = self.envelope_pos + 1
                    out = int(self.ad_array[self.envelope_pos-1])
                else:
                    out = self.objADC.s # we're in the sustain section                    
            else: # we're not playing a note any more, are we in the release section?
                if(self.stop_envelope): # not yet, let's set it up
                    self.stop_envelope = False
                    self.release() # self.ad_array[self.envelope_pos-1],self.objADC.r
                    
                if (self.release_pos<len(self.rel_array)-1): # we are in the release phase
                    self.release_pos = self.release_pos + 1
                    out = int(self.rel_array[self.release_pos])
                else: # we have finished the release phase
                    out = 0
                    self.do_envelope = False
            self.objDAC.update(out, 1) # output to CV2
        
class OLEDDisplay:
    def __init__(self, timer, frequency, objADC, i2c):
        
        self.objADC = objADC
        self.i2c = i2c
                
        # set up timer
        timer.init(period = frequency, callback = self.update)
        
        # set up oled
        self.oled = ssd1306.SSD1306_I2C(128, 64, self.i2c)
        self.offset = 16
        self.timeComp = 35
        self.ampComp = 21.5
        self.yMax = 63
        self.sustainTime = 40        

    def draw_envelope(self):
        self.objADC.update()
        self.oled.text(" A   D   S    R", 0, 0)
        self.oled.text(zfl(str(self.objADC.a),3) + " " + zfl(str(self.objADC.d),3) + " " + zfl(str(self.objADC.s),4) + " " + zfl(str(self.objADC.r),3), 0, 8)
        attackTime = int(self.objADC.a*4/self.timeComp)
        decayTime = int(self.objADC.d*4/self.timeComp)
        sustainLevel = int(self.objADC.s/4/self.ampComp)
        releaseTime = int(self.objADC.r*4/self.timeComp)
        self.oled.line(0, self.yMax, attackTime, self.offset, 1) # draw attack line
        self.oled.line(attackTime, self.offset, attackTime + decayTime, self.yMax - sustainLevel, 1) # draw decay line
        self.oled.line(attackTime + decayTime, self.yMax - sustainLevel, attackTime + decayTime + self.sustainTime, self.yMax - sustainLevel, 1) # draw decay line
        self.oled.line(attackTime + decayTime + self.sustainTime, self.yMax - sustainLevel, attackTime + decayTime + self.sustainTime + releaseTime, self.yMax, 1) # draw release line

    def update(self, tim): # this is run periodically by the timer
        self.oled.fill(0)
        self.draw_envelope()
        self.oled.show()

# pad string [s] with [width] leading zeros
def zfl(s, width):
    return '{:0>{w}}'.format(s, w=width)