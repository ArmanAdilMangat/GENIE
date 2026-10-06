"""
i2c_doctor — why is nothing answering on the I2C bus?

    >>> import i2c_doctor
    >>> i2c_doctor.doctor()

The scan finding NOTHING is different from finding the wrong address. If the
address were wrong you would still see *a* device. Nothing at all means the bus
itself is not working, so this file checks the bus before it checks addresses.

WHAT IT CHECKS, IN ORDER

  1. line levels   Both SDA and SCL must idle HIGH. The module's own 4.7k
                   pull-ups do that. A line stuck LOW means it is shorted to
                   ground, or a damaged chip is holding it down.
  2. hardware I2C  normal scan on SCL=38 SDA=47
  3. SWAPPED scan  same scan with the two pins exchanged. If a device shows up
                   here, your SDA and SCL wires are crossed. This is the single
                   most common cause and it costs you ten seconds to rule out.
  4. soft I2C      bit-banged fallback, in case the hardware peripheral is
                   unhappy with these pins.

EXPECTED ADDRESS
  AD0 -> GND  = 0x68
  AD0 -> 3V3  = 0x69
  With AD0 on 3V3 you should see 0x69, NOT 0x68.
"""

from machine import Pin, I2C, SoftI2C
import time
import pins

CANDIDATES = (0x68, 0x69)


def _name(a):
    if a == 0x68:
        return "MPU-6050 (AD0 low)"
    if a == 0x69:
        return "MPU-6050 (AD0 HIGH)"
    if a == 0x29:
        return "VL53L0X/L1X"
    if a == 0x3C:
        return "SSD1306 OLED"
    return "unknown"


# ---------------------------------------------------------------------------
def lines():
    """Are SDA and SCL idling high? Nothing works until they are."""
    print("\n[1] line levels - both must read 1")
    out = {}
    for label, p in (("SCL", pins.I2C_SCL), ("SDA", pins.I2C_SDA)):
        try:
            v = Pin(p, Pin.IN).value()          # no pull - rely on the module
            out[label] = v
            print("    %s  GPIO%-3d = %d   %s"
                  % (label, p, v, "ok" if v else "<<< STUCK LOW"))
        except Exception as e:
            print("    %s  GPIO%-3d ERROR %r" % (label, p, e))
            out[label] = None

    if out.get("SCL") == 0 or out.get("SDA") == 0:
        print("\n    A line stuck LOW means one of:")
        print("      - that wire is shorted to GND, or in the wrong hole")
        print("      - the module is dead and holding the line down")
        print("      - no module powered at all AND no pull-up anywhere")
        print("    Unplug the module. Both lines should go floating/high.")
        print("    If a line is still LOW with nothing attached, it is the wiring.")
    elif out.get("SCL") == 1 and out.get("SDA") == 1:
        print("    Both idle high - pull-ups are present, bus is electrically ok.")
    return out


def scan(scl=None, sda=None, soft=False, quiet=False):
    scl = pins.I2C_SCL if scl is None else scl
    sda = pins.I2C_SDA if sda is None else sda
    try:
        if soft:
            bus = SoftI2C(scl=Pin(scl), sda=Pin(sda), freq=100000)
        else:
            bus = I2C(0, scl=Pin(scl), sda=Pin(sda), freq=100000)
        found = bus.scan()
    except Exception as e:
        if not quiet:
            print("    ERROR %r" % e)
        return []
    if not quiet:
        if found:
            for a in found:
                print("    0x%02X  %s" % (a, _name(a)))
        else:
            print("    nothing")
    return found


def swap_test():
    """Are SDA and SCL crossed? Ten seconds to rule out the most likely fault."""
    print("\n[3] SWAP test")
    print("  as wired   SCL=%d SDA=%d" % (pins.I2C_SCL, pins.I2C_SDA))
    normal = scan(quiet=True)
    print("    -> %s" % (", ".join("0x%02X" % a for a in normal) or "nothing"))

    print("  swapped    SCL=%d SDA=%d" % (pins.I2C_SDA, pins.I2C_SCL))
    swapped = scan(pins.I2C_SDA, pins.I2C_SCL, quiet=True)
    print("    -> %s" % (", ".join("0x%02X" % a for a in swapped) or "nothing"))

    if swapped and not normal:
        print("\n    *** YOUR SDA AND SCL ARE CROSSED. ***")
        print("    Module SCL must go to GPIO%d, module SDA to GPIO%d."
              % (pins.I2C_SCL, pins.I2C_SDA))
        print("    Swap those two wires and re-run.")
    elif normal:
        print("\n    Wiring is the right way round.")
    else:
        print("\n    Nothing either way - this is not a swap. Keep going.")
    return normal, swapped


