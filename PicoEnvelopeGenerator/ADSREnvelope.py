import machine
import time
from ulab import numpy as np
import sys
np.set_printoptions(threshold=sys.maxsize)

class ADSREnvelope:
    def __init__(self, timer, frequency, attack_length=30, decay_length=20, sustain_level=1500, release_length=40, full_level=4000):
        self.attack_length = attack_length
        self.decay_length = decay_length
        self.sustain_level = sustain_level
        self.release_length = release_length
        self.full_level = full_level
        

        self.envelope_pos = 0
        self.do_envelope = False
        self.stop_envelope = False
        self.is_playing = False
        self.note_on = False
        
        self.current_level = 0

        self.ad_array = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000, 2925, 2850, 2775, 2700, 2625, 2550, 2475, 2400, 2325, 2250, 2175, 2100, 2025, 1950, 1875, 1800, 1725, 1650, 1575, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1461, 1423, 1384, 1346, 1307, 1269, 1230, 1192, 1153, 1115, 1076, 1038, 999, 961, 923, 884, 846, 807, 769, 730, 692, 653, 615, 576, 538, 499, 461, 423, 384, 346, 307, 269, 230, 192, 153, 115, 76, 38, 0]
        self.rel_array = []
        timer.init(period = frequency, callback = self.update)
        
        #self.class_method()
#         do_envelope = False
#         start_envelope = False
#         stop_envelope = False
#         note_on = False # is a note played at the moment?
        
    @classmethod
    def class_method(self):
        print (self.update(self))

    def start_envelope(self):
        print("start envelope")
        self.do_envelope = True
        self.note_on = True
        
    # envelope generator functions
    def attack_decay(self):
        if(self.attack_length<2):
            attack_arr = np.full((1, ), self.full_level, dtype=np.uint16)
        else:
            attack_arr = np.linspace(0, self.full_level, self.attack_length, endpoint = False, dtype=np.uint16)
        if(self.decay_length<2):
            decay_arr = np.full((1, ), self.sustain_level, dtype=np.uint16)
        else:
            decay_arr = np.linspace(self.full_level, self.sustain_level, self.decay_length, endpoint = False, dtype=np.uint16)
        ad_arr = np.concatenate((attack_arr, decay_arr), axis=0)
        return ad_arr

    def release(self, current_level = 1500, release_length = 40):
        if(self.release_length<2):
            release_arr = np.full((1, ), 0, dtype=np.uint16)
        else:
            release_arr = np.linspace(self.sustain_level, 0, self.release_length, dtype=np.uint16)
        return release_arr
    
    def trigger(self): # trigger the envelope from the start
        print("trigger")
        self.envelope_pos = 0
        self.release_pos = 0
#         self.attack_length  = int(chip.read(7) / 4)
#         self.decay_length   = int(chip.read(6) / 4)
#         self.sustain_level  = int(chip.read(5) * 4)
#         self.release_length = int(chip.read(4) / 4)
        self.ad_array = self.attack_decay()
        
    def update(self, tim): # must be run in the loop
        print("update")
        if (self.do_envelope):
            if (self.note_on):
                if (self.envelope_pos<len(self.ad_array)): # we're in the attack/decay section
                    self.envelope_pos = self.envelope_pos + 1
                    out = int(self.ad_array[self.envelope_pos-1])
                else:
                    out = self.sustain_level # we're in the sustain section
                print("pos:",self.envelope_pos,"a:", self.attack_length, "d:", self.decay_length, "s:", self.sustain_level, " v:",out)
                    
            else: # we're in the release section
                if(self.stop_envelope):
                    self.stop_envelope = False
                    self.rel_array = self.release(self.ad_array[self.envelope_pos-1],self.release_length)
                if (self.release_pos<len(self.rel_array)-1):
                    self.release_pos = self.release_pos + 1
                    out = int(self.rel_array[self.release_pos])
                else:
                    out = 0
                    self.do_envelope = False
                print("pos:",self.release_pos, "s:", self.sustain_level, "r:", self.release_length, " v:",out)
            #writeToDac(out,0x60,0)
            


ax = ADSREnvelope(machine.Timer(), 500)
ax.trigger()
ax.start_envelope()
#ax.update()
# while(1):
#     ax.update()
#     time.sleep_ms(2)
#envelope_timer = machine.Timer()
#envelope_timer.init (period = 200, mode = machine.Timer.PERIODIC, callback = ax.update())
