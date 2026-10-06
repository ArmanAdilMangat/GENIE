"""GENIE Node 2 -- characterisation bench for the mounted 4x ToF array.

MODULE. Upload to the board.

Reuses pins3.py, tof3.py, vl53l1x.py and zones.py, which are already on the
board from 07_ToF3_Fingerprint. Nothing is duplicated here -- if the pin map
changes it changes in one place.

WHAT THIS ADDS OVER THE 07 BENCH
    07 answers "are the sensors wired correctly".
    This answers "what can they actually see once mounted on GENIE's body",
    which is a different question and the one the report needs:
      - per-sensor baseline and noise on the real chassis
      - per-sensor usable min and max range, measured not quoted
      - a derived detection threshold that suits each side
      - red/green status LED, hysteresis so it does not strobe
      - results written to JSON and CSV so a rerun can be compared
"""

VERSION = "tof_bench 1.0  2026-08-15"

import time
import json
from machine import Pin

import pins3 as P
import tof3
import tof_test_cfg as C
from zones import cm


# ================================================================= status LED
class Status:
    """WS2812 status light. Degrades to prints if neopixel is unavailable."""

    def __init__(self, pin=None, count=None, brightness=None):
        self.pin = C.RGB_PIN if pin is None else pin
        self.count = C.RGB_COUNT if count is None else count
        self.bright = C.BRIGHTNESS if brightness is None else brightness
        self.np = None
        try:
            from neopixel import NeoPixel
            self.np = NeoPixel(Pin(self.pin, Pin.OUT), self.count)
            self.off()
        except Exception as e:
            print("  (status LED unavailable on GPIO%d: %s)" % (self.pin, e))

    def _scale(self, rgb):
        return tuple(int(c * self.bright) for c in rgb)

    def all(self, rgb):
        if not self.np:
            return
        v = self._scale(rgb)
        for i in range(self.count):
            self.np[i] = v
        self.np.write()

    def pixel(self, i, rgb):
        if not self.np or i >= self.count:
            return
        self.np[i] = self._scale(rgb)

    def show(self):
        if self.np:
            self.np.write()

    def off(self):
        self.all((0, 0, 0))


def find_led_pin():
    """Cycle red/green/blue on GPIO38 then GPIO48. Watch the board."""
    from neopixel import NeoPixel
    for pin in (C.RGB_PIN, C.RGB_ALT_PIN):
        print("\n  trying GPIO%d -- watch the onboard LED" % pin)
        try:
            np = NeoPixel(Pin(pin, Pin.OUT), 1)
            for name, col in (("RED", (1, 0, 0)),
                              ("GREEN", (0, 1, 0)),
                              ("BLUE", (0, 0, 1))):
                np[0] = tuple(int(c * C.BRIGHTNESS) for c in col)
                np.write()
                print("    %s" % name)
                time.sleep(1)
            np[0] = (0, 0, 0)
            np.write()
        except Exception as e:
            print("    failed: %s" % e)
    print("\n  Whichever pin lit up: set RGB_PIN to it in tof_test_cfg.py")
    print("  v1.0 boards use GPIO48, v1.1 boards use GPIO38.")


# ================================================================== maths
def _stats(vals):
    if not vals:
        return None
    n = len(vals)
    mean = sum(vals) / n
    var = sum((x - mean) ** 2 for x in vals) / n
    return {"n": n, "min": min(vals), "max": max(vals),
            "mean": mean, "sd": var ** 0.5}


def _threshold_from(baseline, saw_anything):
    """Derive a per-sensor threshold. Open space falls back to the default."""
    if not saw_anything or baseline is None or baseline >= P.MAX_TRUST_MM:
        return C.DEFAULT_THRESHOLD_MM
    t = baseline - C.MARGIN_MM
    if t < C.MIN_THRESHOLD_MM:
        t = C.MIN_THRESHOLD_MM
    if t > C.MAX_THRESHOLD_MM:
        t = C.MAX_THRESHOLD_MM
    return int(t)


