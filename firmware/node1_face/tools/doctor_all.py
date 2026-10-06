"""
doctor_all.py — A-to-Z board check. Finds the broken wires WITHOUT unwrapping.

    import doctor_all
    doctor_all.run()          # everything, ~40 s, ranked verdict at the end

Individual stages if you want them:

    doctor_all.pin_states()   # every pin: floating / tied low / tied high / driven
    doctor_all.tft_shorts()   # pin-to-pin shorts on the 13 display lines
    doctor_all.i2c_check()    # bus line levels, then scan
    doctor_all.adc_check()    # both MQ-2 channels
    doctor_all.digital_check()
    doctor_all.dht_check()

WHY THIS EXISTS

    Pulling a loom through a sleeve is exactly how dupont crimps back out of
    their housings and how neighbouring pins get pushed together. The symptom
    you have - white screen, one surviving sensor - is what that looks like.

    A white screen means the panel has power for its BACKLIGHT but the
    controller is not receiving. Missing VCC or a lost control line, both
    caused by a wire that is no longer making contact.

    Every test below is NON-DESTRUCTIVE. Nothing is driven against a sensor
    output. The only pins driven are the 13 TFT lines, and the panel side of
    those is a high-impedance input, so driving them is what the driver does
    anyway.

HOW THE FLOAT TEST WORKS - this is the whole trick

    Read a pin twice: once with the internal PULL-UP on, once with PULL-DOWN.

        reads 1 then 0    FLOATING   nothing is holding it - normal for a wire
                                     to a high-Z input, and normal for a
                                     DISCONNECTED wire. See the note below.
        reads 0 then 0    TIED LOW   shorted to GND, or a device holding it
        reads 1 then 1    TIED HIGH  shorted to 3V3
        reads x then x    DRIVEN     something is actively driving it - correct
                                     for a sensor DO pin, WRONG for a TFT pin

    A floating TFT line is expected. A TIED one is a fault. A sensor DO pin
    that floats is a DISCONNECTED sensor - it should be driven by its module.
    That asymmetry is what makes the test useful.

WHERE THE FLOAT TEST LIES - read this before believing a TFT verdict
    (added 20-08-2026, after it reported 13 fatal shorts on a display that
     was working perfectly)

    The float test uses the ESP32's INTERNAL pull-up, which is about 45k.
    Anything pulling harder than that wins, and the reading says TIED.

    A 5V-tolerant TFT shield does its level shifting with a resistor divider
    on every signal - roughly 1k in series and 2k to ground. That 2k against
    the ESP32's 45k pull-up reads 0 every single time. Thirteen lines, all
    reading TIED LOW, is not thirteen solder bridges. It is one resistor
    network doing exactly what it was designed to do.

    Two rules now applied below:

      1  If ALL 13 lines read the same state, it is a network, not a fault.
         Thirteen independent shorts landing on the same rail does not happen.

      2  A static pin reading never outranks a functional test. tft_alive()
         resets the panel and reads its controller ID back over the bus. If
         0x9341 comes back, data went out and data came in - the bus is
         PROVEN good and every TFT pin-state fault is suppressed.

    Run the float test on the display lines only with the ribbon UNPLUGGED.
    With it plugged in the numbers are the shield's, not yours.
"""

from machine import Pin, ADC, I2C
import time

import pins

# the 13 display lines, in the order they sit on P1
TFT = ((4, "LCD_D0"), (5, "LCD_D1"), (6, "LCD_D2"), (7, "LCD_D3"),
       (15, "LCD_D4"), (16, "LCD_D5"), (17, "LCD_D6"), (18, "LCD_D7"),
       (8, "LCD_WR"), (9, "LCD_RD"), (10, "LCD_RS"), (11, "LCD_CS"),
       (12, "LCD_RST"))

# sensor pins that should be DRIVEN by their module when connected
DRIVEN_EXPECTED = ((pins.FLAME, "flame DO", 1),
                   (pins.SW420_TOP, "SW-420 top DO", 1),
                   (pins.SW420_BOT, "SW-420 bot DO", 1))

