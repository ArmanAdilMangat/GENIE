"""GENIE Node 2 -- R307S final GO / NO-GO probe.

SCRIPT. Open in Thonny, press F5. Do NOT upload it.
Needs nothing on the board. No r307.py, no pins3.py, no imports of your code.
That is deliberate: when you are deciding whether a module is dead, the probe
must not be able to be the reason it looks dead.

WIRING THIS ASSUMES  (see WIRING.md)
    module RXD  (green)  <- GPIO17    ESP TX
    module TXD  (yellow) -> GPIO18    ESP RX
    module WAKEUP (blue) -> GPIO16    touch out, active LOW on your unit
    module VCC  (red)    -> 5 V RAIL, not the 3V3 rail, not the DevKit 3V3 pin
    module VT   (white)  -> ESP32 3V3
    module GND  (black)  -> rail GND *and* ESP32 GND, one common node

WHAT THIS ANSWERS, IN ORDER
    A  Is the module's touch circuit alive?        no UART involved
    B  Is the module's TXD line actually driving?  no UART involved
    C  Does anything arrive on RX at all?
    D  Does it answer a handshake at any baud, either pin order?
    E  Will the ring light on any LED command or on a capture?

A and B are the new ones. They are electrical tests done with pull-resistors,
and they are what tells power/wire faults apart from a dead die. Everything
that came before this file jumped straight to D, which cannot distinguish them.
"""

VERSION = "fp_probe 1.0  24-08-2026"

from machine import UART, Pin
import time

# ================================================================== CONFIG
TX_PIN = 17          # ESP TX  -> module RXD
RX_PIN = 18          # ESP RX  <- module TXD
TOUCH  = 16          # module WAKEUP
BAUD   = 57600       # R307 factory default

BAUDS = (57600, 9600, 19200, 38400, 115200)

# Packets built by hand so this file depends on no driver.
# Layout:  EF01 | FFFFFFFF | PID | LEN_HI LEN_LO | DATA... | CK_HI CK_LO
# checksum = PID + LEN_HI + LEN_LO + sum(DATA)
PKT_HANDSHAKE = bytes((0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF,
                       0x01, 0x00, 0x07, 0x13,
                       0x00, 0x00, 0x00, 0x00, 0x00, 0x1B))
PKT_SYSPARAM  = bytes((0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF,
                       0x01, 0x00, 0x03, 0x0F, 0x00, 0x13))
PKT_GETIMAGE  = bytes((0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF,
                       0x01, 0x00, 0x03, 0x01, 0x00, 0x05))
PKT_COUNT     = bytes((0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF,
                       0x01, 0x00, 0x03, 0x1D, 0x00, 0x21))

RESULT = {}


# ================================================================= helpers
def hexs(b):
    return " ".join("%02X" % x for x in b)


def rule(ch="-"):
    print(ch * 66)


def head(n, title):
    print("")
    rule("=")
    print("  TEST %s  %s" % (n, title))
    rule("=")


def ask(prompt):
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def aura(ctrl, speed, colour, times):
    """Build an AuraLedConfig (0x35) packet."""
    data = bytes((0x35, ctrl, speed, colour, times))
    ln = len(data) + 2
    ck = (0x01 + (ln >> 8) + (ln & 0xFF) + sum(data)) & 0xFFFF
    return (bytes((0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01)) +
            bytes(((ln >> 8) & 0xFF, ln & 0xFF)) + data +
            bytes(((ck >> 8) & 0xFF, ck & 0xFF)))


def free_uart():
    """Release UART1 so 17/18 can be read as plain GPIOs."""
    try:
        UART(1).deinit()
    except Exception:
        pass
    time.sleep_ms(50)


def driven_high(pin_no):
    """True only if something EXTERNAL is holding the pin high.

    An internal pull-down loses to any real external driver or pull-up, and
    wins against a floating wire. A bare Pin.IN read cannot tell those apart --
    a floating pin holds residual charge and reads 1. This is the same trick
    that found the broken SDA wire on 15-08; it has never been pointed at the
    fingerprint lines before.
    """
    p = Pin(pin_no, Pin.IN, Pin.PULL_DOWN)
    time.sleep_ms(30)
    votes = 0
    for _ in range(20):
        votes += p.value()
        time.sleep_ms(5)
    return votes >= 18, votes


