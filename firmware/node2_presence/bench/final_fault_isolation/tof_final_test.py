"""GENIE Node 2 -- FINAL ToF test bench.  VL53L1X x4 on one I2C bus.

ESP32-S3 DevKitC-1 / MicroPython / Thonny.  Menu driven.

Self-contained: nothing here imports genie_link, zones, the fingerprint driver
or anything else on the node. It needs only vl53l1x_testing.py, which sits
beside it in this folder. Upload BOTH files to the board and press Run.

    tof_final_test.py       <- run this
    vl53l1x_testing.py      <- renamed copy of the proven driver

WIRING (edit CONFIG below if any of this is wrong)
    VIN   3V3 only. The ESP32-S3 is not 5 V tolerant.
    SDA   GPIO8   shared rail
    SCL   GPIO9   shared rail
    ONE 4.7k pull-up pair for the whole bus, not one pair per breakout.
    XSHUT front 10, left 11, right 12, rear 13   ->  0x30 0x31 0x32 0x33

REV 2 -- changes after the 02-09 bench session
    * only() now forces a real XSHUT low pulse before raising a pin. Without
      it a sensor that was already awake kept its 0x30 address and answered
      ENODEV at 0x29, which read as a dead sensor in test 8 pass 1. That was
      a bug in the bench, not a fault on the board.
    * test 9 no longer counts "not initialised" as an I2C error. It used to
      report 800/800 bus errors when the real number was zero.
    * bring-up is now TWO PHASE with retries: every sensor is addressed
      first, ranging is started only once all of them are addressed. Three
      attempts each, with a full XSHUT power-cycle between attempts.
    * new test 13, cumulative load. Brings sensors up one at a time and
      reads after each, so the count at which the array falls over is
      visible. That is the test that separates a supply problem from a bus
      problem from a bad part.

Addresses live in sensor RAM. Every reset drops all four back to 0x29, so
bring-up runs at the top of every session. That is not a bug to fix.
"""

import time
from machine import I2C, Pin

from vl53l1x_testing import VL53L1X, SHORT, LONG, MODEL_ID

# ==========================================================================
# CONFIG
# ==========================================================================
SDA, SCL = 8, 9
I2C_ID = 0
I2C_FREQ = 400_000

XSHUT = [10, 11, 12, 13]
ADDRESSES = [0x30, 0x31, 0x32, 0x33]
NAMES = ["front", "left", "right", "rear"]
N = 4

MODE = LONG              # LONG ~4 m.  SHORT ~1.3 m, lower VCSEL energy, much
                         # less mutual interference AND less peak current.
                         # Test 11 A/Bs it.

BOOT_MS = 30             # settle after raising XSHUT
RESET_MS = 40            # how long XSHUT is held low for a real reset
RETRIES = 3              # bring-up attempts per sensor
SETTLE_MS = 20           # pause between sensors during bring-up

SOAK_N = 60
XTALK_N = 30
STRESS_LOOPS = 200
LOAD_N = 15              # samples per step in the cumulative load test

XSHUT_OPEN_DRAIN = False

RESULTS = {}


# ==========================================================================
# MicroPython-safe formatting
# ==========================================================================
def lp(s, n):
    s = str(s)
    return s[-n:] if len(s) > n else (" " * (n - len(s))) + s


def rp(s, n):
    s = str(s)
    return s[:n] if len(s) > n else s + (" " * (n - len(s)))


def f1(x):
    return "----" if x is None else "%.1f" % x


def rule(c="-", n=72):
    print(c * n)


def head(t):
    print("")
    rule("=")
    print(t)
    rule("=")


# ==========================================================================
# Bus and XSHUT
# ==========================================================================
_i2c = None
_pins = None


def bus(freq=None):
    global _i2c
    if _i2c is None or freq is not None:
        _i2c = I2C(I2C_ID, sda=Pin(SDA), scl=Pin(SCL), freq=freq or I2C_FREQ)
    return _i2c


def pins():
    global _pins
    if _pins is None:
        if XSHUT_OPEN_DRAIN:
            _pins = [Pin(p, Pin.OPEN_DRAIN, value=0) for p in XSHUT[:N]]
        else:
            _pins = [Pin(p, Pin.OUT, value=0) for p in XSHUT[:N]]
    return _pins


