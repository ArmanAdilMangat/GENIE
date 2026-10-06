"""
test_tft.py - GENIE display bring-up.  ILI9341 / 8-bit 8080 parallel.

RUN THIS FIRST, WITH ONLY THE TFT WIRED.  No sensors, nothing on P2.

    >>> import test_tft
    >>> test_tft.run()

Why this file exists
--------------------
A pin-state "doctor" that runs after a SOFT reboot reads leftover output
levels and reports them as shorts to a rail.  MicroPython's soft reboot does
NOT reset GPIO.  Every test here calls release() first, so a reading of
FLOATING actually means floating.

Wiring, frozen, P1 header only
-----------------------------
    D0 D1 D2 D3 -> GPIO  4  5  6  7
    D4 D5 D6 D7 -> GPIO 15 16 17 18
    WR 8   RD 9   RS/DC 10   CS 11   RST 12
    VCC -> 5V   (MCUFRIEND shields regulate 5V down themselves)
    GND -> GND

Order of tests
--------------
    1  release + pin states      is anything holding a line?
    2  panel ID read             is the controller alive and is it an ILI9341?
    3  solid colour fills        do all 8 data lines carry data?
    4  colour bars               which data line is wrong, if any
    5  fast driver               does the real viper driver work
"""

from machine import Pin
import time

# --------------------------------------------------------------------------
# pin map
# --------------------------------------------------------------------------
D_PINS = (4, 5, 6, 7, 15, 16, 17, 18)          # D0 .. D7
PIN_WR, PIN_RD, PIN_RS, PIN_CS, PIN_RST = 8, 9, 10, 11, 12
ALL_PINS = D_PINS + (PIN_WR, PIN_RD, PIN_RS, PIN_CS, PIN_RST)

NAMES = {4: "D0", 5: "D1", 6: "D2", 7: "D3", 15: "D4", 16: "D5",
         17: "D6", 18: "D7", 8: "WR", 9: "RD", 10: "RS", 11: "CS",
         12: "RST"}

WIDTH, HEIGHT = 240, 320                        # native, rotation 0

RED, GREEN, BLUE = 0xF800, 0x07E0, 0x001F
WHITE, BLACK, YELLOW = 0xFFFF, 0x0000, 0xFFE0
CYAN, MAGENTA = 0x07FF, 0xF81F

D = None
WR = RD = RS = CS = RST = None


# --------------------------------------------------------------------------
# bus
# --------------------------------------------------------------------------
def release():
    """Every display pin back to high-Z input.

    Run before any pin-state reading.  Without this a soft reboot leaves the
    pins driven and every diagnostic lies.
    """
    global D, WR, RD, RS, CS, RST
    for p in ALL_PINS:
        Pin(p, Pin.IN, None)
    D = None
    WR = RD = RS = CS = RST = None


def claim():
    global D, WR, RD, RS, CS, RST
    D = [Pin(p, Pin.OUT) for p in D_PINS]
    WR = Pin(PIN_WR, Pin.OUT, value=1)
    RD = Pin(PIN_RD, Pin.OUT, value=1)
    RS = Pin(PIN_RS, Pin.OUT, value=1)
    CS = Pin(PIN_CS, Pin.OUT, value=1)
    RST = Pin(PIN_RST, Pin.OUT, value=1)


def wr8(b):
    for i in range(8):
        D[i].value((b >> i) & 1)
    WR.value(0)
    WR.value(1)


def rd8():
    """Turn the bus around and read one byte back from the panel."""
    for p in D:
        p.init(Pin.IN)
    RD.value(0)
    time.sleep_us(2)
    v = 0
    for i in range(8):
        v |= D[i].value() << i
    RD.value(1)
    time.sleep_us(1)
    for p in D:
        p.init(Pin.OUT)
    return v


def cmd(c):
    RS.value(0)
    wr8(c)
    RS.value(1)


def dat(b):
    wr8(b)


def hard_reset():
    RST.value(1); time.sleep_ms(20)
    RST.value(0); time.sleep_ms(50)
    RST.value(1); time.sleep_ms(200)


