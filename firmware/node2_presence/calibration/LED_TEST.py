# =============================================================================
# LED_TEST.py  -  GENIE Node 2
# Find out what is actually wrong with the RGB LED. F5 in Thonny.
#
# Needs nothing on the board. Imports no drivers. Touches no sensor.
#
# Why this exists: neopixel.NeoPixel(Pin(38), 1) NEVER raises, even if there is
# no LED on GPIO38. A wrong pin fails completely silently - the code looks
# healthy and the LED does nothing. Only watching the board tells you.
# =============================================================================

from machine import Pin
import time

# Candidate pins for the onboard WS2812 across DevKitC-1 revisions and clones.
CANDIDATES = (38, 48, 47, 21, 45)

BRIGHT = 60


def hold(np, col, name, secs=1.5):
    np[0] = col
    np.write()
    print("      " + name)
    time.sleep(secs)


def sweep():
    print("=" * 60)
    print("TEST 1 - pin sweep")
    print("=" * 60)
    print("WATCH THE BOARD. Ignore the small always-on power LED near the")
    print("USB sockets - that is not the RGB LED and it never changes.")
    print("The RGB LED is a single white square, usually beside the reset")
    print("button. Note which GPIO makes it light.")
    print("")
    import neopixel

    for p in CANDIDATES:
        print("  GPIO" + str(p) + ":")
        try:
            np = neopixel.NeoPixel(Pin(p), 1)
        except Exception as e:
            print("      cannot use this pin:", e)
            continue
        hold(np, (BRIGHT, 0, 0), "should be RED")
        hold(np, (0, BRIGHT, 0), "should be GREEN")
        hold(np, (0, 0, BRIGHT), "should be BLUE")
        np[0] = (0, 0, 0)
        np.write()
        time.sleep(0.4)

    print("")
    print("Which GPIO lit up? Put it in LED_PIN in the other scripts.")
    print("If NONE of them lit, the WS2812 is unpopulated or dead on this")
    print("board - very common on cheap clones. Go to TEST 3.")


def order(pin):
    print("=" * 60)
    print("TEST 2 - colour order on GPIO" + str(pin))
    print("=" * 60)
    import neopixel
    np = neopixel.NeoPixel(Pin(pin), 1)
    print("MicroPython assumes GRB (standard WS2812). Some clones are RGB,")
    print("which swaps red and green - exactly the symptom of 'stuck green'.")
    print("")
    hold(np, (BRIGHT, 0, 0), "code says RED   -> if you see GREEN, order is swapped", 3)
    hold(np, (0, BRIGHT, 0), "code says GREEN -> if you see RED,   order is swapped", 3)
    np[0] = (0, 0, 0)
    np.write()
    print("")
    print("If swapped: in the other scripts just exchange the arguments in")
    print("led_red() and led_green(). Do not patch the neopixel module.")


def brightness(pin):
    print("=" * 60)
    print("TEST 3 - brightness ramp on GPIO" + str(pin))
    print("=" * 60)
    print("Rules out 'it is working but too dim to see inside the box'.")
    import neopixel
    np = neopixel.NeoPixel(Pin(pin), 1)
    for b in (1, 5, 20, 60, 150, 255):
        np[0] = (b, 0, 0)
        np.write()
        print("      red level " + str(b))
        time.sleep(0.8)
    np[0] = (0, 0, 0)
    np.write()


def external():
    print("=" * 60)
    print("TEST 4 - plain external LEDs")
    print("=" * 60)
    print("Wiring, per LED:  GPIO --- 330R --- LED anode")
    print("                  LED cathode --- GND")
    print("Suggested free pins on this node: RED = GPIO5, GREEN = GPIO21")
    print("")
    try:
        rp = int(input("  red pin   [5]  > ") or "5")
        gp = int(input("  green pin [21] > ") or "21")
    except Exception:
        rp, gp = 5, 21

    r = Pin(rp, Pin.OUT, value=0)
    g = Pin(gp, Pin.OUT, value=0)
    print("  alternating for 8 s ...")
    for _ in range(16):
        r.value(1)
        g.value(0)
        time.sleep(0.25)
        r.value(0)
        g.value(1)
        time.sleep(0.25)
    r.value(0)
    g.value(0)
    print("  done. If both blinked, set LED_MODE = 'pins' in the other scripts.")


def blink_alive(pin):
    """Proves the GPIO itself toggles - meter or scope on the pin."""
    print("=" * 60)
    print("TEST 5 - raw square wave on GPIO" + str(pin) + " for 10 s")
    print("=" * 60)
    print("Put a multimeter on it. Should read roughly half of 3.3 V.")
    print("If it reads 0.00 V the pin is dead or reserved - check the")
    print("forbidden list in FRESH_START.md.")
    p = Pin(pin, Pin.OUT)
    t_end = time.ticks_add(time.ticks_ms(), 10000)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        p.value(1)
        time.sleep_ms(1)
        p.value(0)
        time.sleep_ms(1)
    print("  done")


def main():
    while True:
        print("")
        print("=" * 60)
        print("LED DIAGNOSTIC")
        print("=" * 60)
        print(" 1  pin sweep - find the onboard RGB LED   <- START HERE")
        print(" 2  colour order check (red/green swapped?)")
        print(" 3  brightness ramp")
        print(" 4  external LEDs on plain GPIOs")
        print(" 5  raw square wave, for a multimeter")
        print(" 0  quit")
        try:
            c = input("> ").strip()
        except KeyboardInterrupt:
            return

        if c == "1":
            sweep()
        elif c == "2":
            order(int(input("  pin > ").strip()))
        elif c == "3":
            brightness(int(input("  pin > ").strip()))
        elif c == "4":
            external()
        elif c == "5":
            blink_alive(int(input("  pin > ").strip()))
        elif c == "0":
            return


main()
