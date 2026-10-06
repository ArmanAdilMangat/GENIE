# =======================================================================
#  R307S  --  TEST 2 : FULL DIAGNOSTIC SUITE   MicroPython / ESP32-S3
# -----------------------------------------------------------------------
#  Run r307s_lifecheck.py FIRST. It gives you BAUD and whether the
#  Yellow/Green pair is swapped. Put both answers in CONFIG below.
#
#  In Thonny press F5. You get a menu.
#  You can also call any function straight from the Shell afterwards:
#      >>> enroll(3)
#      >>> search()
#      >>> soak(500)
# =======================================================================

from machine import UART, Pin
import time

# ----------------------------------------------------------- CONFIG ----
BAUD       = 57600      # <-- from lifecheck ("baud = ...")
SWAPPED    = False      # <-- True if lifecheck said SWAPPED
PIN_YELLOW = 18
PIN_GREEN  = 17
PIN_TOUCH  = 4
# ------------------------------------------------------------------------

RX = PIN_GREEN  if SWAPPED else PIN_YELLOW
TX = PIN_YELLOW if SWAPPED else PIN_GREEN

uart = UART(1, baudrate=BAUD, bits=8, parity=None, stop=1,
            tx=TX, rx=RX, timeout=200)
touch = Pin(PIN_TOUCH, Pin.IN)

CODES = {
    0x00: "OK",
    0x01: "packet receive error",
    0x02: "no finger on sensor",
    0x03: "failed to capture image",
    0x06: "image too disorderly (smudged/wet)",
    0x07: "too few feature points (light touch / dry finger)",
    0x08: "no match",
    0x09: "not found in library",
    0x0A: "the two scans did not combine (different fingers?)",
    0x0B: "PageID beyond library capacity",
    0x0C: "invalid / corrupt template",
    0x0D: "template upload error",
    0x0E: "cannot receive following packets",
    0x0F: "image upload error",
    0x10: "delete failed",
    0x11: "clear library failed",
    0x13: "wrong password",
    0x15: "no valid image in buffer",
    0x18: "FLASH READ/WRITE ERROR",
    0x1A: "invalid register",
    0x20: "address code incorrect",
    0x21: "password must be verified first",
    -1:   "NO RESPONSE (timeout)",
    -2:   "CHECKSUM ERROR (marginal wiring / wrong baud)",
}


def name(c):
    return CODES.get(c, "unknown code")


def say(what, c):
    print("    %-22s -> 0x%02X  %s" % (what, c & 0xFF, name(c)))


# ------------------------------------------------------------- protocol
def build(data):
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


def cmd(data, tmo=2000):
    """Send a command, return (confirmation_code, data_bytes)."""
    while uart.any():
        uart.read(uart.any())
    uart.write(build(data))
    buf = bytearray()
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < tmo:
        n = uart.any()
        if n:
            buf.extend(uart.read(n))
            c, d = parse(bytes(buf))
            if c >= 0:
                return c, d
            if c == -2:
                return -2, b''
        time.sleep_ms(2)
    return -1, bytes(buf)


# ------------------------------------------------------------- commands
def verify_pwd():
    c, _ = cmd(b'\x13\x00\x00\x00\x00')
    return c == 0x00


def sysparams():
    print("\n-- SYSTEM PARAMETERS --")
    c, d = cmd(b'\x0F')
    if c != 0x00 or len(d) < 17:
        say("ReadSysPara", c)
        return False
    st  = (d[1] << 8) | d[2]
    sid = (d[3] << 8) | d[4]
    cap = (d[5] << 8) | d[6]
    sec = (d[7] << 8) | d[8]
    addr = (d[9] << 24) | (d[10] << 16) | (d[11] << 8) | d[12]
    psz = (d[13] << 8) | d[14]
    br  = (d[15] << 8) | d[16]
    print("    status 0x%04X  busy=%d pwdOK=%d imgBuf=%d"
          % (st, st & 1, (st >> 1) & 1, (st >> 2) & 1))
    print("    system id      : 0x%04X %s"
          % (sid, "(genuine R30x)" if sid == 0x0009 else "(UNEXPECTED)"))
    print("    capacity       : %d templates" % cap)
    print("    security level : %d  (1 loose .. 5 strict)" % sec)
    print("    device address : 0x%08X" % addr)
    print("    packet size    : %d bytes" % ([32, 64, 128, 256][psz] if psz < 4 else 0))
    print("    baud setting   : %d" % (br * 9600))
    return sid == 0x0009


