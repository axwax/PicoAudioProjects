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
        
class OLEDDisplay:
    def __init__(self, timer, frequency, objADC):
        
        self.objADC = objADC
        self.i2c = self.setup_i2c()
                
        # set up timer
        timer.init(period = frequency, callback = self.update)
        
        # set up oled
        self.oled = ssd1306.SSD1306_I2C(128, 64, self.i2c[0])
        self.offset = 16
        self.timeComp = 35
        self.ampComp = 21.5
        self.yMax = 63
        self.sustainTime = 40        

    def draw_envelope(self):
        self.objADC.update()       
        attackTime = int(self.objADC.a*4/self.timeComp)
        decayTime = int(self.objADC.d*4/self.timeComp)
        sustainLevel = int(self.objADC.s/4/self.ampComp)
        releaseTime = int(self.objADC.r*4/self.timeComp)
        self.oled.line(0, self.yMax, attackTime, self.offset, 1) # draw attack line
        self.oled.line(attackTime, self.offset, attackTime + decayTime, self.yMax - sustainLevel, 1) # draw decay line
        self.oled.line(attackTime + decayTime, self.yMax - sustainLevel, attackTime + decayTime + self.sustainTime, self.yMax - sustainLevel, 1) # draw decay line
        self.oled.line(attackTime + decayTime + self.sustainTime, self.yMax - sustainLevel, attackTime + decayTime + self.sustainTime + releaseTime, self.yMax, 1) # draw release line

    def setup_i2c(self):
        print("setup i2c")
        # set up I2C bus 0 and 1
        return [machine.I2C(0,sda=machine.Pin(8), scl=machine.Pin(9), freq=400000), machine.I2C(1,sda=machine.Pin(2), scl=machine.Pin(3), freq=400000)]

    def update(self, tim): # this is run periodically by the timer
        self.oled.fill(0)
        self.oled.text("ADSR", 0, 0)
        self.draw_envelope()
        self.oled.show()

adc = ADCRead()
ax = OLEDDisplay(machine.Timer(), 100, adc)
