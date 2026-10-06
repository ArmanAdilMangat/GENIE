"""GENIE Node 2 -- config for the mounted 4x ToF range test.

MODULE. Upload to the board.

Pin numbers, sensor names and addresses are NOT here -- they live in pins3.py,
which is already on the board. One source of truth. This file only holds the
knobs that are specific to *testing*, so tuning a threshold never risks
touching a pin map that is already proven.
"""

VERSION = "tof_test_cfg 1.0  2026-08-15"

# ------------------------------------------------------------ calibration
CAL_SECONDS = 5           # how long to watch a still scene to learn baseline
CAL_DISCARD_MS = 500      # ignore the first half second; the first samples
                          # after start() are frequently rubbish

# ------------------------------------------------------------- thresholds
#
# A sensor facing a wall 1.2 m away and a sensor facing an open corridor need
# different thresholds. So the threshold is DERIVED per sensor at calibration:
#
#     threshold = baseline_mean - MARGIN_MM
#
# clamped into [MIN_THRESHOLD_MM, MAX_THRESHOLD_MM]. If the sensor sees
# nothing at rest (open space, out of range) the baseline is meaningless and
# we fall back to DEFAULT_THRESHOLD_MM.
#
MARGIN_MM           = 150   # how far inside the baseline counts as "something"
MIN_THRESHOLD_MM    = 100   # never trigger closer than 10 cm
MAX_THRESHOLD_MM    = 1200  # never treat beyond 1.2 m as an obstacle
DEFAULT_THRESHOLD_MM = 800  # used when the sensor sees open space at rest

# Hysteresis stops the LED strobing when someone stands exactly on the line.
# Trigger below threshold; only release once you are threshold + HYST away.
HYST_MM   = 60
CONFIRM_N = 2             # consecutive agreeing samples before a state change

# ------------------------------------------------------------- range sweep
SWEEP_SECONDS = 25        # per sensor, guided by the operator
SATURATE_MM   = 40        # below this the chip saturates and reports nonsense

# ------------------------------------------------------------------- LED
#
# ESP32-S3-DevKitC-1 has ONE onboard addressable RGB LED, but which pin it is
# on depends on the board revision:
#       v1.0 -> GPIO48
#       v1.1 -> GPIO38
# Menu option 1 tries both so you can see which one lights up. Set RGB_PIN to
# whichever works and stop guessing.
#
# NOTE: GPIO38 is earmarked for SIM TX later. Not a conflict today (the SIM is
# not wired) but when it goes in, either move the SIM to GPIO41 or drive the
# external strip on GPIO5 instead.
#
RGB_PIN     = 38
RGB_ALT_PIN = 48
RGB_COUNT   = 1

# External WS2812 stick, if you would rather have one pixel per sensor.
# Set USE_STRIP = True and you get front/left/right/rear as four pixels.
USE_STRIP    = False
STRIP_PIN    = 5
STRIP_COUNT  = 8

# WS2812s are blindingly bright and 8 at full white is ~480 mA -- more than the
# sensors and the ESP32 combined. This is a status indicator, not a lamp.
BRIGHTNESS = 40           # 0-255

COLOUR_CLEAR    = (0, 1, 0)     # green  -- scaled by BRIGHTNESS
COLOUR_DETECT   = (1, 0, 0)     # red    -- something in front
COLOUR_CAL      = (0, 0, 1)     # blue   -- calibrating, hold still
COLOUR_FAULT    = (1, 0, 1)     # purple -- sensor did not come up

# ------------------------------------------------------------------ timing
MONITOR_SECONDS = 120     # default length of the live detection run
LOOP_MS         = 20
PRINT_MS        = 300

# ------------------------------------------------------------------- files
CAL_FILE    = "/tof_cal.json"          # survives reset; reload instead of recal
RESULT_FILE = "/tof_test_results.json"
CSV_FILE    = "/tof_test_results.csv"  # paste straight into the report