def all_off():
    for p in pins():
        p.value(0)
    time.sleep_ms(RESET_MS)


def only(i):
    """Hold every sensor in reset except i. Forces a real low pulse on i so it
    comes up at 0x29 even if it was already awake at 0x30+."""
    all_off()
    pins()[i].value(1)
    time.sleep_ms(BOOT_MS)


def scan():
    try:
        return bus().scan()
    except Exception as e:
        print("  SCAN FAILED: %s" % e)
        return None


def show(a):
    if a is None:
        return "bus fault"
    return " ".join(["0x%02X" % x for x in a]) if a else "(silent)"


# ==========================================================================
# Bring-up  --  two phase, with retries
# ==========================================================================
SENSORS = [None] * N


def _address_one(i, mode):
    """Wake sensor i (others already in whatever state) and give it its
    address. Does NOT start ranging. Returns a VL53L1X or None."""
    for attempt in range(RETRIES):
        pins()[i].value(0)
        time.sleep_ms(RESET_MS)
        pins()[i].value(1)
        time.sleep_ms(BOOT_MS + attempt * 20)      # back off a little each try
        try:
            s = VL53L1X(bus(), 0x29)
            s.init(mode)
            s.set_address(ADDRESSES[i])
            if ADDRESSES[i] in (scan() or []):
                return s, attempt + 1
        except Exception as e:
            last = e
            continue
    pins()[i].value(0)          # park it so it cannot squat on 0x29
    time.sleep_ms(RESET_MS)
    return None, RETRIES


def bring_up(verbose=True, mode=None, count=None, start=True):
    """Phase 1: address every sensor, ranging OFF.
    Phase 2: start ranging on all of them at once.

    Starting each sensor as soon as it is addressed -- what rev 1 did -- means
    the last sensor has to boot while the earlier ones are already firing
    their VCSELs. On a marginal 3V3 rail that is exactly when bring-up fails.
    """
    global SENSORS
    mode = MODE if mode is None else mode
    n = N if count is None else count
    all_off()

    if verbose:
        pre = scan()
        print("  all XSHUT low: %s" % show(pre))
        if pre and 0x29 in pre:
            print("  !! 0x29 answers with every XSHUT LOW -- an XSHUT wire is")
            print("     not connected. It will collide during assignment.")

    SENSORS = [None] * N
    tries = [0] * N
    for i in range(n):
        s, t = _address_one(i, mode)
        SENSORS[i] = s
        tries[i] = t
        if verbose:
            if s:
                print("  %s -> 0x%02X  ok%s" %
                      (rp(NAMES[i], 6), ADDRESSES[i],
                       "" if t == 1 else "   (took %d attempts)" % t))
            else:
                print("  %s -> FAILED after %d attempts" % (rp(NAMES[i], 6), RETRIES))
        time.sleep_ms(SETTLE_MS)

    if start:
        for i in range(n):
            if SENSORS[i]:
                try:
                    SENSORS[i].start()
                except Exception as e:
                    if verbose:
                        print("  %s start() failed: %s" % (rp(NAMES[i], 6), e))
                    SENSORS[i] = None
        time.sleep_ms(120)

    live = sum([1 for s in SENSORS if s])
    if verbose:
        print("  bus now: %s" % show(scan()))
        print("  %d of %d live" % (live, n))
        if max(tries) > 1:
            print("  note: a sensor that only comes up on the 2nd or 3rd try is")
            print("        a marginal supply, not a broken part. Run test 13.")
        if live < n:
            print("  -> run test 2, then test 13.")
    RESULTS["bringup"] = "%d/%d addressed" % (live, n)
    return live


def ensure():
    if not any(SENSORS):
        print("(bringing up first)")
        bring_up(verbose=False)
    return any(SENSORS)


# ==========================================================================
# Reading
# ==========================================================================
# status codes: 0 valid, >0 chip range status, -1 not initialised,
#               -2 I2C / timeout, -3 other
def read_one(i):
    s = SENSORS[i]
    if s is None:
        return (None, -1, "not initialised")
    try:
        mm, code, text = s.distance_verbose()
    except OSError as e:
        return (None, -2, "i2c/timeout: %s" % e)
    except Exception as e:
        return (None, -3, str(e))
    return (mm if code == 0 else None, code, text)


