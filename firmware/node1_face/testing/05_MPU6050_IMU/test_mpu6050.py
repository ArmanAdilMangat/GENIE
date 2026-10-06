"""
test_mpu6050.py - two MPU-6050 IMUs on one I2C bus.

Wire ONLY these after the TFT passes.
    SCL -> GPIO38  (P2-10)
    SDA -> GPIO47  (P2-17)
    VCC -> 3V3 rail        GND -> common GND

    MPU top     AD0 -> GND   -> answers at 0x68
    MPU bottom  AD0 -> 3V3   -> answers at 0x69

Forget the AD0 wire on the second module and BOTH answer at 0x68.  The scan
then shows one device and you spend an hour looking for a dead sensor that
is not dead.

Both modules carry their own 4.7k pull-ups to 3V3.  If SDA and SCL read
FLOATING, no module has power - check 3V3 before anything else.  Never add
your own pull-ups on top of two modules' worth; four in parallel is 1.2k
and the bus starts failing at speed.

    >>> import test_mpu6050
    >>> test_mpu6050.run()
"""

from machine import Pin, I2C
import time

SCL = 38
SDA = 47
TOP = 0x68
BOT = 0x69
FREQ = 400_000

PWR_MGMT_1 = 0x6B
WHO_AM_I = 0x75
ACCEL_XOUT_H = 0x3B


def bus_lines():
    """Both lines MUST be held high by the modules' pull-ups."""
    print("    checking the bus before touching it:")
    ok = True
    for name, pin in (("SCL", SCL), ("SDA", SDA)):
        up = Pin(pin, Pin.IN, Pin.PULL_UP).value()
        time.sleep_ms(5)
        dn = Pin(pin, Pin.IN, Pin.PULL_DOWN).value()
        Pin(pin, Pin.IN, None)
        if up == 1 and dn == 1:
            print("      %s GPIO%-2d  held HIGH - pull-up present.  Good."
                  % (name, pin))
        elif up == 1 and dn == 0:
            print("      %s GPIO%-2d  FLOATING - no powered module on the bus"
                  % (name, pin))
            ok = False
        else:
            print("      %s GPIO%-2d  held LOW - shorted, or a module is"
                  " hung" % (name, pin))
            ok = False
    return ok


def scan():
    i2c = I2C(0, scl=Pin(SCL), sda=Pin(SDA), freq=FREQ)
    found = i2c.scan()
    print("    devices: %s"
          % (", ".join("0x%02X" % a for a in found) if found else "NONE"))
    return i2c, found


def wake(i2c, addr):
    i2c.writeto_mem(addr, PWR_MGMT_1, b'\x00')   # clear sleep bit
    time.sleep_ms(50)


def who(i2c, addr):
    return i2c.readfrom_mem(addr, WHO_AM_I, 1)[0]


def accel(i2c, addr):
    d = i2c.readfrom_mem(addr, ACCEL_XOUT_H, 6)
    out = []
    for i in range(0, 6, 2):
        v = (d[i] << 8) | d[i + 1]
        out.append((v - 65536 if v > 32767 else v) / 16384.0)
    return out


def check():
    print("=" * 58)
    print("  MPU-6050 CHECK  (SCL GPIO%d, SDA GPIO%d)" % (SCL, SDA))
    print("=" * 58)
    if not bus_lines():
        print("\n  FAIL - fix power/wiring, the bus is not even idle-high.")
        return None, []

    i2c, found = scan()
    if not found:
        print("\n  FAIL - lines are high but nothing answers.  SDA and SCL")
        print("  swapped is the usual cause when the pull-ups look fine.")
        return i2c, []

    if TOP in found and BOT not in found:
        print("\n  Only 0x68 answered.  The bottom module's AD0 is not tied")
        print("  to 3V3, so both modules are fighting over 0x68.  Fix AD0.")
    elif BOT in found and TOP not in found:
        print("\n  Only 0x69 answered.  The top module's AD0 is on 3V3 when")
        print("  it should be on GND, or the top module is unpowered.")

    live_addrs = []
    for addr in (TOP, BOT):
        if addr not in found:
            continue
        try:
            wake(i2c, addr)
            w = who(i2c, addr)
            ax, ay, az = accel(i2c, addr)
            mag = (ax * ax + ay * ay + az * az) ** 0.5
            note = "still asleep or unpowered" if mag < 0.5 else \
                   ("PASS" if 0.85 < mag < 1.15 else "reading, but odd scale")
            print("    0x%02X  WHO_AM_I 0x%02X   |a| %.2f g   %s"
                  % (addr, w, mag, note))
            live_addrs.append(addr)
        except OSError as e:
            print("    0x%02X  answered the scan but not a read: %r"
                  % (addr, e))

    print("\n  %d/2 IMU(s) working." % len(live_addrs))
    return i2c, live_addrs


def live(i2c=None, addrs=None):
    """Sitting flat, |a| should read 1.00 g on both.  Tilt one and its X/Y
    swap with Z.  If both change together, you are reading one module
    twice - the AD0 problem again."""
    if i2c is None:
        i2c, addrs = check()
    if not addrs:
        return
    print("\n  Ctrl-C to stop.\n")
    try:
        while True:
            row = []
            for a in addrs:
                x, y, z = accel(i2c, a)
                row.append("0x%02X  %+.2f %+.2f %+.2f  |%.2f|"
                           % (a, x, y, z, (x * x + y * y + z * z) ** 0.5))
            print("  " + "     ".join(row))
            time.sleep_ms(200)
    except KeyboardInterrupt:
        print("\n  stopped")


def run():
    i2c, addrs = check()
    if addrs:
        live(i2c, addrs)


if __name__ == "__main__":
    run()