def count(quiet=False):
    c, d = cmd(b'\x1D')
    if c != 0x00 or len(d) < 3:
        if not quiet:
            say("TemplateNum", c)
        return -1
    n = (d[1] << 8) | d[2]
    if not quiet:
        print("    templates stored: %d" % n)
    return n


def index():
    print("\n-- ENROLLED IDs (index table page 0 = IDs 0-255) --")
    c, d = cmd(b'\x1F\x00')
    if c != 0x00 or len(d) < 33:
        say("ReadIndexTable", c)
        print("    (some R307 firmwares lack 0x1F -- not a fault)")
        return
    ids = [i * 8 + b for i in range(32) for b in range(8) if d[1 + i] & (1 << b)]
    print("    IDs: %s" % (' '.join(str(i) for i in ids) if ids else "(none)"))
    print("    total = %d" % len(ids))


def wait_finger(msg, tmo=12000):
    print("    %s" % msg)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < tmo:
        c, _ = cmd(b'\x01', 1200)
        if c == 0x00:
            print("    image captured.")
            return True
        if c == 0x02:
            time.sleep_ms(60)
            continue
        say("GetImage", c)
        if c < 0:
            return False
        time.sleep_ms(120)
    print("    timeout waiting for finger.")
    return False


def wait_remove():
    print("    remove finger...")
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 8000:
        c, _ = cmd(b'\x01', 1000)
        if c == 0x02:
            time.sleep_ms(300)
            return
        time.sleep_ms(100)


def enroll(slot=1):
    print("\n-- ENROLL to slot #%d --" % slot)
    if not wait_finger("place finger (1st of 2)..."):
        return
    c, _ = cmd(b'\x02\x01', 3000); say("Img2Tz buf1", c)
    if c != 0x00:
        return
    wait_remove()
    if not wait_finger("place the SAME finger again (2nd of 2)..."):
        return
    c, _ = cmd(b'\x02\x02', 3000); say("Img2Tz buf2", c)
    if c != 0x00:
        return
    c, _ = cmd(b'\x05', 3000);     say("RegModel", c)
    if c != 0x00:
        return
    c, _ = cmd(bytes([0x06, 0x01, slot >> 8, slot & 0xFF]), 3000)
    say("Store (flash write)", c)
    if c == 0x00:
        print("    ENROLL OK -- this also proves the flash write path.")
        count()


def search():
    print("\n-- 1:N SEARCH --")
    if not wait_finger("place any enrolled finger..."):
        return
    c, _ = cmd(b'\x02\x01', 3000); say("Img2Tz buf1", c)
    if c != 0x00:
        return
    c, d = cmd(b'\x04\x01\x00\x00\x03\xE8', 4000)   # buf1, page 0, 1000 slots
    if c == 0x00 and len(d) >= 5:
        print("    MATCH  id=%d  confidence=%d"
              % ((d[1] << 8) | d[2], (d[3] << 8) | d[4]))
    else:
        say("Search", c)


def verify(slot=1):
    print("\n-- 1:1 VERIFY against slot #%d --" % slot)
    c, _ = cmd(bytes([0x07, 0x02, slot >> 8, slot & 0xFF]), 3000)
    say("LoadChar -> buf2", c)
    if c != 0x00:
        return
    if not wait_finger("place finger..."):
        return
    c, _ = cmd(b'\x02\x01', 3000); say("Img2Tz buf1", c)
    if c != 0x00:
        return
    c, d = cmd(b'\x03', 3000)
    if c == 0x00 and len(d) >= 3:
        print("    MATCH confidence=%d" % ((d[1] << 8) | d[2]))
    else:
        say("Match", c)


def delete(slot=1):
    print("\n-- DELETE slot #%d --" % slot)
    c, _ = cmd(bytes([0x0C, slot >> 8, slot & 0xFF, 0x00, 0x01]), 3000)
    say("DeletChar", c)
    count()


