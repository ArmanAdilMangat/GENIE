"""
test_button.py - the one GENIE button.

Wire ONLY this after the TFT passes.
    button -> GPIO39  (P2-9)  ->  other side of the button to GND
    No external resistor.  The internal pull-up does the job.

Pressed = 0, released = 1.

GPIO39 was chosen over GPIO0 on purpose.  GPIO0 is a strapping pin: any
wiring fault that holds it low makes the board boot into the ROM
bootloader and Thonny cannot connect at all - the fault hides itself.  On
GPIO39 the same fault is merely visible.

This file also proves the single / double / long press decoder that the
GENIE UI depends on, so a gesture that misfires here will misfire there.

    >>> import test_button
    >>> test_button.run()
"""

from machine import Pin
import time

BTN = 39
DEBOUNCE_MS = 30
DOUBLE_MS = 350                 # second press must start within this
LONG_MS = 700                   # held at least this long = long press


def wired():
    p = Pin(BTN, Pin.IN, Pin.PULL_UP)
    time.sleep_ms(10)
    v = p.value()
    if v == 1:
        return True, "reads 1 - released.  Pull-up working."
    return False, ("reads 0 with nothing pressed - button stuck, wired to "
                   "3V3 instead of GND, or shorted")


def check():
    print("=" * 58)
    print("  BUTTON CHECK  (GPIO%d)" % BTN)
    print("=" * 58)
    ok, why = wired()
    print("    %s" % why)
    if not ok:
        print("\n  FAIL")
        return False

    print("\n    Press and hold the button for 2 seconds...")
    p = Pin(BTN, Pin.IN, Pin.PULL_UP)
    t0 = time.ticks_ms()
    seen = False
    while time.ticks_diff(time.ticks_ms(), t0) < 10000:
        if p.value() == 0:
            seen = True
            break
        time.sleep_ms(10)
    if not seen:
        print("    never went low in 10 s.  FAIL - check the GND side.")
        return False

    held = time.ticks_ms()
    while p.value() == 0:
        time.sleep_ms(10)
    ms = time.ticks_diff(time.ticks_ms(), held)
    print("    held for %d ms.  PASS." % ms)
    return True


def gestures(seconds=45):
    """Decoder: single, double, long.  Same logic the GENIE UI uses."""
    p = Pin(BTN, Pin.IN, Pin.PULL_UP)
    print("\n  Try: one tap, two quick taps, one long hold.  %d s or Ctrl-C\n"
          % seconds)

    t_end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    pending = 0
    last_release = 0
    try:
        while time.ticks_diff(t_end, time.ticks_ms()) > 0:
            if p.value() == 0:
                down = time.ticks_ms()
                time.sleep_ms(DEBOUNCE_MS)
                while p.value() == 0:
                    if time.ticks_diff(time.ticks_ms(), down) > LONG_MS:
                        break
                    time.sleep_ms(5)
                held = time.ticks_diff(time.ticks_ms(), down)

                if held >= LONG_MS:
                    while p.value() == 0:
                        time.sleep_ms(10)
                    print("  LONG   (%d ms)"
                          % time.ticks_diff(time.ticks_ms(), down))
                    pending = 0
                else:
                    up = time.ticks_ms()
                    if pending and time.ticks_diff(up, last_release) \
                            < DOUBLE_MS:
                        print("  DOUBLE")
                        pending = 0
                    else:
                        pending = 1
                        last_release = up
                time.sleep_ms(DEBOUNCE_MS)

            if pending and time.ticks_diff(time.ticks_ms(), last_release) \
                    > DOUBLE_MS:
                print("  SINGLE")
                pending = 0
            time.sleep_ms(5)
    except KeyboardInterrupt:
        pass
    print("\n  stopped")


def run():
    if check():
        gestures()


if __name__ == "__main__":
    run()