def _verdict(st):
    """Plain-English description of what a sensor is looking at."""
    if st is None:
        return "no samples -- sensor silent"
    mean, sd = st["mean"], st["sd"]
    if mean < 100:
        desc = "BLOCKED -- something is against the lens"
    elif mean < 500:
        desc = "close surface at %d cm" % (mean / 10)
    elif mean < 1500:
        desc = "surface at %.1f m" % (mean / 1000)
    elif mean < P.MAX_TRUST_MM:
        desc = "far surface at %.1f m" % (mean / 1000)
    else:
        desc = "open space -- nothing in range"
    if sd > 50:
        desc += "  (NOISY, sd %d mm)" % sd
    return desc


# ============================================================= calibration
def calibrate(sensors, seconds=None, status=None):
    """Watch a still scene and learn each sensor's resting view.

    Nothing may move during this. The whole point is to learn what GENIE's
    chassis sees when the room is empty, so that 'something is there' can be
    defined relative to that rather than by one global number.
    """
    seconds = seconds or C.CAL_SECONDS
    n = len(sensors)

    print("\n--- calibration -------------------------------------------")
    print("  HOLD STILL. Nobody in front of the sensors. %d s.\n" % seconds)
    if status:
        status.all(C.COLOUR_CAL)

    for i in range(3, 0, -1):
        print("    starting in %d..." % i)
        time.sleep(1)

    samples = [[] for _ in range(n)]
    invalid = [0] * n

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
        settled = time.ticks_diff(time.ticks_ms(), t0) > C.CAL_DISCARD_MS
        for i, mm in enumerate(tof3.read_all(sensors)):
            if mm is None:
                continue
            if not settled:
                continue
            if mm <= C.SATURATE_MM:
                invalid[i] += 1
            else:
                samples[i].append(mm)
        time.sleep_ms(C.LOOP_MS)

    if status:
        status.off()

    cal = {}
    print("  %-6s %5s %6s %6s %7s %6s   %s"
          % ("side", "n", "min", "max", "mean", "sd", "what it sees"))
    print("  " + "-" * 74)
    for i in range(n):
        st = _stats(samples[i])
        thr = _threshold_from(st["mean"] if st else None, bool(st))
        cal[P.NAMES[i]] = {
            "index": i,
            "addr": P.ADDRESSES[i],
            "xshut": P.XSHUT[i],
            "stats": st,
            "invalid": invalid[i],
            "threshold_mm": thr,
        }
        if st:
            print("  %-6s %5d %6d %6d %7.0f %6.1f   %s"
                  % (P.NAMES[i], st["n"], st["min"], st["max"],
                     st["mean"], st["sd"], _verdict(st)))
        else:
            print("  %-6s %5d %6s %6s %7s %6s   %s"
                  % (P.NAMES[i], 0, "-", "-", "-", "-", _verdict(None)))

    print("\n  derived thresholds (trigger when closer than this):")
    for i in range(n):
        c = cal[P.NAMES[i]]
        print("    %-6s %4d mm  (%.0f cm)"
              % (P.NAMES[i], c["threshold_mm"], c["threshold_mm"] / 10))
    print("\n  sd under ~10 mm indoors is healthy. Above ~50 mm means ambient")
    print("  light, a dark or angled target, or a loose connection.")

    save_cal(cal)
    return cal


def save_cal(cal):
    try:
        with open(C.CAL_FILE, "w") as fh:
            json.dump(cal, fh)
        print("  saved to %s" % C.CAL_FILE)
    except OSError as e:
        print("  could not save calibration: %s" % e)


