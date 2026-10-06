# VL53L1X time-of-flight ×4

MicroPython on ESP32-S3. Four sensors on one I2C bus.

## Wiring

| Sensor pin | Goes to | Note |
|---|---|---|
| VIN | **3V3** | these are 2.8 V parts with an on-board LDO. Check your board has one before considering 5 V |
| GND | GND | shared with ESP32 |
| SDA | GPIO8 | all four in parallel |
| SCL | GPIO9 | all four in parallel |
| XSHUT | GPIO10 / 11 / 12 / 13 | **one GPIO each — this is not optional** |

Pull-ups: **4.7 kΩ SDA→3V3 and SCL→3V3, one pair for the whole bus.** Many
breakout boards ship with their own pull-ups fitted; four boards' worth in
parallel makes the bus too stiff to pull low. If the scan finds nothing with
four connected but works with one, that's the cause — desolder the pull-ups on
three of the boards.

## The address problem

Every VL53L1X ships at **0x29**. Four on one bus all answer simultaneously and
the bus returns garbage. No driver fixes this.

`tof_array.bring_up()` solves it with XSHUT:

1. Drive all four XSHUT low — every sensor held in reset
2. Raise XSHUT #1 → it wakes at 0x29 → reassign to 0x30
3. Raise #2 → wakes at 0x29 (now free) → 0x31
4. #3 → 0x32, #4 → 0x33

**The reassigned addresses are volatile.** They live in RAM. Every reset and
every power cycle drops them back to 0x29. `bring_up()` must run at the top of
`main.py` on every single boot. This is the most common way this build fails.

## Files

| File | Runs on | Purpose |
|---|---|---|
| `i2c_scan.py` | ESP32 | Run first. Finds the bus, IDs each chip, tests each XSHUT wire |
| `vl53l1x.py` | ESP32 | Driver. **Must be uploaded to the board** |
| `tof_array.py` | ESP32 | Address assignment + 4-sensor read loop |

## Order of operations

1. Wire **one** sensor only. Run `i2c_scan.py` → expect `0x29`, model ID `0xEACC`.
2. Wire the other three plus all four XSHUT lines. Run `i2c_scan.py` again —
   the XSHUT section must report "controls a sensor" for all four.
3. Upload `vl53l1x.py` to the board.
4. Run `tof_array.py` → expect four addresses assigned, then live distances.
   Wave your hand in front of each in turn to confirm which name maps to which
   physical sensor, then edit `NAMES`.

## Distance modes

| Mode | Range | Use when |
|---|---|---|
| `SHORT` | ~1.3 m | Bright ambient light, close targets. Much better immunity to sunlight |
| `LONG` | ~4 m | Default here. Room-scale sensing |

Timing budget is left at the ~100 ms default, so you get about 10 Hz per sensor.
Reading four sequentially costs ~40 ms if all have fresh data. If you need
faster later, timing budget is the thing to add to the driver — it isn't
implemented.

## Reading the status codes

`distance()` returns `None` for anything untrustworthy. Use `distance_verbose()`
during bring-up — it returns `(mm, code, text)` and tells you *why*:

| Text | Usually means |
|---|---|
| `valid` | Trust it |
| `signal too weak` | Target too far, too dark, or angled away |
| `sigma too high` | Noisy — target edge, or two surfaces in the cone |
| `out of bounds - phase wrapped` | Beyond max range; the mm value is meaningless |
| `wrapped target` | Ambiguous distance, common past 4 m in LONG mode |

A matte black surface at 2 m reads far worse than white card at 3 m. Test
against the actual surfaces GENIE will face.

## Symptoms → causes

| Symptom | Cause |
|---|---|
| `i2c_scan` finds nothing | Pull-ups missing, or XSHUT held low, or VIN not on 3V3 |
| Works with one sensor, fails with four | Too many pull-ups in parallel — remove three boards' worth |
| Only 0x29 present after `bring_up()` | XSHUT wires not actually connected; run the XSHUT check in `i2c_scan.py` |
| Addresses work, then all gone after reset | Expected. `bring_up()` must run every boot |
| `not a VL53L1X (model ID 0xEEAA)` | That board is a VL53L0X. Different driver |
| One sensor reads, three return None | Those three failed init — check the bring-up print output |
| Readings jump around wildly | Two sensors' cones overlapping and interfering. Stagger reads or angle them apart |

## Note on crosstalk

Four ToF sensors firing into overlapping fields will interfere — each sees the
others' IR pulses. If you mount them close and pointing the same way, expect
noise. Either angle them apart, or read them one at a time with `stop()` on the
others. The current `read_all()` reads sequentially but leaves all four ranging,
which is fine for well-separated mounting and not fine for a tight cluster.