# =========================================================== TEST A  touch
def test_a_touch():
    head("A", "touch circuit -- is ANY part of the module alive?")
    print("  The touch ring runs off VT (white -> 3V3) on its own circuit,")
    print("  independent of the module's MCU and of UART entirely. If this")
    print("  reacts, the die has power and the blue wire is intact, whatever")
    print("  the UART does later.")
    print("")
    free_uart()
    p = Pin(TOUCH, Pin.IN, Pin.PULL_UP)
    time.sleep_ms(50)

    idle = p.value()
    print("  idle level on GPIO%d = %d" % (TOUCH, idle))
    print("")
    print("  Now REST A FINGER on the sensor glass and hold it there.")
    print("  Watching for 12 s...")
    print("")

    t0 = time.ticks_ms()
    changed = False
    last = idle
    lo = hi = 0
    while time.ticks_diff(time.ticks_ms(), t0) < 12000:
        v = p.value()
        if v:
            hi += 1
        else:
            lo += 1
        if v != last:
            print("    GPIO%d -> %d   at %d ms"
                  % (TOUCH, v, time.ticks_diff(time.ticks_ms(), t0)))
            changed = True
            last = v
        time.sleep_ms(20)

    print("")
    print("  samples high=%d  low=%d" % (hi, lo))
    if changed:
        print("  RESULT: TOUCH RESPONDS. The module has power and pin 5 is")
        print("          intact. A 'dead module' verdict is now much less")
        print("          likely -- keep going.")
    else:
        print("  RESULT: no movement. Either VT (white) is not on 3V3, the")
        print("          blue wire is broken, or the module has no power at")
        print("          all. This does NOT on its own prove the MCU is dead.")
    RESULT["touch"] = changed
    return changed


# ============================================================ TEST B  TXD
def test_b_txd():
    head("B", "module TXD line -- is the UART transmitter driving?")
    print("  A running UART holds its TX line HIGH when idle. So GPIO%d"
          % RX_PIN)
    print("  should be held high from outside. Internal pull-down decides it:")
    print("    high  -> module TXD is driving -> its MCU is running")
    print("    low   -> nothing on the wire   -> MCU not running, or wire")
    print("             broken, or yellow is not on GPIO%d" % RX_PIN)
    print("")
    free_uart()

    ok_rx, votes_rx = driven_high(RX_PIN)
    print("  GPIO%d (module TXD)  held high in %d/20 samples -> %s"
          % (RX_PIN, votes_rx, "DRIVEN" if ok_rx else "FLOATING"))

    # GPIO17 goes to the module's RXD *input*. Measured 24-08-2026: it also
    # reads DRIVEN, because the R307's UART receiver has an internal pull-up
    # to its own 3V3. That is a useful result, not an artefact -- it means the
    # green wire is intact AND the far end is powered. A broken green wire
    # reads FLOATING here while GPIO18 still reads DRIVEN, and that specific
    # pair is the signature of "module talks, module cannot hear us".
    ok_tx, votes_tx = driven_high(TX_PIN)
    print("  GPIO%d (module RXD)  held high in %d/20 samples -> %s"
          % (TX_PIN, votes_tx, "DRIVEN" if ok_tx else "FLOATING"))

    print("")
    if ok_rx and ok_tx:
        print("  RESULT: both lines driven. The module's transmitter is")
        print("          powered and idle-high, and its receiver is pulling")
        print("          our TX line up -- so both wires are intact and the")
        print("          far end has power. Not a dead module. Go to TEST D.")
    elif ok_rx:
        print("  RESULT: the module's UART transmitter IS powered and idle-")
        print("          high, so it is not a dead module -- but GPIO%d is"
              % TX_PIN)
        print("          floating, which means the GREEN wire is broken or")
        print("          in the wrong hole. It can talk; it cannot hear us.")
        print("          Replace that one wire, do not re-seat it.")
    else:
        print("  RESULT: nothing is driving GPIO%d." % RX_PIN)
        print("          Three causes, in order of likelihood:")
        print("            1. VCC is not really 5 V at the module")
        print("            2. the yellow wire is broken or in the wrong hole")
        print("            3. the module's MCU is dead")
        print("          Confirm 1 and 2 with the meter before believing 3.")
    RESULT["txd_driven"] = ok_rx
    return ok_rx


# ========================================================= TEST C  listen
def test_c_listen(seconds=8):
    head("C", "passive listen -- do ANY bytes arrive unprompted?")
    print("  A healthy R307 says nothing unasked, so silence here is normal")
    print("  and proves nothing. Noise here means a wrong baud or a floating")
    print("  RX pin, and that IS worth knowing.")
    print("")
    u = UART(1, baudrate=BAUD, tx=TX_PIN, rx=RX_PIN,
             bits=8, parity=None, stop=1, timeout=200)
    time.sleep_ms(100)
    while u.any():
        u.read()

    t0 = time.ticks_ms()
    got = b""
    while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
        if u.any():
            got += u.read()
        time.sleep_ms(20)
    u.deinit()

    if got:
        print("  %d bytes: %s" % (len(got), hexs(got[:32])))
        print("  RESULT: unsolicited traffic. Wrong baud, or GPIO%d is picking"
              % RX_PIN)
        print("          up noise because nothing is driving it.")
    else:
        print("  silence -- normal, carry on.")
    RESULT["listen"] = got
    return got