def load_cal():
    try:
        with open(C.CAL_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ============================================================== range sweep
def range_sweep(sensors, index, seconds=None):
    """Measure the REAL min and max for one sensor, mounted, in this room.

    The datasheet says 4 m. That is a laboratory number. What matters for the
    report is what this sensor achieves on GENIE's chassis under this lighting
    against a human-sized target, which is usually a lot less.
    """
    seconds = seconds or C.SWEEP_SECONDS
    s = sensors[index]
    if s is None:
        print("  %s did not come up -- skipping" % P.NAMES[index])
        return None

    print("\n--- range sweep: %s ---------------------------------"
          % P.NAMES[index].upper())
    print("  Start with your hand ON the lens.")
    print("  Move it away SLOWLY and steadily until the reading stops")
    print("  tracking you. Then bring it back. %d s.\n" % seconds)
    for i in range(3, 0, -1):
        print("    go in %d..." % i)
        time.sleep(1)

    vals = []
    saturated = 0
    dropouts = 0
    t0 = time.ticks_ms()
    nxt = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
        try:
            if s.data_ready():
                mm = s.distance()
                if mm is None:
                    dropouts += 1
                elif mm <= C.SATURATE_MM:
                    saturated += 1
                else:
                    vals.append(mm)
        except OSError:
            dropouts += 1
        if time.ticks_diff(time.ticks_ms(), nxt) >= 0:
            nxt = time.ticks_add(time.ticks_ms(), C.PRINT_MS)
            print("      %s cm" % cm(vals[-1] if vals else None))
        time.sleep_ms(C.LOOP_MS)

    st = _stats(vals)
    if not st:
        print("\n  no valid samples at all -- check this sensor")
        return None

    result = {"min_mm": st["min"], "max_mm": st["max"],
              "samples": st["n"], "saturated": saturated,
              "dropouts": dropouts}
    print("\n  %s:" % P.NAMES[index])
    print("    usable min : %4d mm  (%.1f cm)" % (st["min"], st["min"] / 10))
    print("    usable max : %4d mm  (%.2f m)" % (st["max"], st["max"] / 1000))
    print("    samples    : %d valid, %d saturated, %d dropped"
          % (st["n"], saturated, dropouts))
    if st["max"] < 1500:
        print("    NOTE: under 1.5 m. Bright ambient light or a dark target.")
        print("          Try again with the blinds shut, or use SHORT mode.")
    return result


# =========================================================== live detection
class Detector:
    """Per-sensor debounced presence, with hysteresis so it cannot strobe."""

    def __init__(self, threshold_mm):
        self.thr = threshold_mm
        self.present = False
        self._count = 0
        self._want = False
        self.last_mm = None
        self.trips = 0

    def update(self, mm):
        """Returns True/False if the state CHANGED, else None."""
        if mm is None:
            return None
        self.last_mm = mm

        if self.present:
            # only release once clearly outside -- hysteresis on the way out
            want = not (mm > self.thr + C.HYST_MM)
        else:
            want = mm < self.thr and mm > C.SATURATE_MM

        if want != self._want:
            self._want = want
            self._count = 1
        else:
            self._count += 1

        if want != self.present and self._count >= C.CONFIRM_N:
            self.present = want
            if want:
                self.trips += 1
            return want
        return None


def monitor(sensors, cal, status=None, seconds=None):
    """Live red/green. This is the demo, and it is also the acceptance test."""
    seconds = seconds or C.MONITOR_SECONDS
    n = len(sensors)

    dets = []
    for i in range(n):
        entry = cal.get(P.NAMES[i]) if cal else None
        thr = entry["threshold_mm"] if entry else C.DEFAULT_THRESHOLD_MM
        dets.append(Detector(thr))

    print("\n--- live detection ----------------------------------------")
    print("  thresholds: %s"
          % ", ".join("%s %dmm" % (P.NAMES[i], dets[i].thr) for i in range(n)))
    print("  RED   = something in front of at least one sensor")
    print("  GREEN = all sides clear")
    print("  %d s. Ctrl+C to stop.\n" % seconds)

    per_pixel = status and status.count >= n
    last_any = None
    t0 = time.ticks_ms()
    nxt = time.ticks_ms()

    try:
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            for i, mm in enumerate(tof3.read_all(sensors)):
                changed = dets[i].update(mm)
                if changed is True:
                    print("      >> %-6s  OBJECT at %s cm"
                          % (P.NAMES[i], cm(dets[i].last_mm)))
                elif changed is False:
                    print("      >> %-6s  clear" % P.NAMES[i])

            any_present = any(d.present for d in dets)

            if status:
                if per_pixel:
                    for i in range(n):
                        status.pixel(i, C.COLOUR_DETECT if dets[i].present
                                     else C.COLOUR_CLEAR)
                    status.show()
                elif any_present != last_any:
                    status.all(C.COLOUR_DETECT if any_present
                               else C.COLOUR_CLEAR)
            last_any = any_present

            if time.ticks_diff(time.ticks_ms(), nxt) >= 0:
                nxt = time.ticks_add(time.ticks_ms(), C.PRINT_MS)
                cells = " | ".join(
                    "%-5s%s%s" % (P.NAMES[i][:5], cm(dets[i].last_mm),
                                  "*" if dets[i].present else " ")
                    for i in range(n))
                print("  %s   %s" % (cells, "DETECT" if any_present else "clear"))

            time.sleep_ms(C.LOOP_MS)
    except KeyboardInterrupt:
        print("  (stopped)")

    if status:
        status.off()

    print("\n  trips per side:")
    for i in range(n):
        print("    %-6s %d" % (P.NAMES[i], dets[i].trips))
    return {P.NAMES[i]: {"threshold_mm": dets[i].thr, "trips": dets[i].trips}
            for i in range(n)}


# ======================================================== mode comparison
def compare_modes(seconds=8):
    """SHORT vs LONG on the same scene. A good figure for the report.

    LONG reaches ~4 m in good conditions. SHORT is ~1.3 m but far more immune
    to ambient light. For a room-scale assistive device that trade is worth
    measuring rather than assuming.
    """
    from vl53l1x import SHORT, LONG
    out = {}
    for label, mode in (("LONG", LONG), ("SHORT", SHORT)):
        print("\n  --- %s mode, %d s, hold the scene still ---" % (label, seconds))
        i2c, sensors = tof3.bring_up(mode=mode, verbose=False)
        vals = [[] for _ in sensors]
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            for i, mm in enumerate(tof3.read_all(sensors)):
                if mm is not None and mm > C.SATURATE_MM:
                    vals[i].append(mm)
            time.sleep_ms(C.LOOP_MS)
        out[label] = {}
        for i in range(len(sensors)):
            st = _stats(vals[i])
            out[label][P.NAMES[i]] = st
            if st:
                print("    %-6s mean %6.0f mm   sd %5.1f   max %5d"
                      % (P.NAMES[i], st["mean"], st["sd"], st["max"]))
            else:
                print("    %-6s no samples" % P.NAMES[i])
        tof3.stop_all(sensors)

    print("\n  Higher max in LONG is expected. If SHORT has a much lower sd,")
    print("  your room is bright and SHORT is the honest choice for GENIE.")
    return out


# ==================================================================== export
def save_results(cal=None, sweeps=None, monitor_result=None, modes=None):
    payload = {
        "version": VERSION,
        "n_sensors": P.N_SENSORS,
        "names": P.NAMES[:P.N_SENSORS],
        "calibration": cal,
        "range_sweeps": sweeps,
        "monitor": monitor_result,
        "mode_comparison": modes,
    }
    try:
        with open(C.RESULT_FILE, "w") as fh:
            json.dump(payload, fh)
        print("  wrote %s" % C.RESULT_FILE)
    except OSError as e:
        print("  could not write JSON: %s" % e)

    # CSV for the report -- one row per sensor, paste straight into a table
    try:
        with open(C.CSV_FILE, "w") as fh:
            fh.write("side,addr,xshut,baseline_mm,noise_sd_mm,"
                     "threshold_mm,min_mm,max_mm,trips\n")
            for i in range(P.N_SENSORS):
                name = P.NAMES[i]
                c = (cal or {}).get(name) or {}
                st = c.get("stats") or {}
                sw = (sweeps or {}).get(name) or {}
                mo = (monitor_result or {}).get(name) or {}
                fh.write("%s,0x%02X,%d,%s,%s,%s,%s,%s,%s\n" % (
                    name, P.ADDRESSES[i], P.XSHUT[i],
                    "%.0f" % st["mean"] if st.get("mean") is not None else "",
                    "%.1f" % st["sd"] if st.get("sd") is not None else "",
                    c.get("threshold_mm", ""),
                    sw.get("min_mm", ""), sw.get("max_mm", ""),
                    mo.get("trips", "")))
        print("  wrote %s" % C.CSV_FILE)
    except OSError as e:
        print("  could not write CSV: %s" % e)


def fetch_help():
    print("\n  To get the results onto your PC:")
    print("    Thonny -> file browser -> MicroPython device")
    print("    right-click %s -> Download to..." % C.CSV_FILE)
    print("    open in Excel, it is already a table")