def init_panel():
    """Shortest ILI9341 init that paints.  No gamma, no power tuning."""
    cmd(0x01); time.sleep_ms(200)       # software reset
    cmd(0x28)                           # display off
    cmd(0x3A); dat(0x55)                # 16 bpp
    cmd(0x36); dat(0x48)                # MADCTL, rotation 0
    cmd(0x11); time.sleep_ms(200)       # sleep out
    cmd(0x29); time.sleep_ms(100)       # display on


def window(x, y, w, h):
    x1, y1 = x + w - 1, y + h - 1
    cmd(0x2A); dat(x >> 8); dat(x & 0xFF); dat(x1 >> 8); dat(x1 & 0xFF)
    cmd(0x2B); dat(y >> 8); dat(y & 0xFF); dat(y1 >> 8); dat(y1 & 0xFF)


def fill(x, y, w, h, colour):
    window(x, y, w, h)
    cmd(0x2C)
    hi, lo = colour >> 8, colour & 0xFF
    for _ in range(w * h):
        wr8(hi)
        wr8(lo)


# --------------------------------------------------------------------------
# 1 - pin states
# --------------------------------------------------------------------------
def t1_pins():
    print("=" * 62)
    print("  1. PIN STATES  (release first, then read)")
    print("=" * 62)
    release()
    time.sleep_ms(50)

    bad = []
    for p in ALL_PINS:
        up = Pin(p, Pin.IN, Pin.PULL_UP).value()
        time.sleep_ms(2)
        dn = Pin(p, Pin.IN, Pin.PULL_DOWN).value()
        Pin(p, Pin.IN, None)
        if up == 1 and dn == 0:
            state = "floating"
        elif up == 0 and dn == 0:
            state = "HELD LOW"
            bad.append((p, state))
        elif up == 1 and dn == 1:
            state = "HELD HIGH"
            bad.append((p, state))
        else:
            state = "??"
            bad.append((p, state))
        print("    GPIO%-3d %-4s  %s" % (p, NAMES[p], state))

    if bad:
        print("\n  %d line(s) held.  With the ribbon UNPLUGGED that means a"
              % len(bad))
        print("  solder bridge.  With it PLUGGED IN it is usually just the")
        print("  panel's own bus - re-run with the display disconnected to")
        print("  tell the two apart.")
    else:
        print("\n  PASS - all 13 lines float.  No solder bridges.")
    return not bad


# --------------------------------------------------------------------------
# 2 - who is on the bus
# --------------------------------------------------------------------------
KNOWN = {0x9341: "ILI9341", 0x9325: "ILI9325", 0x9328: "ILI9328",
         0x9486: "ILI9486", 0x9488: "ILI9488", 0x7789: "ST7789",
         0x7735: "ST7735", 0x8357: "HX8357", 0x1289: "SSD1289"}


def t2_id():
    print("=" * 62)
    print("  2. PANEL ID  (reads the controller back over the bus)")
    print("=" * 62)
    claim()
    hard_reset()
    CS.value(0)

    out = {}
    for reg, n in ((0xD3, 4), (0x04, 4), (0xBF, 6), (0xA1, 5)):
        cmd(reg)
        out[reg] = [rd8() for _ in range(n)]
        print("    reg 0x%02X -> %s"
              % (reg, " ".join("%02X" % b for b in out[reg])))
    CS.value(1)

    ident = 0
    d3 = out[0xD3]
    if d3[2] or d3[3]:
        ident = (d3[2] << 8) | d3[3]
    else:
        r4 = out[0x04]
        if r4[2] or r4[3]:
            ident = (r4[2] << 8) | r4[3]

    if ident == 0:
        print("\n    nothing readable.  Either RD (GPIO9) is not wired, or")
        print("    the panel has no read path (common on cheap SPI-converted")
        print("    boards).  This alone does NOT mean the display is dead -")
        print("    go on to test 3.")
        return None

    name = KNOWN.get(ident, "UNKNOWN")
    print("\n    controller ID 0x%04X = %s" % (ident, name))
    if name == "ILI9341":
        print("    PASS - matches the driver this project uses.")
    elif name == "UNKNOWN":
        print("    ID does not match any driver in the table.  Check the")
        print("    print on the ribbon before writing an init sequence.")
    else:
        print("    MISMATCH.  ili9341_par.py will give a WHITE SCREEN on a")
        print("    %s.  That is your bug." % name)
    return ident


