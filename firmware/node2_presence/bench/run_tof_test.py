"""GENIE Node 2 -- mounted 4x ToF characterisation test.

SCRIPT. Do not upload -- open in Thonny and press F5.

UPLOAD TO THE BOARD:
    tof_test_cfg.py   tof_bench.py
    (pins3.py, tof3.py, vl53l1x.py, zones.py are already there from 07)

WHAT THIS IS FOR
    07 proved the sensors are wired correctly. This measures what they can
    actually SEE once taped to GENIE's body -- which is a different question,
    and the one the report needs numbers for.

RUN IN THIS ORDER
    1  find the LED pin          (once, then set RGB_PIN in the config)
    2  bring up the array        (after every reset -- addresses are volatile)
    3  calibrate                 (learns each side's resting view)
    4  range sweep               (real min/max per side, not datasheet numbers)
    5  live detection            (red/green -- the demo AND the acceptance test)
    6  SHORT vs LONG             (optional, good figure for the report)
    7  save results              (JSON + CSV)
"""

import time

import pins3 as P
import tof3
import tof_bench as B
import tof_test_cfg as C


STATE = {"i2c": None, "sensors": None, "status": None,
         "cal": None, "sweeps": {}, "monitor": None, "modes": None}


def _ask(prompt):
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return None


def get_status():
    if STATE["status"] is None:
        STATE["status"] = B.Status()
    return STATE["status"]


def need_sensors():
    if STATE["sensors"] is None or not any(STATE["sensors"]):
        print("\n  bring up the array first (option 2)")
        return None
    return STATE["sensors"]


def do_bring_up():
    print("\n--- bring up ----------------------------------------------")
    i2c, sensors = tof3.bring_up(verbose=True)
    STATE["i2c"], STATE["sensors"] = i2c, sensors
    alive = sum(1 for s in sensors if s)
    st = get_status()
    if alive == P.N_SENSORS:
        st.all(C.COLOUR_CLEAR)
        time.sleep(1)
        st.off()
    elif alive:
        st.all(C.COLOUR_FAULT)
        time.sleep(1)
        st.off()
    return sensors


def do_calibrate():
    s = need_sensors()
    if not s:
        return
    STATE["cal"] = B.calibrate(s, status=get_status())


def do_sweep():
    s = need_sensors()
    if not s:
        return
    print("\n  which side?")
    for i in range(P.N_SENSORS):
        print("    %d  %s" % (i + 1, P.NAMES[i]))
    print("    a  all of them, one after another")
    c = _ask("  select: ")
    if c is None:
        return
    if c.lower() == "a":
        idxs = range(P.N_SENSORS)
    else:
        try:
            idxs = [int(c) - 1]
        except ValueError:
            print("  '%s'?" % c)
            return
    for i in idxs:
        if i < 0 or i >= P.N_SENSORS:
            continue
        r = B.range_sweep(s, i)
        if r:
            STATE["sweeps"][P.NAMES[i]] = r
        if len(list(idxs)) > 1:
            print("\n  move to the next side...")
            time.sleep(3)


def do_monitor():
    s = need_sensors()
    if not s:
        return
    cal = STATE["cal"] or B.load_cal()
    if not cal:
        print("\n  no calibration found -- running one first")
        cal = B.calibrate(s, status=get_status())
        STATE["cal"] = cal
    STATE["monitor"] = B.monitor(s, cal, status=get_status())


def show_thresholds():
    cal = STATE["cal"] or B.load_cal()
    if not cal:
        print("\n  no calibration yet (option 3)")
        return
    print("\n  side    baseline   noise    threshold   sees")
    print("  " + "-" * 66)
    for i in range(P.N_SENSORS):
        c = cal.get(P.NAMES[i])
        if not c:
            continue
        st = c.get("stats") or {}
        print("  %-6s %8s %7s %10d   %s" % (
            P.NAMES[i],
            "%.0f mm" % st["mean"] if st.get("mean") is not None else "-",
            "%.1f" % st["sd"] if st.get("sd") is not None else "-",
            c["threshold_mm"],
            B._verdict(st if st else None)))
    print("\n  To change one by hand: edit MARGIN_MM or DEFAULT_THRESHOLD_MM")
    print("  in tof_test_cfg.py, re-upload it, and recalibrate.")


MENU = """
============================================================
 GENIE NODE 2 -- MOUNTED ToF ARRAY TEST  (%d sensors)
============================================================
  1  find the LED pin      (GPIO38 vs GPIO48, run once)
  2  bring up array        (after EVERY reset)
  ---
  3  calibrate + analyse surroundings
  4  range sweep           (real min/max per side)
  5  LIVE detection        (red / green, hysteresis)
  ---
  6  show thresholds
  7  SHORT vs LONG comparison
  8  save results (JSON + CSV)
  9  how to get files off the board
  0  quit
------------------------------------------------------------""" % P.N_SENSORS


def main():
    print("\n" + "=" * 60)
    print(" MOUNTED ToF ARRAY TEST")
    print("=" * 60)
    tof3.manifest()
    print("    %-10s %s" % ("tof_bench", B.VERSION))
    print("    %-10s %s" % ("cfg", C.VERSION))

    while True:
        print(MENU)
        c = _ask("  select: ")
        if c is None or c == "0":
            if STATE["status"]:
                STATE["status"].off()
            tof3.stop_all(STATE["sensors"] or [])
            print("bye")
            return
        if c == "1":
            B.find_led_pin()
        elif c == "2":
            do_bring_up()
        elif c == "3":
            do_calibrate()
        elif c == "4":
            do_sweep()
        elif c == "5":
            do_monitor()
        elif c == "6":
            show_thresholds()
        elif c == "7":
            STATE["modes"] = B.compare_modes()
            STATE["sensors"] = None        # compare_modes re-ran bring_up
            print("\n  re-run option 2 before the live test")
        elif c == "8":
            B.save_results(STATE["cal"], STATE["sweeps"],
                           STATE["monitor"], STATE["modes"])
        elif c == "9":
            B.fetch_help()
        else:
            print("  '%s'? pick 0-9." % c)


if __name__ == "__main__":
    main()