def soft_test():
    print("\n[4] software (bit-banged) I2C on the same pins")
    found = scan(soft=True)
    if found:
        print("\n    Soft I2C works but hardware I2C did not. Odd but usable -")
        print("    switch the driver over to SoftI2C if hardware I2C stays dead.")
    return found


def slow_scan():
    """Some modules with long wires need a slower clock."""
    print("\n[5] slow scan, 50 kHz")
    try:
        bus = I2C(0, scl=Pin(pins.I2C_SCL), sda=Pin(pins.I2C_SDA), freq=50000)
        found = bus.scan()
        print("    %s" % (", ".join("0x%02X" % a for a in found) or "nothing"))
        return found
    except Exception as e:
        print("    ERROR %r" % e)
        return []


def alive(addr=None):
    """Read WHO_AM_I. Confirms the chip is really an MPU and really awake."""
    print("\n[6] WHO_AM_I")
    found = scan(quiet=True)
    targets = [addr] if addr else [a for a in found if a in CANDIDATES]
    if not targets:
        print("    no MPU on the bus to ask")
        return
    for a in targets:
        try:
            bus = I2C(0, scl=Pin(pins.I2C_SCL), sda=Pin(pins.I2C_SDA), freq=100000)
            v = bus.readfrom_mem(a, 0x75, 1)[0]
            ok = v in (0x68, 0x69, 0x70, 0x72, 0x73, 0x98)
            print("    0x%02X -> WHO_AM_I 0x%02X  %s"
                  % (a, v, "genuine MPU" if ok else "<<< unexpected, likely a clone or damaged"))
        except OSError as e:
            print("    0x%02X -> no response (%r)" % (a, e))


def isolate():
    """Is the module holding SCL down, or is it the wiring?

    Three steps, and the answer is unambiguous. Uses the ESP32's INTERNAL
    pull-up, so a healthy floating pin must read 1 - no external parts needed.
    """
    scl, sda = pins.I2C_SCL, pins.I2C_SDA

    def rd():
        return (Pin(scl, Pin.IN, Pin.PULL_UP).value(),
                Pin(sda, Pin.IN, Pin.PULL_UP).value())

    print("\nISOLATION TEST - follow the prompts exactly\n")

    input("  1. Unplug the module COMPLETELY (all 4 wires). Enter> ")
    a = rd()
    print("     SCL=%d SDA=%d   %s" % (a[0], a[1],
          "both high, GPIOs are healthy" if a == (1, 1)
          else "<<< a bare GPIO reads LOW - that pin is shorted on the board"))
    if a[0] == 0:
        print("\n     GPIO%d reads LOW with NOTHING attached." % scl)
        print("     The fault is on the breadboard, not the module. Find the")
        print("     short between that column and ground.")
        return "wiring"

    input("\n  2. Plug in ONLY VCC and GND. Leave SCL/SDA off. Enter> ")
    b = rd()
    print("     SCL=%d SDA=%d   %s" % (b[0], b[1],
          "still fine" if b == (1, 1) else "<<< unexpected"))

    input("\n  3. Now plug in SCL and SDA too. Enter> ")
    c = rd()
    print("     SCL=%d SDA=%d" % (c[0], c[1]))

    if c == (1, 1):
        print("\n     Both lines high with the module connected - the bus is")
        print("     healthy now. Re-run doctor(); a reseat probably fixed it.")
        return "fixed"
    if c[0] == 0:
        print("\n     *** THE MODULE IS PULLING SCL LOW. ***")
        print("     A healthy MPU never does this. Combined with the earlier")
        print("     overheating, this module is dead.")
        print("     DO NOT put it on the second ESP32 - it will take that")
        print("     bus down as well. Test the other module on its own.")
        return "dead module"
    print("\n     SDA is the one being held low. Same conclusion.")
    return "dead module"


