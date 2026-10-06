# GENIE Node 2 — ToF calibration

Goal of this stage: 4× VL53L1X learn the static environment, then a red blink
when something intrudes and green when clear. Nothing else. TFT, power saving,
camera and servo are later stages.

---

## Files

| File | Action | Needs on board |
|---|---|---|
| `LED_TEST.py` | **F5** — only if the LED misbehaves | nothing |
| `QUICK_CHECK.py` | **F5** — start here | `vl53l1x.py` |
| `CALIBRATE_AND_DETECT.py` | **F5** — the real thing | `vl53l1x.py` |

`vl53l1x.py` stays the only upload. Everything else is inlined, same convention
as the bench scripts.

**Run `QUICK_CHECK.py` first.** No menu, no saved state: bring up → 3 s baseline
→ live loop. Wave your hand, watch the onboard LED go red. It answers one
question only — *is the wiring, driver, LED and detection logic alive?* Once it
passes, move to `CALIBRATE_AND_DETECT.py` for the robust version (MAD noise,
per-sensor thresholds, hysteresis, drift, saved baseline).

Set `N_SENSORS` in `QUICK_CHECK.py` to how many are physically wired. It uses
the **first N** entries, so `2` means XSHUT GPIO10 and GPIO11 — not any other pair.

---

## Before the first run

1. **Check `LED_PIN`.** Set to `38` (DevKitC-1 v1.1). If the LED never lights,
   change to `48` (v1.0). Nothing else in the script depends on it.
2. **Sanity-check the units.** Hold a book at a measured 200 mm. Your
   `vl53l1x.py` returns millimetres, so expect ~200.
3. **`DIST_MODE = SHORT`** by default (~1.3 m, far better ambient-light
   immunity). Switch to `LONG` only if you need to see past 1.3 m — it is
   noticeably noisier under room lighting and useless in sunlight.

Both scripts drive the driver correctly for you: construct at `0x29` →
`set_address()` → `init(DIST_MODE)` → `start()`. `distance()` returns `None`
when the range status is bad, and both scripts treat that as "no reading"
rather than as distance zero. Do not "simplify" that away.

---

## LED

Both sensor scripts run a **RED → GREEN → BLUE self-test at startup**. Watch
the board, not the console. This exists because
`neopixel.NeoPixel(Pin(38), 1)` **never raises on a wrong pin** — WS2812 has no
acknowledgement, so writing into empty air succeeds silently. A wrong
`LED_PIN` produces no error and no light, and everything else still looks
perfectly healthy.

| Setting | Meaning |
|---|---|
| `LED_MODE` | `"neo"` onboard WS2812 · `"pins"` two plain LEDs · `"none"` console only |
| `LED_PIN` | 38 on DevKitC-1 **v1.1**, 48 on **v1.0**. Clones: 47 / 21 / 45. |
| `SWAP_RG` | `True` if your clone is RGB-ordered instead of GRB |
| `BLINK_RED` | `False` = solid red on detect. `True` = blink at `BLINK_MS`. |
| `RED_PIN` / `GREEN_PIN` | 14 and 21 for `"pins"` mode. **Not GPIO5** — the WS2812 stick owns it. |

Colour writes are cached, so the LED is only updated when the state actually
changes rather than every 20 ms loop.

### If the onboard LED will not change colour

1. **Power-cycle the board and run nothing.** WS2812s latch their last colour
   until new data or loss of power — a soft reset does not clear them. If the
   LED stays lit with no script running, that light is the board's power LED or
   a stale latch, not your code. That means the pin is wrong.
2. **Read the silkscreen** on the underside for `v1.0` / `v1.1`.
3. **Run `LED_TEST.py` option 1** — it sweeps 38 / 48 / 47 / 21 / 45.
4. If no pin lights at all, the WS2812 is unpopulated. Common on clones.
   Switch to `LED_MODE = "pins"`.

