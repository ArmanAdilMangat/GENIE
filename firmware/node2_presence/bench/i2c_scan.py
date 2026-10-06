"""Run this FIRST, before any VL53L1X code.

Scans the I2C bus and identifies what answers. Standalone -- no driver needed.

Expected results:
  ONE sensor connected, XSHUT floating/high  -> 0x29 found, model ID 0xEACC
  FOUR sensors connected, no XSHUT control   -> 0x29 found, but garbage or
                                                bus errors. This is the
                                                collision, and it is normal.
"""

from machine import I2C, Pin
import time

SDA, SCL = 8, 9
XSHUT = [10, 11, 12, 13]

MODEL_ID_REG = 0x010F        # 16-bit register address
VL53L1X_ID = 0xEACC
VL53L0X_ID = 0xEEAA          # L0X answers 0xEE at 8-bit reg 0xC0


def read16(i2c, addr, reg):
    try:
        i2c.writeto(addr, bytes([reg >> 8, reg & 0xFF]), False)
        d = i2c.readfrom(addr, 2)
        return (d[0] << 8) | d[1]
    except OSError:
        return None


i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=100000)

print("=" * 50)
print(" I2C SCAN  (SDA=GPIO%d  SCL=GPIO%d)" % (SDA, SCL))
print("=" * 50)

found = i2c.scan()
if not found:
    print("""
NOTHING ON THE BUS.

  1. Pull-ups: 4.7k from SDA to 3V3 and SCL to 3V3. ONE pair for the whole
     bus, not one pair per sensor. Some breakout boards have them fitted --
     four boards each with pull-ups makes the bus too stiff to drive.
  2. VIN of every sensor on 3V3 (these are 2.8V parts with an on-board LDO;
     5V on VIN kills them on some clones -- check your board's regulator).
  3. GND shared with the ESP32.
  4. XSHUT floating or tied high. Held low = sensor asleep = invisible.
""")
    raise SystemExit

print("\naddresses responding: %s" % [hex(a) for a in found])
print()

for a in found:
    mid = read16(i2c, a, MODEL_ID_REG)
    if mid == VL53L1X_ID:
        what = "VL53L1X   (model ID 0x%04X)" % mid
    elif mid is not None and (mid >> 8) == 0xEE:
        what = "VL53L0X   (not L1X -- wrong driver)"
    else:
        what = "unknown   (model ID %s)" % ("none" if mid is None else hex(mid))
    print("  0x%02X  %s" % (a, what))

if len(found) == 1 and found[0] == 0x29:
    print("""
One sensor at the factory address 0x29. That is correct for a single board.

With all four wired you will still see only 0x29 -- they all share it and
talk over each other. That is why tof_array.py drives XSHUT: it wakes them
one at a time and hands each a private address.
""")
elif 0x29 in found and len(found) > 1:
    print("\n0x29 plus reassigned addresses -- one sensor has not been given")
    print("a new address yet, or the board was reset after assignment.")

# ---- quick XSHUT sanity check -------------------------------------------
print("-" * 50)
print("XSHUT check: pulling each low should make 0x29 disappear")
pins = [Pin(p, Pin.OUT, value=1) for p in XSHUT]
time.sleep_ms(50)
for i, p in enumerate(pins):
    p.value(0)
    time.sleep_ms(50)
    gone = 0x29 not in i2c.scan()
    p.value(1)
    time.sleep_ms(50)
    print("  XSHUT #%d (GPIO%d): %s" % (i + 1, XSHUT[i],
          "controls a sensor" if gone else "no effect -- check this wire"))