FLOAT, LOW, HIGH, DRIVEN = "FLOATING", "TIED LOW", "TIED HIGH", "DRIVEN"

_faults = []

# set by tft_alive(). None = not tested, 0 = no answer, else the controller ID.
_tft_id = None


# ---------------------------------------------------------------------------
def tft_alive():
    """Reset the panel and read its controller ID back over the bus.

    This is a FUNCTIONAL test and it outranks every static pin reading in
    this file. Getting 0x9341 back means a command byte went out on D0-D7
    with WR and RS, the panel accepted it, and four bytes came back in on
    the same lines with RD. A bus that does that is not shorted.
    """
    global _tft_id
    print("\n" + "=" * 62)
    print("  0. IS THE DISPLAY ALIVE?  (functional, beats any pin reading)")
    print("=" * 62)

    D = [Pin(p, Pin.OUT) for p in (4, 5, 6, 7, 15, 16, 17, 18)]
    WR = Pin(8, Pin.OUT, value=1)
    RD = Pin(9, Pin.OUT, value=1)
    RS = Pin(10, Pin.OUT, value=1)
    CS = Pin(11, Pin.OUT, value=1)
    RST = Pin(12, Pin.OUT, value=1)

    RST.value(1); time.sleep_ms(20)
    RST.value(0); time.sleep_ms(50)
    RST.value(1); time.sleep_ms(200)

    CS.value(0)
    RS.value(0)
    for i in range(8):                      # command 0xD3, RDDID4
        D[i].value((0xD3 >> i) & 1)
    WR.value(0); WR.value(1)
    RS.value(1)

    got = []
    for p in D:
        p.init(Pin.IN)
    for _ in range(4):
        RD.value(0)
        time.sleep_us(2)
        v = 0
        for i in range(8):
            v |= D[i].value() << i
        RD.value(1)
        time.sleep_us(1)
        got.append(v)
    for p in D:
        p.init(Pin.OUT)
    CS.value(1)

    for p in (4, 5, 6, 7, 15, 16, 17, 18, 8, 9, 10, 11, 12):
        Pin(p, Pin.IN, None)                # release, so stage 1 is honest

    print("    reg 0xD3 -> %s" % " ".join("%02X" % b for b in got))
    _tft_id = (got[2] << 8) | got[3]

    if _tft_id == 0x9341:
        print("    ID 0x9341 = ILI9341.  The panel answered.")
        print("    THE BUS IS PROVEN GOOD - data went out and came back on")
        print("    the same 13 lines.  TFT pin-state faults are suppressed")
        print("    below; a static reading cannot overrule this.")
    elif _tft_id:
        print("    ID 0x%04X - the bus works, but this is NOT an ILI9341." %
              _tft_id)
        _fault(1, "panel controller is 0x%04X, not 0x9341" % _tft_id,
               "ili9341_par.py will give a white screen on this part no "
               "matter how good the wiring is")
    else:
        print("    no answer.  Either RD (GPIO9) is not wired, the panel has")
        print("    no read path, or the bus really is broken.  Stage 1 below")
        print("    now matters - run it with the ribbon UNPLUGGED.")
    return _tft_id


def _fault(sev, what, why):
    """sev: 1 = fatal, 2 = probable, 3 = worth a look."""
    _faults.append((sev, what, why))


def _state(gpio):
    """Float test. Returns FLOAT / LOW / HIGH / DRIVEN."""
    up = Pin(gpio, Pin.IN, Pin.PULL_UP).value()
    time.sleep_ms(2)
    dn = Pin(gpio, Pin.IN, Pin.PULL_DOWN).value()
    time.sleep_ms(2)
    if up == 1 and dn == 0:
        return FLOAT
    if up == 0 and dn == 0:
        return LOW
    if up == 1 and dn == 1:
        return HIGH
    return DRIVEN


