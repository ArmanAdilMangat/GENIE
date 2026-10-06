"""
test_mq2.py - MQ-2 smoke/gas, both modules.

Wire ONLY this after the TFT passes.
    MQ-2 #1  AO -> GPIO1   (P2-4)   VCC -> 5V bench   GND -> common GND
    MQ-2 #2  AO -> GPIO2   (P2-5)   VCC -> 5V bench   GND -> common GND

GPIO1 and GPIO2 are the only two usable ADC1 pins.  Do not move these to
GPIO11-20: that is ADC2, which returns garbage the moment WiFi or ESP-NOW
is running.

The bench supply GND MUST be tied to the ESP32 GND.  Without a common
ground the ADC has no reference and the readings wander between two levels.
That was the old "bimodal" fault - it was never the sensor.

    >>> import test_mq2
    >>> test_mq2.run()          # warm-up, baseline, then live
    >>> test_mq2.live()         # skip warm-up, straight to readings
"""

from machine import Pin, ADC
import time

MQ2_1 = 1
MQ2_2 = 2
ADC_VREF = 3.3
ADC_MAX = 4095
ADC_LINEAR_MAX = 3040          # above this the ESP32 ADC flattens out
WARMUP_S = 90                  # heater needs this long from cold
ALERT_RATIO = 1.20
ALARM_RATIO = 1.50


def make_adc(pin):
    a = ADC(Pin(pin))
    try:
        a.atten(ADC.ATTN_11DB)
    except AttributeError:
        pass
    if hasattr(a, "read"):
        try:
            a.width(ADC.WIDTH_12BIT)
        except AttributeError:
            pass
        return a.read
    return lambda: a.read_u16() >> 4


def avg(read, n=16):
    t = 0
    for _ in range(n):
        t += read()
        time.sleep_ms(2)
    return t // n


def volts(raw):
    return raw * ADC_VREF / ADC_MAX


def bar(v, lo=0.5, hi=2.0, w=20, mark=1.0):
    pos = max(0, min(w, int((v - lo) / (hi - lo) * w)))
    mk = max(0, min(w - 1, int((mark - lo) / (hi - lo) * w)))
    return "".join("#" if i < pos else ("|" if i == mk else ".")
                   for i in range(w))


def check():
    """One shot: are both channels plausible?"""
    print("=" * 58)
    print("  MQ-2 CHANNEL CHECK")
    print("=" * 58)
    ok = True
    for name, pin in (("#1", MQ2_1), ("#2", MQ2_2)):
        raw = avg(make_adc(pin))
        v = volts(raw)
        if raw < 60:
            verdict = "DEAD - AO not connected, or module has no 5V"
            ok = False
        elif raw > ADC_LINEAR_MAX:
            verdict = "RAILED - fit the 10k/20k divider, ADC is saturated"
            ok = False
        else:
            verdict = "plausible"
        print("    MQ-2 %s  GPIO%-2d  raw %4d  %.2f V   %s"
              % (name, pin, raw, v, verdict))
    print("\n  %s" % ("PASS" if ok else "FAIL - fix the above first"))
    return ok


def warmup(seconds=WARMUP_S):
    print("  heater warm-up, %d s.  Readings drift the whole time - that is"
          % seconds)
    print("  the heater, not a fault.  Do not judge anything until it ends.")
    a1, a2 = make_adc(MQ2_1), make_adc(MQ2_2)
    t0 = time.time()
    while time.time() - t0 < seconds:
        left = seconds - int(time.time() - t0)
        print("    %3ds left   #1 %4d   #2 %4d" % (left, avg(a1), avg(a2)))
        time.sleep(5)
    print("  warm.")


def baseline(samples=20):
    a1, a2 = make_adc(MQ2_1), make_adc(MQ2_2)
    s1 = s2 = 0
    for _ in range(samples):
        s1 += avg(a1)
        s2 += avg(a2)
        time.sleep_ms(100)
    b1, b2 = s1 / samples, s2 / samples
    print("  baseline (clean air):  #1 %.0f   #2 %.0f" % (b1, b2))
    return b1, b2


def live(b1=None, b2=None):
    """Live ratio display.  Hold a lit lighter (unlit, gas only) near a
    module and its ratio should climb past 1.20 within a couple of seconds."""
    if b1 is None:
        b1, b2 = baseline()
    a1, a2 = make_adc(MQ2_1), make_adc(MQ2_2)
    print("\n  Ctrl-C to stop.  | marks the clean-air baseline.\n")
    try:
        while True:
            r1, r2 = avg(a1), avg(a2)
            q1, q2 = r1 / b1, r2 / b2
            f1 = "ALARM" if q1 > ALARM_RATIO else \
                 ("alert" if q1 > ALERT_RATIO else "     ")
            f2 = "ALARM" if q2 > ALARM_RATIO else \
                 ("alert" if q2 > ALERT_RATIO else "     ")
            print("  #1 %4d %.2fx [%s] %s    #2 %4d %.2fx [%s] %s"
                  % (r1, q1, bar(q1), f1, r2, q2, bar(q2), f2))
            time.sleep_ms(500)
    except KeyboardInterrupt:
        print("\n  stopped")


def run():
    if not check():
        return
    warmup()
    b1, b2 = baseline()
    live(b1, b2)


if __name__ == "__main__":
    run()
