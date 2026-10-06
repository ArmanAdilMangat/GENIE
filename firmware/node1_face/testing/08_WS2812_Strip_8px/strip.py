"""
strip.py - WS2812 8-pixel status strip for GENIE.

    DIN -> GPIO48  (P2-16)
    5V  -> ESP32 5V pin is fine for 8 LEDs at BRIGHT <= 60
    GND -> ESP32 GND (and bench supply GND if you use one)

Standalone.  Imports only machine, time, neopixel.  Upload flat to the
device root.

    >>> import strip
    >>> strip.demo()             # every effect, once
    >>> s = strip.Status()       # non-blocking, for genie_live.py
    >>> s.set("thinking")
    >>> while True: s.tick()

Two ways to use it
------------------
    Strip   blocking.  Call an effect, it runs and returns.  Bench only.
    Status  non-blocking.  set() a state, then call tick() from your main
            loop.  Nothing sleeps, so the button and the sensors stay
            responsive.  This is the one genie_live.py should use.

Things that are true about this strip and will waste your time otherwise
-----------------------------------------------------------------------
GPIO48 also drives the DevKitC-1's own RGB LED.  Its DOUT goes nowhere, so
the onboard LED and strip pixel 0 sit in PARALLEL - both show pixel 0.  The
onboard LED mirroring the first strip LED is correct behaviour, not a fault.

Colour order is GRB on almost every WS2812.  neopixel handles that.  If red
comes out green your strip is the rarer RGB type - set ORDER_RGB = True.

Data is 3.3V into a 5V part.  Eight LEDs almost always work.  If pixel 0 is
right and the rest are random, that is the level, not the code: 330 ohm in
series at DIN and a 470uF cap across the strip's 5V/GND fix it.

8 LEDs at full white is ~480 mA.  BRIGHT caps that.  Leave it capped.
"""

from machine import Pin
import time
import neopixel

DIN = 48
N = 8
BRIGHT = 60                 # 0-255 ceiling. 8 px at 255 white is ~480 mA.
ORDER_RGB = False           # True only if red/green come out swapped

BLACK = (0, 0, 0)
RED = (BRIGHT, 0, 0)
GREEN = (0, BRIGHT, 0)
BLUE = (0, 0, BRIGHT)
YELLOW = (BRIGHT, BRIGHT, 0)
CYAN = (0, BRIGHT, BRIGHT)
MAGENTA = (BRIGHT, 0, BRIGHT)
WHITE = (BRIGHT, BRIGHT, BRIGHT)

# The four states GENIE actually reports.  Agreed here once so they do not
# drift between genie_live.py, the TFT face and this file.
STATES = {
    "off":      (BLACK,  "solid"),
    "idle":     (BLUE,   "breathe"),    # listening for the wake word
    "heard":    (GREEN,  "solid"),      # wake word matched
    "thinking": (YELLOW, "chase"),      # Whisper + Mistral running
    "speaking": (CYAN,   "breathe"),    # pyttsx3 talking
    "alert":    (RED,    "flash"),      # a sensor tripped
    "error":    (MAGENTA, "flash"),
}


def _order(c):
    return (c[1], c[0], c[2]) if ORDER_RGB else c


