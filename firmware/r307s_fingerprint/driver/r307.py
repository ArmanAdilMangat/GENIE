"""R307S optical fingerprint driver — MicroPython / ESP32-S3.

MUST be saved onto the BOARD, not just the PC.
Thonny: File > Save as... > MicroPython device > filename r307.py

Verified against the actual module on 2026-08-08:
    capacity        1000 templates
    security level  3
    packet size     128 bytes
    baud            57600
    address         0xFFFFFFFF

Verified wiring (do not change without a demonstrated reason):
    RED    pin1  -> external +5V   (~5.17 V measured)
    BLACK  pin2  -> external GND, tied to ESP32 GND
    YELLOW pin3  TXD -> GPIO18 (ESP RX)
    GREEN  pin4  RXD <- GPIO17 (ESP TX)
    BLUE   pin5  TOUCH -> GPIO16
    WHITE  pin6  3.3V  -> ESP32 3V3
"""


VERSION = "r307 1.1  24-08-2026"

# CHANGES IN 1.1 -- both found by auditing this file on 24-08-2026:
#
#   1. led() sent colour=0x01, which is RED. It has never once asked this
#      module for blue. If you have been watching for a blue ring, the
#      command going out the wire was not the one you thought it was.
#      led() now takes a colour, and ring_sweep() walks every combination.
#
#   2. __init__ talked to the module immediately. The R307 needs a few
#      hundred ms after any power or line disturbance before it will accept
#      a command; without the wait the FIRST command after construction can
#      be silently dropped, which reads exactly like a dead module.
#
# Nothing else changed. The packet layer below was verified against real
# silicon on 08-08-2026 and is not in question.

from machine import UART, Pin
import struct
import time

HDR = b"\xEF\x01"
ADDR = b"\xFF\xFF\xFF\xFF"
PID_CMD, PID_DATA, PID_ACK, PID_END = 0x01, 0x02, 0x07, 0x08

OK = 0x00
NO_FINGER = 0x02
NOT_FOUND = 0x09
ENROLL_MISMATCH = 0x0A

WIDTH, HEIGHT = 256, 288
PIXELS = WIDTH * HEIGHT      # 73728
PACKED = PIXELS // 2         # 36864 — UpImage sends 4 bits per pixel

ERRORS = {
    0x00: "ok",
    0x01: "packet receive error",
    0x02: "no finger on sensor",
    0x03: "failed to enroll image",
    0x06: "image too messy",
    0x07: "too few feature points",
    0x08: "fingerprints do not match",
    0x09: "no matching template found",
    0x0A: "the two scans did not combine",
    0x0B: "page id out of range",
    0x0D: "template upload error",
    0x0F: "image upload error",
    0x10: "template delete error",
    0x11: "database clear error",
    0x13: "wrong password",
    0x15: "no valid image in buffer",
    0x18: "flash read/write error",
    0x1A: "invalid register number",
}


def err(code):
    if code is None:
        return "no reply from sensor"
    return ERRORS.get(code, "unknown code 0x%02X" % code)