Not a cause, so do not chase them: the `neopixel` module (proved working by
`bench/neo_test.py`), bitstream timing, GPIO38 vs PSRAM (octal
PSRAM is 33–37, 38 is clear), and LED power gating (there is none on this
board).

---

## Menu

| # | Does |
|---|---|
| 1 | Pull-down wiring test only. Expect `1 1`. |
| 2 | Bring-up: XSHUT sequence, readdress to `0x30–0x33`. **Must run every boot.** |
| 3 | Calibrate. 5 s countdown, then 80 samples/sensor. Saves to flash. |
| 4 | Live detection from the saved baseline. |
| 5 | Print the saved baseline. |
| 6 | 2 → 3 → 4 in one go. **This is the normal run.** |

Ctrl-C leaves detection and returns to the menu.

---

## How calibration works

Per sensor, 80 samples of the empty environment:

- **median** → baseline (robust; a mean gets destroyed by ToF outliers)
- **MAD × 1.4826** → noise sigma (robust standard deviation)
- **margin** = `max(6σ, 80 mm)` → trigger at `baseline − margin`

Two modes are picked automatically:

- **WALL** — a surface is in view (a real wall, a table, GENIE's own body).
  Trigger when a reading comes in closer than `baseline − margin`.
- **OPEN** — fewer than half the samples were valid, i.e. nothing in range.
  Trigger on any valid reading closer than `OPEN_TRIGGER` (1200 mm).

Because noise is measured per sensor at its own baseline, the threshold is
automatically tighter for a near wall and looser for a far one. That is the
whole point of doing it this way instead of one global number.

**Hysteresis + debounce:** entering DETECT needs `baseline − margin`, leaving it
needs the object to retreat past `baseline − 0.6×margin`, and either change
needs 2 consecutive frames. Without both, the LED strobes at the boundary.

**Drift:** while a sensor is CLEAR, its baseline creeps toward the current
reading at 2% per frame. A chair moved permanently becomes the new normal in a
few seconds instead of latching red forever. It cannot creep while detecting,
so a person standing still does not get absorbed.

---

## Tuning

| Constant | Raise it if | Lower it if |
|---|---|---|
| `K_SIGMA` (6.0) | false triggers on a noisy sensor | it misses slow/soft approaches |
| `MIN_MARGIN_MM` (80) | jittery near a close wall | you need sub-8 cm sensitivity |
| `N_CONSEC` (2) | LED flickers | detection feels laggy |
| `OPEN_TRIGGER` (1200) | you want a wider bubble | it trips on distant passers-by |
| `DRIFT_ALPHA` (0.02) | environment changes often | objects get absorbed too fast |
| `I2C_FREQ` | — | drop to `100000` if the bus is flaky |

---

## Warnings the script will raise

**`Lens is almost certainly obstructed`** — baseline under 150 mm with near-zero
noise. A ToF cannot see through clear acrylic, tape or a window. Cut a hole.
This is the single most likely thing to break the enclosure build.

**`N% dropped reads`** — under 70% valid samples. Direct sunlight, a glossy or
matte-black target, or a marginal I2C bus. Re-calibrate in the lighting the
demo will actually happen in.

**`bus not silent with all XSHUT low`** — an XSHUT wire is not connected. Fix
before trusting any address assignment.

---

## Gate before moving on

Do not advance to the ESP-NOW stage until all of this holds:

- [ ] Option 6 completes clean from a **cold boot** (unplug/replug, not Ctrl-D), 3× in a row
- [ ] All four sensors report `WALL` or `OPEN` deliberately — no surprises
- [ ] Yield ≥ 90% on every sensor
- [ ] Walking into each of the four sides individually turns red, and only that sensor shows `#`
- [ ] Standing still 60 s in front stays red (drift does not absorb a person)
- [ ] Empty room 5 min stays green with zero false triggers
- [ ] Baseline survives a reboot (option 5 after a power cycle)

The 5-minute false-trigger test is the one people skip and the one that
embarrasses you in the demo.
