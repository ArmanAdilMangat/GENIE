# =======================================================================
#  R307S  --  TEST 1 : LIFE CHECK        MicroPython / ESP32-S3 / Thonny
# -----------------------------------------------------------------------
#  Answers ONE question: is the sensor alive and talking, or dead?
#  No libraries. Raw R30x protocol.
#
#  Run it in Thonny (F5). Fully automatic, ~40 s.
#
#  WIRING UNDER TEST:
#    Red    -> +5V external        Black -> GND (common with ESP GND)
#    Yellow -> GPIO18   (expected sensor TX -> ESP RX)
#    Green  -> GPIO17   (expected sensor RX <- ESP TX)
#    Blue   -> GPIO4    (touch / wake output)
#    White  -> 3V3      (touch-circuit power)
# =======================================================================

from machine import UART, Pin
import time

PIN_YELLOW = 18
PIN_GREEN  = 17
PIN_TOUCH  = 4

# every legal R30x rate = N * 9600, N = 1..12   (57600 = factory default)
BAUDS = [57600, 9600, 19200, 28800, 38400, 48000,
         67200, 76800, 86400, 96000, 105600, 115200]

CODES = {
    0x00: "OK",
    0x01: "packet receive error",
    0x02: "no finger on sensor",
    0x03: "failed to capture image",
    0x06: "image too disorderly",
    0x07: "too few feature points",
    0x08: "no match",
    0x09: "not found in library",
    0x0A: "templates did not combine",
    0x0B: "PageID beyond capacity",
    0x0C: "invalid template",
    0x0D: "template upload error",
    0x0F: "image upload error",
    0x10: "delete failed",
    0x11: "clear library failed",
    0x13: "WRONG PASSWORD (sensor is alive!)",
    0x15: "no valid image in buffer",
    0x18: "FLASH READ/WRITE ERROR",
    0x1A: "invalid register",
    0x20: "address code incorrect",
    0x21: "password must be verified first",
}

uart = None


def hexs(b, limit=24):
    return ' '.join('%02X' % x for x in b[:limit]) + (' ...' if len(b) > limit else '')


def build(data):
    """Wrap a command payload in the EF01 packet frame."""
    ln = len(data) + 2
    pkt = bytearray(b'\xEF\x01\xFF\xFF\xFF\xFF\x01')
    pkt.append(ln >> 8)
    pkt.append(ln & 0xFF)
    pkt.extend(data)
    s = (0x01 + (ln >> 8) + (ln & 0xFF) + sum(data)) & 0xFFFF
    pkt.append(s >> 8)
    pkt.append(s & 0xFF)
    return bytes(pkt)


def parse(b):
    """-> (code, data). code >=0 real reply, -1 no packet found, -2 bad checksum."""
    n = len(b)
    for i in range(max(0, n - 10)):
        if b[i] != 0xEF or b[i + 1] != 0x01:
            continue
        ln = (b[i + 7] << 8) | b[i + 8]
        if ln < 2 or i + 9 + ln > n:
            continue
        dlen = ln - 2
        s = (b[i + 6] + b[i + 7] + b[i + 8] + sum(b[i + 9:i + 9 + dlen])) & 0xFFFF
        chk = (b[i + 9 + dlen] << 8) | b[i + 10 + dlen]
        if chk != s:
            return -2, b''
        return b[i + 9], bytes(b[i + 9:i + 9 + dlen])
    return -1, b''


def slurp(hard_ms=700, quiet_ms=40):
    """Collect raw bytes; stop early on a valid packet."""
    buf = bytearray()
    t0 = time.ticks_ms()
    last = t0
    while time.ticks_diff(time.ticks_ms(), t0) < hard_ms:
        n = uart.any()
        if n:
            buf.extend(uart.read(n))
            last = time.ticks_ms()
            c, _ = parse(bytes(buf))
            if c >= 0 or c == -2:
                break
        elif buf and time.ticks_diff(time.ticks_ms(), last) > quiet_ms:
            break
        time.sleep_ms(2)
    return bytes(buf)


def send(data):
    while uart.any():
        uart.read(uart.any())
    uart.write(build(data))


# ------------------------------------------------------------ [1] touch
def touch_test():
    print("\n[1] TOUCH LINE  (Blue -> GPIO%d)  --  floating test" % PIN_TOUCH)
    lo = Pin(PIN_TOUCH, Pin.IN, Pin.PULL_DOWN).value()
    time.sleep_ms(30)
    hi = Pin(PIN_TOUCH, Pin.IN, Pin.PULL_UP).value()
    time.sleep_ms(30)
    p = Pin(PIN_TOUCH, Pin.IN)

    print("    pulldown reads %d , pullup reads %d  ->  " % (lo, hi), end="")
    if lo == 0 and hi == 1:
        print("FLOATING")
        print("    Nothing is driving GPIO%d." % PIN_TOUCH)
        print("    Causes: White(3V3) not connected, Blue not connected,")
        print("            or this unit has no touch-detect circuit.")
        print("    NOT fatal -- UART can still work perfectly.")
    else:
        print("DRIVEN %s -- touch circuit is powered." % ("HIGH" if lo else "LOW"))

    print("    Put your finger on the sensor now (6 s window)...")
    base = p.value()
    changed = False
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 6000:
        v = p.value()
        if v != base:
            print("    GPIO%d changed %d -> %d" % (PIN_TOUCH, base, v))
            base = v
            changed = True
        time.sleep_ms(10)
    print("    RESULT: touch output WORKS." if changed else
          "    RESULT: no change (touch unused/unpowered -- fine for UART use).")