class R307:
    def __init__(self, uart_id=1, tx=17, rx=18, baud=57600, touch=16,
                 settle_ms=400):
        self.u = UART(uart_id, baudrate=baud, bits=8, parity=None, stop=1,
                      tx=Pin(tx), rx=Pin(rx), timeout=2000, timeout_char=100)
        self.touch = Pin(touch, Pin.IN) if touch is not None else None
        # See note 2 at the top of this file. Do not remove.
        time.sleep_ms(settle_ms)
        self.flush()

    # ------------------------------------------------------ packet layer

    def flush(self):
        while self.u.any():
            self.u.read()

    def _read_exact(self, n, timeout_ms):
        buf = bytearray()
        t0 = time.ticks_ms()
        while len(buf) < n:
            chunk = self.u.read(n - len(buf))
            if chunk:
                buf.extend(chunk)
                t0 = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                return None
            else:
                time.sleep_ms(1)
        return bytes(buf)

    def _sync(self, timeout_ms):
        t0 = time.ticks_ms()
        prev = None
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            b = self.u.read(1)
            if not b:
                time.sleep_ms(1)
                continue
            if prev == 0xEF and b[0] == 0x01:
                return True
            prev = b[0]
        return False

    def read_packet(self, timeout_ms=3000):
        """Any packet type. Returns (pid, payload, checksum_ok) or None."""
        if not self._sync(timeout_ms):
            return None
        head = self._read_exact(7, timeout_ms)
        if head is None:
            return None
        pid = head[4]
        length = (head[5] << 8) | head[6]
        body = self._read_exact(length, timeout_ms)
        if body is None:
            return None
        payload, chk = body[:-2], (body[-2] << 8) | body[-1]
        calc = (pid + head[5] + head[6] + sum(payload)) & 0xFFFF
        return pid, payload, calc == chk

    def cmd(self, data, timeout_ms=3000):
        """Send a command, return (confirmation_code, payload_after_code)."""
        self.flush()
        length = len(data) + 2
        chk = (PID_CMD + (length >> 8) + (length & 0xFF) + sum(data)) & 0xFFFF
        self.u.write(HDR + ADDR + bytes([PID_CMD]) +
                     struct.pack(">H", length) + data + struct.pack(">H", chk))
        p = self.read_packet(timeout_ms)
        if p is None or p[0] != PID_ACK or not p[1]:
            return None, b""
        return p[1][0], p[1][1:]

    # ------------------------------------------------------- primitives

    def verify_pwd(self, pwd=0):
        code, _ = self.cmd(b"\x13" + struct.pack(">I", pwd))
        return code == OK

    def read_sysparam(self):
        code, d = self.cmd(b"\x0F")
        if code != OK or len(d) < 16:
            return None
        status, sys_id, cap, sec, addr, psize, baud = struct.unpack(">HHHHIHH", d[:16])
        return {"status": status, "capacity": cap, "security_level": sec,
                "packet_size": 32 << psize, "baud": baud * 9600}

    def template_count(self):
        code, d = self.cmd(b"\x1D")
        return struct.unpack(">H", d[:2])[0] if code == OK and len(d) >= 2 else -1

    # AuraLedConfig, 0x35.  ctrl 1=breathe 2=flash 3=on 4=off
    #                       colour 1=red 2=blue 3=purple
    # Not every R307 firmware implements this. A 0x01 reply or no reply here
    # means "command not supported", NOT "module broken". The illumination
    # during get_image() is the real proof the optics are powered.
    RED, BLUE, PURPLE = 0x01, 0x02, 0x03

    def led(self, on=True, colour=BLUE, speed=0x40, times=0x00):
        code, _ = self.cmd(bytes([0x35, 0x03 if on else 0x04,
                                  speed, colour, times]))
        return code == OK

    def ring_sweep(self, hold_s=2):
        """Walk every ctrl x colour combination, printing what came back.

        Use this once, in a dim room, before concluding the ring is dead.
        Your own older notes describe this unit's ring as RED, so do not
        read anything into blue specifically failing.
        """
        names = {1: "breathe", 2: "flash", 3: "on", 4: "off"}
        cols = {1: "red", 2: "blue", 3: "purple"}
        any_ok = False
        for colour in (1, 2, 3):
            for ctrl in (3, 2, 1):
                code, _ = self.cmd(bytes([0x35, ctrl, 0x40, colour, 0x00]))
                print("  %-8s %-7s -> %s" % (names[ctrl], cols[colour],
                                             err(code)))
                any_ok = any_ok or code == OK
                time.sleep(hold_s)
            self.cmd(bytes([0x35, 4, 0x40, colour, 0x00]))
        if not any_ok:
            print("  0x35 unsupported on this firmware -- expected on many")
            print("  R307 units. Judge the optics by get_image() instead.")
        return any_ok

    def get_image(self):
        code, _ = self.cmd(b"\x01")
        return code

    def img2tz(self, buf=1):
        code, _ = self.cmd(bytes([0x02, buf]))
        return code

    def reg_model(self):
        code, _ = self.cmd(b"\x05")
        return code

    def store(self, page, buf=1):
        code, _ = self.cmd(bytes([0x06, buf]) + struct.pack(">H", page))
        return code

    def delete(self, page, count=1):
        code, _ = self.cmd(b"\x0C" + struct.pack(">HH", page, count))
        return code

    def search(self, buf=1, start=0, num=1000):
        code, d = self.cmd(bytes([0x04, buf]) + struct.pack(">HH", start, num))
        if code == OK and len(d) >= 4:
            return struct.unpack(">HH", d[:4])
        return -1, 0

    def empty_db(self):
        code, _ = self.cmd(b"\x0D")
        return code == OK

    def used_slots(self):
        """ReadIndexTable (0x1F) -> sorted list of occupied slot numbers.

        The sensor answers with a 32-byte bitmap per page, 256 slots each.
        Capacity 1000 means pages 0-3. This is the only way to ask the sensor
        *which* slots are taken -- template_count() gives the number only.
        """
        used = []
        for page in range(4):
            code, d = self.cmd(bytes([0x1F, page]))
            if code != OK or len(d) < 32:
                return None if page == 0 else used
            for byte_i in range(32):
                b = d[byte_i]
                if not b:
                    continue
                for bit in range(8):
                    if b & (1 << bit):
                        used.append(page * 256 + byte_i * 8 + bit)
        return used

    # --------------------------------------------------------- up_image

    def up_image(self, sink, progress=None, timeout_ms=4000):
        """Pull the raw image buffer out of the sensor.

        `sink(packed_bytes)` is called once per packet with the raw 4-bit
        packed data. Returns the number of packed bytes received; a full
        image is PACKED (36864) bytes = 73728 pixels.

        Each byte holds two pixels: high nibble first, then low nibble.
        Use unpack() below to expand to 8-bit grayscale.
        """
        code, _ = self.cmd(b"\x0A")
        if code != OK:
            return 0
        got = 0
        while got < PACKED:
            p = self.read_packet(timeout_ms)
            if p is None:
                break
            pid, payload, _ = p
            if pid not in (PID_DATA, PID_END):
                continue
            sink(payload)
            got += len(payload)
            if progress:
                progress(got, PACKED)
            if pid == PID_END:       # end packet still carries real data
                break
        return got

    @staticmethod
    def unpack(packed, out=None):
        """4-bit packed -> 8-bit grayscale. Nibble replicated for full range."""
        n = len(packed)
        if out is None:
            out = bytearray(2 * n)
        for i in range(n):
            b = packed[i]
            hi, lo = b >> 4, b & 0x0F
            out[2 * i] = (hi << 4) | hi
            out[2 * i + 1] = (lo << 4) | lo
        return out

    # ---------------------------------------------------------- helpers

    def wait_finger(self, timeout_s=10, want=True):
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_s * 1000:
            code = self.get_image()
            if code is None:
                return False
            if (code == OK) == want:
                return True
            time.sleep_ms(100)
        return False

    def _capture(self, buf, tries=5, settle_ms=500, timeout_s=15):
        """Wait for a finger, let it SETTLE, then convert to a template.

        The settle delay is the important part. wait_finger() returns at first
        contact, when only the tip is touching. Converting that gives a partial
        print, and two different partials will not combine -- which shows up
        later as the misleading 'two scans did not combine' error.

        Poor-quality scans (0x06 messy, 0x07 too few points) are retried rather
        than failed, since they are almost always fixed by pressing again.
        """
        for attempt in range(tries):
            if not self.wait_finger(timeout_s):
                return 0xFE                      # timeout
            time.sleep_ms(settle_ms)             # let the whole pad make contact
            if self.get_image() != OK:
                continue                         # lifted during the settle
            code = self.img2tz(buf)
            if code == OK:
                return OK
            if code in (0x06, 0x07):
                print("    poor scan (%s)" % err(code))
                print("    press flatter, use the CENTRE of the pad, hold still")
                self.wait_finger(10, want=False)
                time.sleep_ms(400)
                continue
            return code
        return 0x07                              # ran out of tries

    def enroll(self, page, tries=5):
        print("  place finger and HOLD still...")
        code = self._capture(1, tries)
        if code == 0xFE:
            return False, "timed out waiting for finger"
        if code != OK:
            return False, "scan 1: " + err(code)

        print("  lift finger")
        if not self.wait_finger(10, want=False):
            return False, "finger never lifted"
        time.sleep(1)

        print("  place the SAME finger again -- same spot, same angle...")
        code = self._capture(2, tries)
        if code == 0xFE:
            return False, "timed out on second scan"
        if code != OK:
            return False, "scan 2: " + err(code)

        code = self.reg_model()
        if code == ENROLL_MISMATCH:
            return False, ("the two scans did not combine -- press the SAME "
                           "part of the finger both times, flat and firm")
        if code != OK:
            return False, err(code)

        code = self.store(page)
        if code != OK:
            return False, "store: " + err(code)
        return True, "enrolled to slot %d" % page

    def identify(self, timeout_s=8):
        if not self.wait_finger(timeout_s):
            return -1, 0
        if self.img2tz(1) != OK:
            return -1, 0
        return self.search()