def empty():
    print("\n!! This ERASES ALL fingerprints.")
    if input("   Type ERASE to confirm: ").strip() != "ERASE":
        print("    cancelled.")
        return
    c, _ = cmd(b'\x0D', 4000)
    say("Empty", c)
    count()


def image_quality(n=10):
    print("\n-- IMAGE QUALITY (%d captures) --" % n)
    print("    keep one finger on the sensor for the whole test.")
    ok = feat = 0
    for i in range(n):
        c, _ = cmd(b'\x01', 1500)
        if c == 0x00:
            ok += 1
            f, _ = cmd(b'\x02\x01', 3000)
            if f == 0x00:
                feat += 1
            print("    %2d: image OK, feature 0x%02X %s" % (i + 1, f & 0xFF, name(f)))
        else:
            print("    %2d: 0x%02X %s" % (i + 1, c & 0xFF, name(c)))
        time.sleep_ms(200)
    print("    images %d/%d, usable features %d/%d" % (ok, n, feat, n))
    if ok >= n * 0.8 and feat >= n * 0.7:
        print("    OPTICS + DSP: GOOD")
    elif ok >= n * 0.8:
        print("    optics fine, features poor -> dry/dirty finger or dirty glass")
    else:
        print("    poor capture -> clean the glass, check the 5V rail")


def soak(n=200):
    print("\n-- LINK SOAK TEST (%d packets) --" % n)
    good = tmo = chk = 0
    t0 = time.ticks_ms()
    for _ in range(n):
        c, _ = cmd(b'\x0F', 800)
        if c == 0x00:
            good += 1
        elif c == -1:
            tmo += 1
        elif c == -2:
            chk += 1
    ms = time.ticks_diff(time.ticks_ms(), t0)
    print("    good=%d  timeouts=%d  checksum-errors=%d  (%d ms)" % (good, tmo, chk, ms))
    if good == n:
        print("    LINK: ROCK SOLID.")
    elif good > n * 0.95:
        print("    LINK: usable but not clean -- shorten wires, 100nF at the sensor.")
    else:
        print("    LINK: UNRELIABLE -- power sag or bad joint. Fix before trusting it.")
    return good, tmo, chk


def flash_test():
    print("\n-- FLASH READ/WRITE TEST (notepad page 15) --")
    print("    harmless to fingerprints; overwrites notepad page 15 only.")
    pattern = bytes((0xA5 ^ i) & 0xFF for i in range(32))
    c, _ = cmd(b'\x18\x0F' + pattern, 3000)
    say("WriteNotepad", c)
    if c != 0x00:
        print("    -> flash WRITE path FAILED. Enrollment will not persist.")
        return False
    c, d = cmd(b'\x19\x0F', 3000)
    say("ReadNotepad", c)
    if c != 0x00 or len(d) < 33:
        return False
    if bytes(d[1:33]) == pattern:
        print("    FLASH VERIFY OK -- non-volatile memory is healthy.")
        return True
    print("    FLASH VERIFY MISMATCH -- suspect module.")
    return False


def led():
    print("\n-- LED / BACKLIGHT --")
    c, _ = cmd(b'\x50', 1500); say("LED on  (0x50)", c)
    time.sleep_ms(1200)
    c, _ = cmd(b'\x51', 1500); say("LED off (0x51)", c)
    time.sleep_ms(600)
    c, _ = cmd(b'\x35\x02\x30\x01\x05', 1500); say("AuraLed (0x35)", c)
    print("    0x01/0x1A here just means this firmware lacks the command.")
    print("    Did the ring actually light? That is the real answer.")


def touch_monitor(secs=10):
    print("\n-- TOUCH PIN MONITOR (GPIO%d), %d s --" % (PIN_TOUCH, secs))
    last = touch.value()
    ch = 0
    print("    idle level = %d. Touch and release a few times." % last)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < secs * 1000:
        v = touch.value()
        if v != last:
            print("    %5d ms: %d -> %d" % (time.ticks_diff(time.ticks_ms(), t0), last, v))
            last = v
            ch += 1
        time.sleep_ms(5)
    print("    transitions = %d %s" % (ch, "-> touch line WORKS" if ch else
          "-> no activity (White unpowered, or no touch circuit)"))