def _scale(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


# ---------------------------------------------------------------------------
class Strip:
    """Blocking effects.  Fine on the bench, wrong inside a main loop."""

    def __init__(self, n=N, pin=DIN):
        self.n = n
        self.np = neopixel.NeoPixel(Pin(pin, Pin.OUT), n)

    # -- primitives ---------------------------------------------------------
    def show(self):
        self.np.write()

    def set(self, i, colour):
        if 0 <= i < self.n:
            self.np[i] = _order(colour)

    def solid(self, colour, show=True):
        for i in range(self.n):
            self.np[i] = _order(colour)
        if show:
            self.show()

    def off(self):
        self.solid(BLACK)

    # -- effects ------------------------------------------------------------
    def breathe(self, colour, cycles=2, step_ms=20):
        for _ in range(cycles):
            for f in list(range(0, 21)) + list(range(20, -1, -1)):
                self.solid(_scale(colour, f / 20.0))
                time.sleep_ms(step_ms)

    def chase(self, colour, laps=3, step_ms=70, tail=2):
        for _ in range(laps):
            for head in range(self.n):
                for i in range(self.n):
                    d = (head - i) % self.n
                    self.np[i] = _order(_scale(colour, max(0.0, 1 - d / (tail + 1.0))))
                self.show()
                time.sleep_ms(step_ms)
        self.off()

    def flash(self, colour, times=4, on_ms=120, off_ms=120):
        for _ in range(times):
            self.solid(colour)
            time.sleep_ms(on_ms)
            self.off()
            time.sleep_ms(off_ms)

    def meter(self, value, lo=BLACK, hi=None, show=True):
        """Bar graph, 0.0 to 1.0.  Green -> yellow -> red across the strip.

        Use it for the MQ-2 ratio: meter(ratio / 2.0) puts the 1.5x alarm
        threshold at three quarters of the strip.
        """
        lit = int(max(0.0, min(1.0, value)) * self.n + 0.5)
        for i in range(self.n):
            if i < lit:
                f = i / max(1, self.n - 1)
                if f < 0.5:
                    c = (int(BRIGHT * f * 2), BRIGHT, 0)
                else:
                    c = (BRIGHT, int(BRIGHT * (1 - f) * 2), 0)
                self.np[i] = _order(c)
            else:
                self.np[i] = _order(BLACK)
        if show:
            self.show()

    def wheel(self, laps=1, step_ms=15):
        """Rainbow sweep.  Proves every pixel and every channel at once."""
        for _ in range(laps):
            for offset in range(0, 256, 4):
                for i in range(self.n):
                    p = (i * 256 // self.n + offset) & 255
                    if p < 85:
                        c = (255 - p * 3, p * 3, 0)
                    elif p < 170:
                        p -= 85
                        c = (0, 255 - p * 3, p * 3)
                    else:
                        p -= 170
                        c = (p * 3, 0, 255 - p * 3)
                    self.np[i] = _order(_scale(c, BRIGHT / 255.0))
                self.show()
                time.sleep_ms(step_ms)
        self.off()


# ---------------------------------------------------------------------------
class Status:
    """Non-blocking state indicator.  Nothing here sleeps.

        s = Status()
        s.set("idle")
        while True:
            s.tick()            # call as often as you like, it self-paces
            ... your real work ...
    """

    FRAME_MS = 25

    def __init__(self, n=N, pin=DIN):
        self.s = Strip(n, pin)
        self.state = "off"
        self.colour = BLACK
        self.mode = "solid"
        self.frame = 0
        self.last = time.ticks_ms()
        self.s.off()

    def set(self, state):
        if state == self.state:
            return
        if state not in STATES:
            state = "error"
        self.state = state
        self.colour, self.mode = STATES[state]
        self.frame = 0

    def tick(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last) < self.FRAME_MS:
            return
        self.last = now
        f = self.frame
        self.frame += 1

        if self.mode == "solid":
            if f == 0:
                self.s.solid(self.colour)

        elif self.mode == "breathe":
            phase = f % 80
            level = phase if phase < 40 else 80 - phase
            self.s.solid(_scale(self.colour, level / 40.0))

        elif self.mode == "chase":
            head = (f // 3) % self.s.n
            for i in range(self.s.n):
                d = (head - i) % self.s.n
                self.s.np[i] = _order(_scale(self.colour, max(0.0, 1 - d / 3.0)))
            self.s.show()

        elif self.mode == "flash":
            self.s.solid(self.colour if (f // 6) % 2 == 0 else BLACK)

    def off(self):
        self.set("off")
        self.s.off()


# ---------------------------------------------------------------------------
def demo():
    """Every effect once.  About 40 s."""
    s = Strip()
    print("  wheel        - every pixel, every channel")
    s.wheel()
    print("  solid RGBW   - colour order check")
    for c, name in ((RED, "red"), (GREEN, "green"), (BLUE, "blue"),
                    (WHITE, "white")):
        print("    %s" % name)
        s.solid(c)
        time.sleep(1)
    s.off()
    print("  breathe blue - the idle state")
    s.breathe(BLUE)
    print("  chase yellow - the thinking state")
    s.chase(YELLOW)
    print("  flash red    - the alert state")
    s.flash(RED)
    print("  meter sweep  - the MQ-2 bar")
    for v in range(0, 21):
        s.meter(v / 20.0)
        time.sleep_ms(80)
    for v in range(20, -1, -1):
        s.meter(v / 20.0)
        time.sleep_ms(40)
    s.off()
    print("\n  Done.  Red showed red = GRB order correct.")
    print("  All 8 pixels lit in the wheel = no break, no level problem.")


def states(hold=2):
    """Walk the six GENIE states so you can agree the colours by eye."""
    st = Status()
    for name in ("idle", "heard", "thinking", "speaking", "alert", "error"):
        print("  %-9s %s" % (name, STATES[name][1]))
        st.set(name)
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < hold * 1000:
            st.tick()
            time.sleep_ms(5)
    st.off()


if __name__ == "__main__":
    demo()