# --------------------------------------------------------------------------
# 3 - solid fills
# --------------------------------------------------------------------------
def t3_fills(pause=2):
    print("=" * 62)
    print("  3. SOLID FILLS  (watch the screen)")
    print("=" * 62)
    claim()
    hard_reset()
    CS.value(0)
    init_panel()

    seq = ((RED, "RED"), (GREEN, "GREEN"), (BLUE, "BLUE"),
           (WHITE, "WHITE"), (BLACK, "BLACK"))
    for colour, label in seq:
        print("    filling %-6s ... (slow on purpose, ~20 s)" % label)
        fill(0, 0, WIDTH, HEIGHT, colour)
        time.sleep(pause)
    CS.value(1)

    print("""
    Which colours were wrong tells you which data lines are wrong:

      RED   wrong  ->  D3..D7  (GPIO 7, 15, 16, 17, 18)
      GREEN wrong  ->  D0..D2 (GPIO 4,5,6) and D5..D7 (GPIO 16,17,18)
      BLUE  wrong  ->  D0..D4  (GPIO 4, 5, 6, 7, 15)
      ALL   white  ->  no data reaching the panel at all: check WR (GPIO8),
                       RS (GPIO10), CS (GPIO11), or the init sequence
      backlight only, never changes -> RST (GPIO12) not pulsed, or wrong
                       controller.  Run t2_id().
    """)


# --------------------------------------------------------------------------
# 4 - colour bars
# --------------------------------------------------------------------------
def t4_bars():
    print("=" * 62)
    print("  4. COLOUR BARS  (8 bands, top to bottom)")
    print("=" * 62)
    claim()
    hard_reset()
    CS.value(0)
    init_panel()

    bars = ((WHITE, "white"), (YELLOW, "yellow"), (CYAN, "cyan"),
            (GREEN, "green"), (MAGENTA, "magenta"), (RED, "red"),
            (BLUE, "blue"), (BLACK, "black"))
    band = HEIGHT // len(bars)
    for i, (colour, label) in enumerate(bars):
        fill(0, i * band, WIDTH, band, colour)
        print("    band %d  %s" % (i + 1, label))
    CS.value(1)
    print("\n    All 8 bands correct and in order = the bus is good.")
    print("    A band the wrong colour = that colour's data lines (see t3).")
    print("    Bands smeared or repeated = WR (GPIO8) timing / bad solder.")


# --------------------------------------------------------------------------
# 5 - the real driver
# --------------------------------------------------------------------------
def t5_driver():
    print("=" * 62)
    print("  5. FAST DRIVER  (ili9341_par.py, viper)")
    print("=" * 62)
    release()
    try:
        from ili9341_par import ILI9341Par, color565
    except ImportError:
        print("    ili9341_par.py is not on the device.")
        print("    Upload it FLAT to the device root, then re-run.")
        return False

    t = time.ticks_ms()
    tft = ILI9341Par(rotation=1)
    print("    init took %d ms" % time.ticks_diff(time.ticks_ms(), t))

    for colour, label in ((color565(255, 0, 0), "red"),
                          (color565(0, 255, 0), "green"),
                          (color565(0, 0, 255), "blue")):
        t = time.ticks_ms()
        tft.fill_screen(colour)
        print("    full-screen %-5s  %4d ms"
              % (label, time.ticks_diff(time.ticks_ms(), t)))
        time.sleep_ms(400)

    tft.fill_screen(0)
    print("\n    Under ~120 ms per full screen = viper is compiling and the")
    print("    bus is running at full speed.  PASS.")
    return True


# --------------------------------------------------------------------------
def run():
    print("\nGENIE TFT bring-up - ONLY the display should be wired\n")
    t1_pins()
    print()
    t2_id()
    print()
    t3_fills()
    print()
    t4_bars()
    print()
    t5_driver()
    print("\nDone.  Screen coloured and bars in order = display PASSES.")
    print("Next: Testing/01_MQ2_Gas\n")


if __name__ == "__main__":
    run()