# ======================================================== TEST D  handshake
def _exchange(u, pkt, wait_ms=700):
    while u.any():
        u.read()
    u.write(pkt)
    t0 = time.ticks_ms()
    buf = b""
    while time.ticks_diff(time.ticks_ms(), t0) < wait_ms:
        if u.any():
            buf += u.read()
            if len(buf) >= 12:
                break
        time.sleep_ms(5)
    return buf


def _valid(buf):
    return len(buf) >= 10 and buf[0] == 0xEF and buf[1] == 0x01 and buf[6] == 0x07


def test_d_handshake():
    head("D", "handshake sweep -- 5 bauds x 2 pin orders x 4 commands")
    print("  40 exchanges. A good reply starts  EF 01 FF FF FF FF 07")
    print("")
    hits = []
    for tx, rx in ((TX_PIN, RX_PIN), (RX_PIN, TX_PIN)):
        for baud in BAUDS:
            u = UART(1, baudrate=baud, tx=tx, rx=rx,
                     bits=8, parity=None, stop=1, timeout=300)
            # The R307 needs a moment after any line disturbance before it
            # will accept a command. 400 ms is generous and costs nothing.
            time.sleep_ms(400)

            tag = "TX=%-2d RX=%-2d @ %-6d" % (tx, rx, baud)
            line = []
            good = False
            for name, pkt in (("hshk", PKT_HANDSHAKE),
                              ("sysp", PKT_SYSPARAM),
                              ("cnt ", PKT_COUNT),
                              ("img ", PKT_GETIMAGE)):
                buf = _exchange(u, pkt)
                if _valid(buf):
                    good = True
                    line.append("%s=OK(0x%02X)" % (name, buf[9]))
                elif buf:
                    line.append("%s=junk" % name)
                else:
                    line.append("%s=-" % name)
            u.deinit()

            print("  %s  %s" % (tag, "  ".join(line)))
            if good:
                hits.append((tx, rx, baud))

    print("")
    if hits:
        tx, rx, baud = hits[0]
        print("  RESULT: MODULE IS ALIVE.")
        print("          Use  R307(tx=%d, rx=%d, baud=%d)" % (tx, rx, baud))
        if (tx, rx) != (TX_PIN, RX_PIN):
            print("          NOTE: your green and yellow wires are SWAPPED.")
        if baud != BAUD:
            print("          NOTE: it is running at %d, not %d." % (baud, BAUD))
    else:
        print("  RESULT: silent on all 10 combinations.")
    RESULT["hits"] = hits
    return hits


# ============================================================== TEST E  LED
def test_e_led(tx, rx, baud):
    head("E", "ring illumination -- every mode, then a real capture")
    print("  Two things to know before you read anything into this:")
    print("")
    print("   1. Your old r307.py led() always sent colour=0x01, which IS")
    print("      red. Blue is 0x02. Every LED command this project ever sent")
    print("      asked for red -- which is why you never saw blue.")
    print("   2. VERIFIED 24-08-2026: this module answers 0x00 to all nine")
    print("      ctrl x colour combinations. AuraLedConfig is fully")
    print("      supported here. The ring can do red, blue and purple.")
    print("")
    print("  The aura ring is DIM by design -- it is an indicator, not the")
    print("  capture lamp, and 0x35 has no brightness field. The bright")
    print("  illumination is separate and fires only during a real capture,")
    print("  which is what the GetImage block below is for. Press a finger")
    print("  down for those or they return 0x02 and nothing lights.")
    print("")
    print("  Watch the sensor glass in a DIM room for the next ~40 s.")
    print("")
    u = UART(1, baudrate=baud, tx=tx, rx=rx, bits=8, parity=None,
             stop=1, timeout=300)
    time.sleep_ms(400)

    names = {1: "breathe", 2: "flash", 3: "always on", 4: "always off"}
    cols  = {1: "red", 2: "blue", 3: "purple"}
    for colour in (1, 2, 3):
        for ctrl in (3, 2, 1):
            buf = _exchange(u, aura(ctrl, 0x40, colour, 0x00), 600)
            code = "0x%02X" % buf[9] if _valid(buf) else "no reply"
            print("    %-10s %-7s -> %s" % (names[ctrl], cols[colour], code))
            time.sleep(2)
        _exchange(u, aura(4, 0x40, colour, 0x00), 600)

    print("")
    print("  Now 6 x GetImage. On most R307 firmware the ring only lights")
    print("  DURING a capture, so this is the honest test. Put a finger on")
    print("  the glass now.")
    for i in range(6):
        buf = _exchange(u, PKT_GETIMAGE, 900)
        if _valid(buf):
            print("    capture %d -> 0x%02X" % (i + 1, buf[9]))
        else:
            print("    capture %d -> no reply" % (i + 1))
        time.sleep(1)
    u.deinit()

    a = ask("\n  Did the ring light AT ANY POINT? (y/n) ").lower()
    RESULT["led"] = a.startswith("y")
    return RESULT["led"]