def loopback():
    print("\n-- ESP32 UART LOOPBACK --")
    print("    UNPLUG the sensor. Jumper GPIO%d <-> GPIO%d." % (PIN_YELLOW, PIN_GREEN))
    input("    Press ENTER when ready: ")
    u = UART(1, baudrate=BAUD, bits=8, parity=None, stop=1, tx=TX, rx=RX, timeout=200)
    time.sleep_ms(50)
    while u.any():
        u.read(u.any())
    pat = b'GENIE-R307S-LOOPBACK'
    u.write(pat)
    time.sleep_ms(150)
    got = u.read() or b''
    print("    sent: %s" % pat)
    print("    got : %s" % got)
    if got == pat:
        print("    ESP32 UART pins are GOOD -> any failure is the sensor or wiring.")
    else:
        print("    ESP32 UART pins FAILED -> wrong pins, damaged GPIO, or a conflict.")
    print("    Reconnect the sensor before running other tests.")


def monitor(secs=60):
    print("\n-- CONTINUOUS ALIVE MONITOR (%d s) -- Ctrl-C to stop --" % secs)
    polls = fails = 0
    t0 = time.ticks_ms()
    try:
        while time.ticks_diff(time.ticks_ms(), t0) < secs * 1000:
            n = count(True)
            polls += 1
            if n < 0:
                fails += 1
                print("    %4d: LINK DROP" % polls)
            else:
                print("    %4d: alive, %d templates" % (polls, n))
            time.sleep_ms(1000)
    except KeyboardInterrupt:
        pass
    print("    polls=%d  drops=%d" % (polls, fails))


def run_all():
    print("\n########## FULL NON-DESTRUCTIVE SWEEP ##########")
    print("link: baud %d, RX=GPIO%d TX=GPIO%d" % (BAUD, RX, TX))
    print("password verify -> %s" % ("OK" if verify_pwd() else "FAILED"))
    sysparams()
    count()
    index()
    soak(200)
    flash_test()
    led()
    image_quality(10)
    print("\n########## SWEEP DONE ##########")
    print("Healthy = sysparams read, soak 200/200, flash VERIFY OK,")
    print("images 8+/10. Then run enroll(1) and search() to prove the")
    print("biometric path end to end.")


# ------------------------------------------------------------------ menu
MENU = """
=========== R307S FULL TEST ===========
  a  run ALL non-destructive tests
  p  system parameters        t  template count
  i  list enrolled IDs        e  enroll   (e5 = slot 5)
  s  1:N search               v  1:1 verify (v5)
  d  delete (d5)              x  ERASE ALL templates
  q  image quality x10        k  link soak test (200)
  f  flash read/write test    g  LED / aura test
  b  touch pin monitor        L  ESP32 UART loopback
  r  continuous alive monitor h  this menu
  0  quit
=======================================
"""


def menu():
    print(MENU)
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not line:
            continue
        k = line[0]
        try:
            arg = int(line[1:]) if len(line) > 1 else 1
        except ValueError:
            arg = 1
        if   k == '0': return
        elif k == 'a': run_all()
        elif k == 'p': sysparams()
        elif k == 't': count()
        elif k == 'i': index()
        elif k == 'e': enroll(arg)
        elif k == 's': search()
        elif k == 'v': verify(arg)
        elif k == 'd': delete(arg)
        elif k == 'x': empty()
        elif k == 'q': image_quality()
        elif k == 'k': soak(200)
        elif k == 'f': flash_test()
        elif k == 'g': led()
        elif k == 'b': touch_monitor()
        elif k == 'L': loopback()
        elif k == 'r': monitor()
        else:          print(MENU)


print("R307S full diagnostic (GENIE / ESP32-S3 / MicroPython)")
print("baud %d  RX=GPIO%d  TX=GPIO%d  touch=GPIO%d" % (BAUD, RX, TX, PIN_TOUCH))
print("handshake %s" % ("OK" if verify_pwd() else
      "FAILED -- run r307s_lifecheck.py first"))
menu()