def add_second():
    """Add a second module WITHOUT risking the one that already works.

    The danger: a damaged module holds a bus line low, and that kills the
    whole bus - you would lose the working IMU too and spend an hour thinking
    the code broke. So we check the LINE LEVELS before we ever scan.
    """
    print("\nADDING A SECOND MPU - safe procedure\n")

    before = scan(quiet=True)
    if not before:
        print("  Nothing on the bus right now. Fix that first with doctor().")
        return
    print("  currently working: %s" % ", ".join("0x%02X" % a for a in before))

    taken = set(before)
    if 0x69 in taken and 0x68 not in taken:
        want, ad0 = 0x68, "GND (or leave AD0 unconnected)"
    elif 0x68 in taken and 0x69 not in taken:
        want, ad0 = 0x69, "3V3"
    else:
        print("  Both addresses are already in use. Nothing to add.")
        return

    print("\n  The new module must land at 0x%02X, so its AD0 -> %s" % (want, ad0))
    print("  SCL -> GPIO%d, SDA -> GPIO%d, same two rows as the first one."
          % (pins.I2C_SCL, pins.I2C_SDA))
    print("  VCC -> 3V3 rail, GND -> GND rail.")

    input("\n  POWER OFF, wire the second module, power back on. Enter> ")

    lvl = (Pin(pins.I2C_SCL, Pin.IN).value(),
           Pin(pins.I2C_SDA, Pin.IN).value())
    print("\n  line check: SCL=%d SDA=%d" % lvl)
    if 0 in lvl:
        print("\n  *** STOP. UNPLUG THE NEW MODULE NOW. ***")
        print("  It is holding a bus line low, which takes the working IMU")
        print("  down with it. That module is dead - do not put it on the")
        print("  ToF ESP32 either, it would kill those four sensors too.")
        return "bad module"

    after = scan(quiet=True)
    print("  scan: %s" % (", ".join("0x%02X" % a for a in after) or "nothing"))

    if want in after and len(after) >= 2:
        print("\n  Both IMUs on the bus. Run imu_test.selfcheck() - each must")
        print("  read 1.00 g at rest before you trust either of them.")
        return "ok"
    if after == before:
        print("\n  New module did not appear, but the bus is undamaged.")
        print("  Almost certainly AD0: it must go to %s for 0x%02X." % (ad0, want))
        print("  If AD0 is right and it still does not show, that module is")
        print("  dead in a quieter way - it just never answers.")
        return "not detected"
    print("\n  Unexpected result. Run doctor() for the full picture.")
    return "unclear"


def doctor():
    print("=" * 52)
    print("  I2C DOCTOR   SCL=GPIO%d  SDA=GPIO%d"
          % (pins.I2C_SCL, pins.I2C_SDA))
    print("=" * 52)

    lvl = lines()

    print("\n[2] hardware I2C scan, 100 kHz")
    normal = scan()

    n2, sw = swap_test()
    soft = soft_test() if not normal else []
    slow = slow_scan() if not (normal or soft) else []
    alive()

    print("\n" + "=" * 52)
    print("  VERDICT")
    print("=" * 52)
    found = normal or soft or slow
    if found:
        for a in found:
            print("  0x%02X  %s" % (a, _name(a)))
        if 0x69 in found:
            print("  AD0 is on 3V3 - correct for the SECOND module.")
        if 0x68 in found and 0x69 in found:
            print("  Both IMUs present. Run imu_test.selfcheck().")
        elif 0x69 in found:
            print("  One IMU, at 0x69. 0x69 is TAKEN, so the second module")
            print("  needs AD0 -> GND (or AD0 left unconnected) to sit at 0x68.")
            print("  Run i2c_doctor.add_second() for the safe procedure.")
        elif 0x68 in found:
            print("  One IMU, at 0x68. The second module needs AD0 -> 3V3")
            print("  to sit at 0x69. Run i2c_doctor.add_second().")
    elif sw:
        print("  SDA and SCL are crossed. Swap the two wires.")
    elif lvl.get("SDA") == 0 or lvl.get("SCL") == 0:
        print("  A bus line is stuck LOW - wiring short, or a dead module")
        print("  holding the line down. Unplug the module and re-run lines().")
    else:
        print("  Bus is electrically fine (both lines idle high) but nothing")
        print("  answers. In order of likelihood:")
        print("    1. SCL/SDA in the wrong holes - recount against WIRING_P2.md")
        print("       module SCL -> GPIO%d,  module SDA -> GPIO%d"
              % (pins.I2C_SCL, pins.I2C_SDA))
        print("    2. VCC or GND not actually reaching the module. The green")
        print("       LED can be lit from a partial connection - meter 3.3 V")
        print("       between the module's own VCC and GND pins.")
        print("    3. The module was damaged by the earlier overheating.")
        print("       Try the other one on its own.")
    return found


if __name__ == "__main__":
    doctor()