# ============================================================== TEST F  info
def test_f_info(tx, rx, baud):
    head("F", "read the module's own parameters")
    u = UART(1, baudrate=baud, tx=tx, rx=rx, bits=8, parity=None,
             stop=1, timeout=300)
    time.sleep_ms(400)
    buf = _exchange(u, PKT_SYSPARAM, 900)
    if _valid(buf) and len(buf) >= 28:
        d = buf[10:]
        cap  = (d[4] << 8) | d[5]
        sec  = (d[6] << 8) | d[7]
        psz  = (d[12] << 8) | d[13]
        bd   = (d[14] << 8) | d[15]
        print("  capacity       %d templates" % cap)
        print("  security level %d" % sec)
        print("  packet size    %d bytes" % (32 << psz))
        print("  baud           %d" % (bd * 9600))
        print("")
        print("  Compare against 08-08-2026, when this module was working:")
        print("    capacity 1000 | security 3 | packet 128 | baud 57600")
    else:
        print("  no usable reply: %s" % hexs(buf[:16]))
    cnt = _exchange(u, PKT_COUNT, 900)
    if _valid(cnt) and len(cnt) >= 12:
        print("  templates stored %d" % ((cnt[10] << 8) | cnt[11]))
    u.deinit()


# =============================================================== VERDICT
def verdict():
    print("")
    rule("=")
    print("  VERDICT")
    rule("=")
    t   = RESULT.get("touch")
    txd = RESULT.get("txd_driven")
    hits = RESULT.get("hits") or []

    if hits:
        print("  ALIVE. It answered. Whatever was wrong was wiring or baud,")
        print("  not the silicon. Fix WIRING.md to match the working line")
        print("  above, upload r307.py, then run fp_bringup.py.")
    elif txd:
        print("  NOT DEAD, but not talking. Its transmitter is powered and")
        print("  idle-high, which a dead die cannot do. That points at the")
        print("  RXD path -- our GPIO%d to the module's green wire. Swap"
              % TX_PIN)
        print("  that one wire for a new one and run TEST D again. This is")
        print("  the single most likely remaining fault.")
    elif t:
        print("  PARTIALLY ALIVE. The touch circuit works, so VT and the")
        print("  blue wire are fine and the board is powered, but the main")
        print("  MCU is not driving TXD. Check the RED wire is on 5 V at the")
        print("  MODULE END under load -- your 15-08 notes say the handshake")
        print("  died right after a 3V3/5V rework, and this is exactly that")
        print("  failure signature. If it measures 5 V, the MCU is gone.")
    else:
        print("  NO SIGN OF LIFE on any channel -- no touch, no TXD, no")
        print("  reply. Before calling it dead, prove with the meter:")
        print("    - 4.2 V or more across the module's own VCC/GND under load")
        print("    - module GND continuous to ESP32 GND, under 1 ohm")
        print("    - 45-60 mA drawn on the 5 V line")
        print("  All three good and still nothing = the module is dead.")
        print("  Buy another. Do not spend another week on this one.")
    rule("=")


# ================================================================== MAIN
def run_all():
    print("")
    rule("=")
    print("  R307S FINAL TRY  --  %s" % VERSION)
    rule("=")
    print("  Power the module from the 5 V rail. Grounds common. Then sit")
    print("  through all of it -- about three minutes.")
    ask("\n  [enter] to start ")

    test_a_touch()
    test_b_txd()
    test_c_listen()
    hits = test_d_handshake()

    if hits:
        tx, rx, baud = hits[0]
        test_f_info(tx, rx, baud)
        test_e_led(tx, rx, baud)
    else:
        print("\n  Skipping E and F -- nothing answered to talk to.")

    verdict()


MENU = """
  1  touch circuit          (no UART)
  2  TXD driven?            (no UART)   <- the new one, run it
  3  passive listen
  4  handshake sweep
  5  read parameters
  6  LED / ring sweep
  ---
  0  run everything, in order
  q  quit
"""


def menu():
    while True:
        print(MENU)
        c = ask("  select: ")
        if c == "q":
            return
        elif c == "0":
            run_all()
        elif c == "1":
            test_a_touch()
        elif c == "2":
            test_b_txd()
        elif c == "3":
            test_c_listen()
        elif c == "4":
            test_d_handshake()
        elif c in ("5", "6"):
            hits = RESULT.get("hits") or [(TX_PIN, RX_PIN, BAUD)]
            tx, rx, baud = hits[0]
            if c == "5":
                test_f_info(tx, rx, baud)
            else:
                test_e_led(tx, rx, baud)
        else:
            print("  ?")


menu()
