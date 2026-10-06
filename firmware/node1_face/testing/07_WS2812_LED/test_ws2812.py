"""
test_ws2812.py - WS2812 / NeoPixel status strip.

Wire ONLY this after the TFT passes.
    DIN -> GPIO48  (P2-16)
    5V  -> bench supply 5V      GND -> common GND

GPIO48 is also the ESP32-S3 DevKitC-1's ONBOARD RGB LED.  With nothing
wired, N=1 still works and the onboard LED lights - that is a free test of
the pin before you connect anything.  With a strip wired, the onboard LED
becomes pixel 0 and the strip starts at pixel 1.

A WS2812 wants 5V data.  Driven straight from a 3.3V ESP32 pin most strips
work, some are flaky at the far end.  If colours are right at pixel 0 and
wrong further along, that is the level, not the code - a single diode or a
74HCT125 on the data line fixes it.

Never power a long strip from the ESP32's 5V pin.  60 LEDs at full white
is 3.6 A and it will brown out the board.

    >>> import test_ws2812
    >>> test_ws2812.run()        # assumes 1 pixel (onboard only)
    >>> test_ws2812.run(8)       # 8-pixel strip wired
"""

from machine import Pin
import time
import neopixel

DIN = 48
DEFAULT_N = 1
BRIGHT = 40                     # keep low on the bench: full white is hot


def strip(n=DEFAULT_N):
    return neopixel.NeoPixel(Pin(DIN, Pin.OUT), n)


def off(n=DEFAULT_N):
    np = strip(n)
    for i in range(n):
        np[i] = (0, 0, 0)
    np.write()


def check(n=DEFAULT_N):
    print("=" * 58)
    print("  WS2812 CHECK  (GPIO%d, %d pixel(s))" % (DIN, n))
    print("=" * 58)
    np = strip(n)
    for colour, label in (((BRIGHT, 0, 0), "RED"),
                          ((0, BRIGHT, 0), "GREEN"),
                          ((0, 0, BRIGHT), "BLUE"),
                          ((BRIGHT, BRIGHT, BRIGHT), "WHITE")):
        for i in range(n):
            np[i] = colour
        np.write()
        print("    all %s" % label)
        time.sleep(1)
    off(n)
    print("""
    Saw all four colours in order          -> PASS
    Colours swapped (red shows green etc.) -> your strip is RGB not GRB.
                                              Swap the tuple order.
    Nothing at all                         -> DIN on the wrong pin, or the
                                              strip has no 5V
    First pixel right, rest wrong/random   -> 3.3V data level, see the
                                              header of this file
    """)


def chase(n=DEFAULT_N, laps=3):
    """Walks one lit pixel down the strip.  Counts your pixels for you and
    exposes a break: everything past a bad pixel stays dark."""
    np = strip(n)
    for _ in range(laps):
        for i in range(n):
            for j in range(n):
                np[j] = (BRIGHT, 0, 0) if j == i else (0, 0, 0)
            np.write()
            time.sleep_ms(80)
    off(n)
    print("    chase done - count the pixels that lit.  Fewer than %d means"
          % n)
    print("    a break at that position." if n > 1 else "    (single pixel)")


def status_demo(n=DEFAULT_N):
    """The four states GENIE actually uses, so the colours get agreed on
    once here instead of drifting across files."""
    np = strip(n)
    states = ((0, 0, BRIGHT), "IDLE     listening for the wake word"), \
             ((0, BRIGHT, 0), "HEARD    wake word matched"), \
             ((BRIGHT, BRIGHT, 0), "THINKING  Whisper + Mistral running"), \
             ((BRIGHT, 0, 0), "ALERT    a sensor tripped")
    for colour, label in states:
        for i in range(n):
            np[i] = colour
        np.write()
        print("    %s" % label)
        time.sleep(1.5)
    off(n)


def run(n=DEFAULT_N):
    check(n)
    chase(n)
    status_demo(n)
    print("\n  Done.  Strip PASSES if all four colours and the chase were")
    print("  correct.  That is every sensor tested - next: 10_Integration.")


if __name__ == "__main__":
    run()