# ---------------------------------------------------------------------------
def pin_states():
    """Every pin the project uses, and what is holding it."""
    # Run the functional display test first if it has not run this session.
    # Without it _tft_id stays None, the shield's level-shifter network reads
    # as 13 tied lines, and calling pin_states() on its own invents a fault
    # that run() would have suppressed. Same file, two different answers.
    if _tft_id is None:
        tft_alive()

    print("\n" + "=" * 62)
    print("  1. PIN STATES - what is holding each line")
    print("=" * 62)

    print("\n  TFT lines (all 13 should read FLOATING with the ribbon OUT)")
    tied = set()
    states = {}
    for gpio, name in TFT:
        st = _state(gpio)
        states[gpio] = st
        if st != FLOAT:
            tied.add(gpio)
        print("    GPIO%-3d %-9s %-10s %s"
              % (gpio, name, st, "" if st == FLOAT else "<<<"))

    uniform = len(set(states.values())) == 1 and FLOAT not in states.values()

    if not tied:
        print("    all 13 float - no display line is shorted to a rail")
    elif _tft_id == 0x9341:
        print("\n    IGNORE the <<< marks. The panel answered in stage 0, so")
        print("    these lines demonstrably carry data. What you are reading")
        print("    is the shield's level-shifter network - about 2k to ground")
        print("    on each signal, against a 45k internal pull-up. No fault.")
    elif uniform:
        print("\n    All 13 read the SAME state. That is one resistor network,")
        print("    not 13 independent shorts - almost certainly the shield's")
        print("    level shifters. Unplug the ribbon and re-run to be sure.")
        _fault(3, "all 13 TFT lines read %s" % states[TFT[0][0]],
               "uniform across every line = a network, not shorts. Re-run "
               "with the display UNPLUGGED before treating this as a fault")
    else:
        for gpio, name in TFT:
            if states[gpio] != FLOAT:
                _fault(1, "TFT %s (GPIO%d) is %s" % (name, gpio, states[gpio]),
                       "a display line shorted to a rail cannot carry data - "
                       "this alone gives a white screen")

    print("\n  Sensor DO lines (should read DRIVEN or TIED HIGH - a module is"
          " holding them)")
    for gpio, name, _ in DRIVEN_EXPECTED:
        st = _state(gpio)
        print("    GPIO%-3d %-14s %-10s %s"
              % (gpio, name, st, "<<< module not connected" if st == FLOAT else ""))
        if st == FLOAT:
            _fault(2, "%s (GPIO%d) is floating" % (name, gpio),
                   "its module is not driving the pin - VCC, GND or the "
                   "signal wire has come out")
        elif st == LOW:
            # An SW-420 idling LOW is a pot wound past its trip point. The
            # module still counts knocks perfectly, because the ISR triggers
            # on EDGES, not on level. This used to raise a fault and send you
            # hunting a wiring problem that was never there. Note, not fault.
            print("        (idles LOW - pot past the trip point. Harmless if"
                  " test_sw420.py counts taps.)")

    print("\n  Button and strip")
    st = _state(pins.BTN_A)
    print("    GPIO%-3d %-14s %-10s %s" % (pins.BTN_A, "button", st,
          "(known: wrong leg pair)" if st == LOW else ""))
    st = _state(pins.LED_STRIP)
    print("    GPIO%-3d %-14s %-10s" % (pins.LED_STRIP, "WS2812 DIN", st))

    print("\n  I2C lines (both MUST read TIED HIGH - the MPU pull-ups)")
    for gpio, name in ((pins.I2C_SCL, "SCL"), (pins.I2C_SDA, "SDA")):
        st = _state(gpio)
        ok = st in (HIGH, DRIVEN)
        print("    GPIO%-3d %-14s %-10s %s" % (gpio, name, st, "" if ok else "<<<"))
        if st == FLOAT:
            _fault(1, "I2C %s (GPIO%d) is floating" % (name, gpio),
                   "no pull-up means no MPU is powered - check 3V3 to both "
                   "modules")
        elif st == LOW:
            _fault(1, "I2C %s (GPIO%d) stuck LOW" % (name, gpio),
                   "a dead device is holding the bus down, or the wire is "
                   "shorted to ground")

    print("\n  DHT11")
    st = _state(pins.DHT)
    print("    GPIO%-3d %-14s %-10s" % (pins.DHT, "DHT11 DATA", st))
    return tied