# ------------------------------------------------------------ [2] sweep
def probe(baud, swap):
    global uart
    rx = PIN_GREEN if swap else PIN_YELLOW
    tx = PIN_YELLOW if swap else PIN_GREEN
    try:
        if uart:
            uart.deinit()
    except Exception:
        pass
    uart = UART(1, baudrate=baud, bits=8, parity=None, stop=1,
                tx=tx, rx=rx, timeout=100)
    time.sleep_ms(60)

    send(b'\x13\x00\x00\x00\x00')          # VfyPwd, password 0x00000000
    raw = slurp(700)

    print("  %-7d %-8s " % (baud, "SWAPPED" if swap else "normal"), end="")
    if not raw:
        print("silence")
        return False

    c, d = parse(raw)
    if c == -1:
        print("%2d bytes: %s   <- garbage (wrong baud / noise)" % (len(raw), hexs(raw)))
        return False
    if c == -2:
        print("%2d bytes: %s   <- BAD CHECKSUM (marginal wiring)" % (len(raw), hexs(raw)))
        return False
    print("VALID PACKET, code 0x%02X (%s)" % (c, CODES.get(c, "unknown")))
    return True


# ------------------------------------------------------------ [4] params
def sysparams():
    print("\n[4] SYSTEM PARAMETERS")
    send(b'\x13\x00\x00\x00\x00')
    slurp(600)

    send(b'\x0F')
    c, d = parse(slurp(900))
    if c != 0x00 or len(d) < 17:
        print("    ReadSysPara failed: code %s (%s)" % (c, CODES.get(c, "?")))
        if c == 0x21:
            print("    -> the module has a NON-ZERO password set.")
        return
    st  = (d[1] << 8) | d[2]
    sid = (d[3] << 8) | d[4]
    cap = (d[5] << 8) | d[6]
    sec = (d[7] << 8) | d[8]
    addr = (d[9] << 24) | (d[10] << 16) | (d[11] << 8) | d[12]
    psz = (d[13] << 8) | d[14]
    br  = (d[15] << 8) | d[16]
    print("    status register : 0x%04X  busy=%d pwdOK=%d imgBuf=%d"
          % (st, st & 1, (st >> 1) & 1, (st >> 2) & 1))
    print("    system id       : 0x%04X %s"
          % (sid, "(genuine R30x)" if sid == 0x0009 else "(UNEXPECTED)"))
    print("    capacity        : %d templates" % cap)
    print("    security level  : %d  (1 loose .. 5 strict, 3 default)" % sec)
    print("    device address  : 0x%08X" % addr)
    print("    packet size     : %d bytes" % ([32, 64, 128, 256][psz] if psz < 4 else 0))
    print("    baud setting    : %d" % (br * 9600))

    send(b'\x1D')
    c, d = parse(slurp(900))
    if c == 0x00 and len(d) >= 3:
        print("    templates stored: %d" % ((d[1] << 8) | d[2]))


# ------------------------------------------------------------------ main
def run():
    print("\n===============================================")
    print("   R307S  LIFE CHECK   (GENIE / ESP32-S3)")
    print("===============================================")
    print("Yellow->GPIO18  Green->GPIO17  Blue->GPIO4")
    print("Red->+5V ext    White->3V3     GNDs common")

    touch_test()

    found_baud = None
    found_swap = False

    print("\n[2] UART SWEEP -- normal orientation (RX=18, TX=17)")
    print("    baud    pins     response")
    for b in BAUDS:
        if probe(b, False):
            found_baud, found_swap = b, False
            break

    if found_baud is None:
        print("\n[3] UART SWEEP -- SWAPPED orientation (RX=17, TX=18)")
        for b in BAUDS:
            if probe(b, True):
                found_baud, found_swap = b, True
                break
    else:
        print("\n[3] swapped sweep skipped -- already talking.")

    print("\n===============================================")
    if found_baud:
        print("   VERDICT:  SENSOR IS ALIVE")
        print("   baud   = %d" % found_baud)
        if found_swap:
            print("   wiring = SWAPPED -> your Yellow is RX, Green is TX.")
            print("   -> either swap the two wires, or set SWAPPED = True")
            print("      in r307s_fulltest.py")
        else:
            print("   wiring = as documented (Yellow=TX, Green=RX). Correct.")
        print("===============================================")
        sysparams()
        print("\nNEXT: set BAUD/SWAPPED at the top of r307s_fulltest.py and run it.")
    else:
        print("   VERDICT:  NO RESPONSE ON ANY BAUD, EITHER WAY")
        print("===============================================")
        print("Work through these in order:")
        print(" 1. Multimeter Red-to-Black AT THE SENSOR connector, powered,")
        print("    under load. Must read 4.5-6.0 V.")
        print(" 2. Is ESP32 GND actually tied to the external supply GND?")
        print("    Without that common ground the UART cannot work.")
        print(" 3. Does the ring glow at power-up? No glow + correct voltage")
        print("    = dead module.")
        print(" 4. Continuity-test the 6-pin JST. Broken solder on the flying")
        print("    leads is the #1 cause.")
        print(" 5. Run loopback() from r307s_fulltest.py (jumper 17<->18 with")
        print("    the sensor unplugged) to clear the ESP32 pins themselves.")
        print(" 6. R307 pulls ~120 mA peaks. A weak 5V rail browns it out and")
        print("    it never answers.")

    return found_baud, found_swap


run()