def read_all():
    return [read_one(i) for i in range(N)]


# ==========================================================================
# Stats
# ==========================================================================
def stats(vals):
    good = [v for v in vals if v is not None]
    n = len(good)
    o = {"n": len(vals), "ok": n, "drop": len(vals) - n,
         "min": None, "max": None, "med": None, "sigma": None}
    if n == 0:
        return o
    s = sorted(good)
    o["min"], o["max"] = s[0], s[-1]
    o["med"] = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    d = sorted([abs(v - o["med"]) for v in s])
    mad = d[n // 2] if n % 2 else (d[n // 2 - 1] + d[n // 2]) / 2
    o["sigma"] = mad * 1.4826
    return o


def tally(codes):
    t = {}
    for c in codes:
        t[c] = t.get(c, 0) + 1
    return t


def tally_str(t, texts):
    parts = []
    for c in sorted(t.keys()):
        if c == 0:
            continue
        parts.append("%dx%s(%s)" % (t[c], c, texts.get(c, "?")[:22]))
    return ", ".join(parts) if parts else "all valid"


def shdr():
    print("  " + rp("sensor", 7) + rp("ok/n", 9) + lp("min", 7) + lp("median", 8) +
          lp("max", 7) + lp("sigma", 8) + "   status codes")


def srow(name, st, tstr):
    return ("  " + rp(name, 7) + rp("%d/%d" % (st["ok"], st["n"]), 9) +
            lp(f1(st["min"]), 7) + lp(f1(st["med"]), 8) + lp(f1(st["max"]), 7) +
            lp(f1(st["sigma"]), 8) + "   " + tstr)


def collect(n, gap=25):
    vals = [[] for _ in range(N)]
    codes = [[] for _ in range(N)]
    texts = [{} for _ in range(N)]
    for _ in range(n):
        r = read_all()
        for i in range(N):
            mm, c, t = r[i]
            vals[i].append(mm)
            codes[i].append(c)
            texts[i][c] = t
        time.sleep_ms(gap)
    return vals, codes, texts


# ==========================================================================
# 1  bus scan
# ==========================================================================
def t_scan():
    head("1  BUS SCAN")
    for p in pins():
        p.value(1)
    time.sleep_ms(BOOT_MS)
    f = scan()
    if f is None:
        print("  Bus jammed. In order of likelihood: a breakout on 5 V; a split")
        print("  breadboard rail fed on one half only; more than one 4.7k pair;")
        print("  a dupont wire broken inside its insulation.")
        RESULTS["scan"] = "BUS FAULT"
        return
    print("  found: %s" % show(f))
    got = [a for a in ADDRESSES[:N] if a in f]
    print("  assigned: %d/%d   %s" % (len(got), N, show(got)))
    if 0x29 in f:
        print("  note: 0x29 present -> at least one sensor is unassigned.")
    RESULTS["scan"] = "%d/%d assigned, %d devices" % (len(got), N, len(f))


# ==========================================================================
# 2  XSHUT wiring proof
# ==========================================================================
def t_xshut():
    head("2  XSHUT WIRING PROOF")
    print("Each sensor enabled alone, from a real reset. A failure here is")
    print("power, the XSHUT wire, SDA/SCL to that board, or the part.")
    print("")
    all_off()
    base = scan()
    print("  all low  -> %s%s" % (show(base), "   OK" if base == [] else ""))
    if base:
        print("  !! something answers with all XSHUT low.")
    live = 0
    for i in range(N):
        only(i)
        f = scan()
        new = [] if f is None else [a for a in f if a not in (base or [])]
        note = ""
        if 0x29 in new:
            try:
                mid = VL53L1X(bus(), 0x29).model_id()
                note = ("  id=0x%04X genuine" % mid) if mid == MODEL_ID else \
                       ("  id=0x%04X  <-- NOT a VL53L1X" % mid)
            except Exception as e:
                note = "  id read failed: %s" % e
        ok = bool(new)
        if ok:
            live += 1
        print("  %s GPIO%s  %s  saw %s%s" %
              (rp(NAMES[i], 6), rp(XSHUT[i], 4), "OK  " if ok else "DEAD",
               show(new), note))
    all_off()
    print("")
    print("  %d/%d respond in isolation." % (live, N))
    if live < N:
        print("  -> Replace the dupont wire on the dead one before anything else.")
    RESULTS["xshut"] = "%d/%d respond alone" % (live, N)
    return live


# ==========================================================================
# 3  bring-up
# ==========================================================================
def t_bringup():
    head("3  BRING-UP  (address all, then start all)")
    bring_up(verbose=True)


# ==========================================================================
# 4  identify
# ==========================================================================
def t_identify():
    head("4  IDENTIFY")
    n = 0
    for i in range(N):
        s = SENSORS[i]
        if s is None:
            print("  %s 0x%02X  not initialised" % (rp(NAMES[i], 6), ADDRESSES[i]))
            continue
        try:
            mid = s.model_id()
        except Exception as e:
            print("  %s 0x%02X  no answer (%s)" % (rp(NAMES[i], 6), s.address, e))
            continue
        good = (mid == MODEL_ID)
        if good:
            n += 1
        print("  %s 0x%02X  id=0x%04X  %s" %
              (rp(NAMES[i], 6), s.address, mid,
               "genuine VL53L1X" if good else "UNKNOWN PART"))
    RESULTS["identify"] = "%d/%d genuine" % (n, N)


# ==========================================================================
# 5  single read
# ==========================================================================
def t_single():
    head("5  SINGLE READ")
    if not ensure():
        return
    r = read_all()
    for i in range(N):
        mm, code, text = r[i]
        print("  %s %s mm   status %s  %s" %
              (rp(NAMES[i], 6), lp(mm if mm is not None else "----", 6),
               lp(code, 3), text))
    RESULTS["single"] = " ".join([str(x[0]) if x[0] is not None else "--" for x in r])


# ==========================================================================
# 6  live stream
# ==========================================================================
def t_stream():
    head("6  LIVE STREAM   (Ctrl-C to stop)")
    if not ensure():
        return
    print("  " + "".join([lp(NAMES[i], 9) for i in range(N)]) + lp("Hz", 8))
    t0 = time.ticks_ms()
    n = 0
    try:
        while True:
            r = read_all()
            n += 1
            el = time.ticks_diff(time.ticks_ms(), t0) / 1000.0
            print("  " + "".join([lp(x[0] if x[0] is not None else "----", 9)
                                  for x in r]) +
                  lp(f1(n / el) if el > 0 else "-", 8))
            time.sleep_ms(50)
    except KeyboardInterrupt:
        print("  stopped after %d frames" % n)


# ==========================================================================
# 7  stability soak
# ==========================================================================
def t_soak():
    head("7  STABILITY SOAK  (%d samples, all four live)" % SOAK_N)
    if not ensure():
        return
    print("  hold the scene still.")
    vals, codes, texts = collect(SOAK_N)
    shdr()
    bad = []
    for i in range(N):
        st = stats(vals[i])
        print(srow(NAMES[i], st, tally_str(tally(codes[i]), texts[i])))
        if st["ok"] == 0:
            bad.append("%s: no valid readings" % NAMES[i])
        elif st["drop"] > st["n"] * 0.1:
            bad.append("%s: %d dropouts" % (NAMES[i], st["drop"]))
        elif st["sigma"] is not None and st["sigma"] > 30:
            bad.append("%s: sigma %s mm" % (NAMES[i], f1(st["sigma"])))
    print("")
    print("  sigma is the MAD estimate. Under ~10 mm on a still target is healthy.")
    print("  Status 2 in bulk means the target is too far or too dark for the")
    print("  mode, NOT a sensor fault -- point it at a wall 30-80 cm away.")
    for b in bad:
        print("  !! " + b)
    RESULTS["soak"] = "clean" if not bad else "; ".join(bad)


# ==========================================================================
# 8  isolation vs combined
# ==========================================================================
def t_crosstalk():
    head("8  ISOLATION vs COMBINED")
    print("  Pass 1: each sensor alone, from a real reset, others held low.")
    print("  Pass 2: all four ranging at once. Do not move anything between.")
    print("")

    alone, a_tal, a_txt = [], [], []
    for i in range(N):
        only(i)
        v, c, txt = [], [], {}
        try:
            s = VL53L1X(bus(), 0x29)
            s.init(MODE)
            s.start()
            for _ in range(XTALK_N):
                try:
                    mm, code, text = s.distance_verbose()
                except Exception as e:
                    mm, code, text = 0, -2, str(e)
                v.append(mm if code == 0 else None)
                c.append(code)
                txt[code] = text
                time.sleep_ms(20)
            s.stop()
        except Exception as e:
            print("  %s could not run alone: %s" % (rp(NAMES[i], 6), e))
        alone.append(stats(v))
        a_tal.append(tally(c))
        a_txt.append(txt)
    all_off()

    bring_up(verbose=False)
    time.sleep_ms(100)
    vals, codes, texts = collect(XTALK_N, 20)
    comb = [stats(vals[i]) for i in range(N)]

    print("  " + rp("sensor", 7) + lp("alone", 8) + lp("together", 10) +
          lp("delta", 8) + lp("sigA", 7) + lp("sigT", 7) + lp("dropA/T", 10))
    flags = []
    for i in range(N):
        a, c = alone[i], comb[i]
        d = None if (a["med"] is None or c["med"] is None) else c["med"] - a["med"]
        print("  " + rp(NAMES[i], 7) + lp(f1(a["med"]), 8) + lp(f1(c["med"]), 10) +
              lp(f1(d), 8) + lp(f1(a["sigma"]), 7) + lp(f1(c["sigma"]), 7) +
              lp("%d/%d" % (a["drop"], c["drop"]), 10))
        ct = tally(codes[i])
        if a_tal[i]:
            print("        alone   : " + tally_str(a_tal[i], a_txt[i]))
        print("        together: " + tally_str(ct, texts[i]))

        if ct.get(-1, 0) >= XTALK_N:
            flags.append("%s: never came up for pass 2 (bring-up, not crosstalk)" % NAMES[i])
            continue
        if a["ok"] > 0 and c["ok"] == 0:
            flags.append("%s: alive alone, DEAD in combination" % NAMES[i])
        elif d is not None and abs(d) > 40:
            flags.append("%s: median moves %s mm when the others run" % (NAMES[i], f1(d)))
        elif (a["sigma"] is not None and c["sigma"] is not None
              and c["sigma"] > a["sigma"] * 3 + 5):
            flags.append("%s: noise triples in combination" % NAMES[i])
        if ct.get(9, 0):
            flags.append("%s: status 9 CROSSTALK FAIL x%d" % (NAMES[i], ct[9]))
        if ct.get(-2, 0):
            flags.append("%s: %d I2C timeouts in combination" % (NAMES[i], ct[-2]))

    print("")
    if not flags:
        print("  VERDICT: no combination effect.")
        RESULTS["crosstalk"] = "no combination effect"
        return
    for f in flags:
        print("  !! " + f)
    print("")
    print("  How to read it")
    print("  - 'never came up for pass 2' is a BRING-UP problem. Go to test 13.")
    print("    Nothing about crosstalk can be concluded from it.")
    print("  - status 9, medians shifting, noise up: optical. Try MODE=SHORT")
    print("    (test 11), angle the boards apart, or range one at a time.")
    print("  - status 2 or 4: target too far / too dark. Not a fault.")
    print("  - I2C timeouts, or DEAD only in combination: electrical. Test 13.")
    RESULTS["crosstalk"] = "; ".join(flags)


# ==========================================================================
# 9  bus stress
# ==========================================================================
def t_stress():
    head("9  BUS STRESS  (%d round-robin cycles)" % STRESS_LOOPS)
    if not ensure():
        return
    i2c_err = [0] * N
    notinit = [0] * N
    invalid = [0] * N
    t0 = time.ticks_ms()
    for _ in range(STRESS_LOOPS):
        for i in range(N):
            _mm, c, _t = read_one(i)
            if c == -1:
                notinit[i] += 1
            elif c < 0:
                i2c_err[i] += 1
            elif c != 0:
                invalid[i] += 1
    el = time.ticks_diff(time.ticks_ms(), t0)
    print("  " + rp("sensor", 7) + lp("i2c errors", 12) + lp("not init", 10) +
          lp("invalid", 9))
    tot = 0
    tested = 0
    for i in range(N):
        tot += i2c_err[i]
        if notinit[i] < STRESS_LOOPS:
            tested += 1
        print("  " + rp(NAMES[i], 7) + lp(i2c_err[i], 12) + lp(notinit[i], 10) +
              lp(invalid[i], 9))
    print("")
    print("  %d sensors actually on the bus. %d ms elapsed." % (tested, el))
    print("  'not init' is a bring-up failure, NOT a bus error -- ignore it here.")
    if tot:
        print("  !! %d real I2C errors. Try test 10 at 100 kHz and check there is" % tot)
        print("     exactly ONE 4.7k pull-up pair on the whole bus.")
    else:
        print("  Bus is CLEAN under load on every sensor that came up.")
    RESULTS["stress"] = "%d real i2c errors, %d sensors on bus" % (tot, tested)


# ==========================================================================
# 10  speed sweep
# ==========================================================================
def t_speed():
    head("10  I2C SPEED SWEEP")
    for f in (100_000, 400_000):
        bus(f)
        time.sleep_ms(50)
        n = bring_up(verbose=False)
        _v, codes, _t = collect(10, 20)
        errs = sum([1 for i in range(N) for c in codes[i] if c == -2])
        print("  %s kHz  ->  %d/%d up, %d i2c errors in 40 reads" %
              (lp(f // 1000, 4), n, N, errs))
    bus(I2C_FREQ)
    bring_up(verbose=False)
    print("  restored %d kHz" % (I2C_FREQ // 1000))


# ==========================================================================
# 11  distance mode A/B
# ==========================================================================
def t_mode_ab():
    head("11  DISTANCE MODE A/B   (LONG vs SHORT)")
    print("  SHORT reaches ~1.3 m but uses less VCSEL energy: less mutual")
    print("  interference AND less peak current. If SHORT comes up 4/4 and")
    print("  LONG does not, that is your answer.")
    for label, m in (("LONG ", LONG), ("SHORT", SHORT)):
        n = bring_up(verbose=False, mode=m)
        time.sleep_ms(100)
        vals, codes, texts = collect(30, 20)
        print("")
        print("  --- %s --- %d/%d came up" % (label, n, N))
        shdr()
        for i in range(N):
            print(srow(NAMES[i], stats(vals[i]),
                       tally_str(tally(codes[i]), texts[i])))
    bring_up(verbose=False, mode=MODE)


# ==========================================================================
# 12  lens obstruction
# ==========================================================================
def t_lens():
    head("12  LENS OBSTRUCTION CHECK")
    print("  Point every sensor at open space, more than 1 m clear.")
    try:
        input("  press Enter> ")
    except Exception:
        pass
    if not ensure():
        return
    vals, codes, texts = collect(30, 25)
    shdr()
    flags = []
    for i in range(N):
        st = stats(vals[i])
        print(srow(NAMES[i], st, tally_str(tally(codes[i]), texts[i])))
        if st["med"] is not None and st["med"] < 150 and (st["sigma"] or 0) < 5:
            flags.append("%s: %s mm with almost no noise -> lens obstructed" %
                         (NAMES[i], f1(st["med"])))
    print("")
    if flags:
        for f in flags:
            print("  !! " + f)
        print("  Nothing goes in front of a ToF lens.")
    else:
        print("  no obstruction signature.")
    RESULTS["lens"] = "clear" if not flags else "; ".join(flags)


# ==========================================================================
# 13  CUMULATIVE LOAD  --  the decisive test
# ==========================================================================
def t_load():
    head("13  CUMULATIVE LOAD  (1 -> 4 sensors)")
    print("  Brings up 1 sensor, reads it, then 2, then 3, then 4 -- each time")
    print("  from a clean reset. If bring-up is solid at 1 and 2 and falls over")
    print("  at 3 or 4, the sensors are fine and the 3V3 rail is not.")
    print("")
    print("  " + rp("sensors up", 12) + rp("addressed", 11) + "valid reads per sensor")
    first_fail = None
    for k in range(1, N + 1):
        live = bring_up(verbose=False, count=k)
        vals, codes, _t = collect(LOAD_N, 20)
        oks = []
        for i in range(k):
            oks.append(stats(vals[i])["ok"])
        errs = sum([1 for i in range(k) for c in codes[i] if c == -2])
        print("  " + rp(k, 12) + rp("%d/%d" % (live, k), 11) +
              " ".join([("%s:%d/%d" % (NAMES[i].strip(), oks[i], LOAD_N))
                        for i in range(k)]) +
              ("   %d i2c err" % errs if errs else ""))
        if live < k and first_fail is None:
            first_fail = k
    print("")
    if first_fail is None:
        print("  All four come up. If the array still misbehaves it is optical,")
        print("  not supply -- go to test 8 and test 11.")
        RESULTS["load"] = "4/4 under full load"
    else:
        print("  !! First failure at %d sensors. Below that it is solid." % first_fail)
        print("")
        print("  That is a POWER problem, not a sensor problem. In order:")
        print("   1. 100uF electrolytic + 100nF ceramic across 3V3/GND right at")
        print("      the sensor cluster, not at the ESP32 end of the wires.")
        print("   2. Feed the sensors from a separate 3V3 supply sharing GND,")
        print("      not the DevKitC's on-board LDO.")
        print("   3. MODE = SHORT. Lower VCSEL energy, lower peak current.")
        print("   4. Shorter, thicker power wires. Dupont at 20 cm has real")
        print("      resistance and real inductance at VCSEL pulse edges.")
        RESULTS["load"] = "first failure at %d sensors" % first_fail


# ==========================================================================
# 14  run all
# ==========================================================================
def t_all():
    RESULTS.clear()
    t_scan()
    t_xshut()
    t_bringup()
    t_identify()
    t_single()
    t_soak()
    t_load()
    t_crosstalk()
    t_stress()
    head("REPORT")
    for k in ("scan", "xshut", "bringup", "identify", "single",
              "soak", "load", "crosstalk", "stress"):
        if k in RESULTS:
            print("  " + rp(k, 11) + str(RESULTS[k]))
    rule()
    print("  Addresses are RAM-only. The next reset drops all four to 0x29.")


# ==========================================================================
# menu
# ==========================================================================
MENU = (
    ("1", "Bus scan", t_scan),
    ("2", "XSHUT wiring proof   (find the dead one)", t_xshut),
    ("3", "Bring-up: address all, then start all", t_bringup),
    ("4", "Identify (model ID)", t_identify),
    ("5", "Single read, all four", t_single),
    ("6", "Live stream", t_stream),
    ("7", "Stability soak", t_soak),
    ("8", "Isolation vs combined   (crosstalk)", t_crosstalk),
    ("9", "Bus stress under load", t_stress),
    ("10", "I2C speed sweep  100k / 400k", t_speed),
    ("11", "Distance mode A/B  LONG vs SHORT", t_mode_ab),
    ("12", "Lens obstruction check", t_lens),
    ("13", "CUMULATIVE LOAD 1->4   (supply vs sensor)", t_load),
    ("14", "RUN ALL -> report", t_all),
)


def menu():
    while True:
        print("")
        rule("=")
        print("GENIE Node 2 -- FINAL ToF test bench   rev 2")
        print("SDA%d SCL%d   XSHUT %s   ->   %s" %
              (SDA, SCL, ",".join([str(x) for x in XSHUT[:N]]),
               " ".join(["0x%02X" % a for a in ADDRESSES[:N]])))
        rule("=")
        for k, t, _f in MENU:
            print("  " + lp(k, 2) + "  " + t)
        print("   0  exit")
        try:
            c = input("select> ").strip()
        except KeyboardInterrupt:
            c = "0"
        if c == "0":
            print("bye.")
            return
        hit = False
        for k, _t, f in MENU:
            if c == k:
                hit = True
                try:
                    f()
                except KeyboardInterrupt:
                    print("\n  interrupted")
                except Exception as e:
                    print("  ERROR: %s" % e)
                break
        if not hit:
            print("  ?")


def main():
    print("")
    print("GENIE ToF final test bench -- rev 2")
    print("VIN must be 3V3. The ESP32-S3 is not 5 V tolerant.")
    bus()
    pins()
    menu()


if __name__ == "__main__":
    main()