# ---------------------------------------------------------------------------
def tft_shorts(skip=None):
    """Pin-to-pin shorts across the display lines.

    Pull one line low in OPEN-DRAIN mode, read every other line with its
    pull-up on. Any line that follows is shorted to the driven one.

    Open-drain matters twice. It only ever PULLS LOW, so it never pushes
    current into a short. And value() on an open-drain pin reads the REAL
    line; a push-pull pin read back just reports what you told it, which
    tells you nothing.

    This is THE test for a loom pulled through a sleeve. Two crimps pushed
    together each read perfectly on a continuity check to the ESP32 and still
    short to each other - a meter on one wire at a time will never find it.

    skip: pins already known TIED LOW. They read 0 no matter who is driving,
    so leaving them in makes every other line look shorted to them and one
    real fault becomes twelve false ones.
    """
    skip = skip or set()
    names = dict(TFT)
    print("\n" + "=" * 62)
    print("  2. TFT PIN-TO-PIN SHORTS")
    print("=" * 62)
    if skip:
        print("  skipping %s - already tied low, they would read as shorted"
              % ", ".join("GPIO%d" % g for g in sorted(skip)))
        print("  to everything and bury the real result")
    print("  pulling each display line low, watching the others\n")

    found = []
    seen = set()
    for gpio, name in TFT:
        if gpio in skip:
            continue
        try:
            drv = Pin(gpio, Pin.OPEN_DRAIN, Pin.PULL_UP)
        except (TypeError, ValueError):
            drv = Pin(gpio, Pin.OPEN_DRAIN)
        drv.value(0)
        time.sleep_ms(3)
        for other, oname in TFT:
            if other == gpio or other in skip:
                continue
            if Pin(other, Pin.IN, Pin.PULL_UP).value() == 0:
                pair = (gpio, other) if gpio < other else (other, gpio)
                if pair not in seen:
                    seen.add(pair)
                    found.append(pair)
        drv.value(1)
        Pin(gpio, Pin.IN)
        time.sleep_ms(3)

    if not found:
        print("  no shorts between any two display lines")
    else:
        for a, b in found:
            print("  SHORT: GPIO%-3d %-9s <->  GPIO%-3d %s"
                  % (a, names[a], b, names[b]))
            _fault(1, "GPIO%d (%s) and GPIO%d (%s) are shorted"
                   % (a, names[a], b, names[b]),
                   "two display lines on one wire cannot both carry data - "
                   "separate those two crimps")
    return found


# ---------------------------------------------------------------------------
def i2c_check():
    print("\n" + "=" * 62)
    print("  3. I2C BUS")
    print("=" * 62 + "\n")
    try:
        bus = I2C(0, scl=Pin(pins.I2C_SCL), sda=Pin(pins.I2C_SDA), freq=100000)
        found = bus.scan()
    except Exception as e:
        print("    ERROR %r" % e)
        _fault(1, "I2C bus would not initialise", repr(e))
        return []
    if not found:
        print("    nothing on the bus")
        _fault(1, "no I2C devices answer",
               "both MPUs have lost power or a bus wire. Check 3V3 and GND "
               "to both modules before anything else")
    for a in found:
        tag = ""
        if a == pins.MPU_TOP:
            tag = "  <- MPU top (AD0 low)"
        elif a == pins.MPU_BOT:
            tag = "  <- MPU bottom (AD0 high)"
        print("    0x%02X%s" % (a, tag))
    for addr, label in ((pins.MPU_TOP, "MPU top"), (pins.MPU_BOT, "MPU bottom")):
        if addr not in found:
            _fault(2, "%s (0x%02X) missing" % (label, addr),
                   "power, SDA/SCL, or AD0 has come loose on that module")
    return found


