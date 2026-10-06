"""
test_dht11.py - DHT11 temperature and humidity.

Wire ONLY this after the TFT passes.
    DHT11 DATA -> GPIO21  (P2-18)
    VCC -> 3V3 rail        GND -> common GND
    A 4.7k-10k pull-up from DATA to 3V3 if the module is the bare 3-pin
    type.  The 4-pin breakout board already has one fitted.

OSError(116,) means ETIMEDOUT - the sensor never answered.  In order of
likelihood:
    1  read faster than once per 2 s  (the DHT11 simply will not answer)
    2  no pull-up on DATA
    3  DATA on the wrong pin
    4  the sensor is on 3V3 but wants 5V - most DHT11 modules take either,
       a few insist on 5V
    5  dead sensor

    >>> import test_dht11
    >>> test_dht11.run()
"""

from machine import Pin
import time
import dht

DHT_PIN = 21
MIN_INTERVAL_MS = 2000          # DHT11 hard limit, do not lower


def wired():
    up = Pin(DHT_PIN, Pin.IN, Pin.PULL_UP).value()
    time.sleep_ms(5)
    dn = Pin(DHT_PIN, Pin.IN, Pin.PULL_DOWN).value()
    Pin(DHT_PIN, Pin.IN, None)
    if up == 1 and dn == 1:
        return True, "DATA held HIGH - pull-up present, idle.  Correct."
    if up == 1 and dn == 0:
        return False, ("DATA floating - no pull-up and no module.  Fit a "
                       "4.7k to 3V3.")
    return False, "DATA held LOW - shorted, or sensor is holding the line"


def check():
    print("=" * 58)
    print("  DHT11 CHECK  (GPIO%d)" % DHT_PIN)
    print("=" * 58)
    ok, why = wired()
    print("    %s" % why)

    d = dht.DHT11(Pin(DHT_PIN))
    good = 0
    for i in range(5):
        try:
            d.measure()
            t, h = d.temperature(), d.humidity()
            print("    try %d   %d C   %d %%RH" % (i + 1, t, h))
            good += 1
        except OSError as e:
            print("    try %d   FAILED  %r" % (i + 1, e))
        time.sleep_ms(MIN_INTERVAL_MS)

    print("\n  %d/5 reads succeeded." % good)
    if good == 0:
        print("  FAIL - see the header of this file, causes are listed in")
        print("  order of likelihood.")
    elif good < 4:
        print("  MARGINAL - intermittent.  Almost always the pull-up or a")
        print("  long/unshielded DATA wire.  Shorten it.")
    else:
        print("  PASS")
    return good >= 4


def live():
    d = dht.DHT11(Pin(DHT_PIN))
    fails = 0
    print("\n  Ctrl-C to stop.  One read every 2 s - that is the sensor's")
    print("  own limit, reading faster returns errors, not fresh data.\n")
    try:
        while True:
            try:
                d.measure()
                print("  %5d C    %3d %%RH" % (d.temperature(), d.humidity()))
            except OSError as e:
                fails += 1
                print("  read failed %r  (%d so far)" % (e, fails))
            time.sleep_ms(MIN_INTERVAL_MS)
    except KeyboardInterrupt:
        print("\n  stopped.  %d failed read(s)." % fails)


def run():
    if check():
        live()


if __name__ == "__main__":
    run()