# ---------------------------------------------------------------------------
def adc_check():
    print("\n" + "=" * 62)
    print("  4. MQ-2 ANALOG CHANNELS")
    print("=" * 62 + "\n")
    out = {}
    for label, gpio in (("MQ-2 #1", pins.MQ2_1), ("MQ-2 #2", pins.MQ2_2)):
        try:
            rd = pins.make_adc(gpio)
            v = sum(rd() for _ in range(16)) // 16
            out[label] = v
            if v < 30:
                note = "<<< reads ~0 - AO wire off, or module unpowered"
                _fault(2, "%s reads %d" % (label, v),
                       "AO disconnected or the module has lost 5 V")
            elif v > 4050:
                note = "<<< railed - AO on 5 V with no divider, or shorted high"
                _fault(2, "%s railed at %d" % (label, v), "check the AO wire")
            else:
                note = "plausible"
            print("    %-8s GPIO%-3d raw %4d   %s" % (label, gpio, v, note))
        except Exception as e:
            print("    %-8s GPIO%-3d ERROR %r" % (label, gpio, e))
            _fault(2, "%s ADC failed" % label, repr(e))
    return out


# ---------------------------------------------------------------------------
def digital_check():
    print("\n" + "=" * 62)
    print("  5. DIGITAL SENSOR IDLE STATES")
    print("=" * 62 + "\n")
    for gpio, name, idle in DRIVEN_EXPECTED:
        v = Pin(gpio, Pin.IN, Pin.PULL_UP).value()
        print("    GPIO%-3d %-14s reads %d   %s"
              % (gpio, name, v, "expected %d" % idle if v != idle else "ok"))


# ---------------------------------------------------------------------------
def dht_check():
    print("\n" + "=" * 62)
    print("  6. DHT11")
    print("=" * 62 + "\n")
    try:
        import dht
        d = dht.DHT11(Pin(pins.DHT))
        time.sleep_ms(1200)
        d.measure()
        print("    %d C   %d %%RH   ok" % (d.temperature(), d.humidity()))
        return True
    except Exception as e:
        print("    failed: %r" % e)
        _fault(2, "DHT11 not responding", repr(e))
        return False


# ---------------------------------------------------------------------------
def verdict():
    print("\n" + "=" * 62)
    print("  VERDICT")
    print("=" * 62 + "\n")
    if not _faults:
        print("  Nothing wrong found. If the screen is still white, the fault")
        print("  is on the PANEL side of the wires - VCC or GND at the TFT")
        print("  connector itself, which no GPIO test can see.")
        print("\n  Meter 3.3 V between the TFT's own VCC and GND pads.")
        return

    _faults.sort(key=lambda f: f[0])
    sev_name = {1: "FATAL   ", 2: "PROBABLE", 3: "MINOR   "}
    for sev, what, why in _faults:
        print("  [%s] %s" % (sev_name[sev], what))
        print("             %s" % why)
    print("\n  %d issue(s). Fix the FATAL ones first." % len(_faults))
    if _tft_id == 0x9341:
        print("  The display answered in stage 0, so nothing here explains a")
        print("  white screen - the panel and its 13 lines are proven good.")


def run():
    global _faults
    _faults = []
    print("\n" + "#" * 62)
    print("#  GENIE board doctor - full sweep")
    print("#  nothing here is destructive; sensors are never driven against")
    print("#" * 62)
    pins.check()
    tft_alive()
    tied = pin_states()
    tft_shorts(skip=tied)
    i2c_check()
    adc_check()
    digital_check()
    dht_check()
    verdict()
    print("\n  When done, re-seat and run:  import hello_tft; hello_tft.go()")
    print("  A red screen there means the display wiring is good again.\n")


if __name__ == "__main__":
    run()
