# FINAL TESTING OF TOF SENSORS

Final bring-up and fault-isolation bench for the four VL53L1X on Node 2.
Standalone — it does not import `genie_link`, `zones`, `sensors.py`, or any
fingerprint code. Nothing outside this folder is touched.

## Upload

Both files must be **on the board**, in the same directory:

```
tof_final_test.py
vl53l1x_testing.py  (a copy of the driver, renamed only so it cannot
                     collide with the vl53l1x.py already on the board)
```

Thonny: `File > Save as... > MicroPython device` for each, then open
`tof_final_test.py` and press Run.

## Wiring it assumes

| | |
|---|---|
| VIN | **3V3 only** — the ESP32-S3 is not 5 V tolerant |
| SDA / SCL | GPIO8 / GPIO9, shared rail |
| Pull-ups | **ONE** 4.7 kΩ pair for the whole bus |
| XSHUT | front 10 · left 11 · right 12 · rear 13 |
| Addresses | 0x30 · 0x31 · 0x32 · 0x33 |

Wrong? Edit the `CONFIG` block at the top of `tof_final_test.py`. Nothing else
needs changing.

## Menu

| | Test | What it settles |
|---|---|---|
| 1 | Bus scan | is anything on the bus at all |
| 2 | **XSHUT wiring proof** | enables each sensor alone — names the dead wire |
| 3 | Bring-up | assigns 0x30–0x33, one at a time |
| 4 | Identify | model ID 0xEACC, genuine vs clone |
| 5 | Single read | one distance + range status per sensor |
| 6 | Live stream | continuous, Ctrl-C to stop |
| 7 | Stability soak | 60 samples, min/median/max/σ (MAD), dropouts |
| 8 | **Isolation vs combined** | the one for "works alone, breaks together" |
| 9 | Bus stress | 800 reads, counts I²C errors under load |
| 10 | I²C speed sweep | 100 kHz vs 400 kHz |
| 11 | Distance mode A/B | LONG vs SHORT, same scene |
| 12 | Lens obstruction | flags the < 150 mm / near-zero-noise signature |
| 13 | Run all | 1–9 in sequence, one report block |

## Test 2 before test 8

A sensor that is dead in test 2 is dead full stop — power, the XSHUT wire,
SDA/SCL to that board, or the part. It is not an address clash and not
crosstalk, and running test 8 on it wastes the sitting. Dupont wires break
inside the insulation: **replace** the wire, don't re-seat it.

## Reading test 8

Every sensor is measured alone (the other three held in reset), then all four
live. Same scene, nothing moved. It diffs medians, σ, dropouts, **and the
VL53L1X range-status codes** — the chip's own opinion of each reading.

- **status 9, medians shifting > 40 mm, or σ tripling** → optical. The 940 nm
  cones overlap or share a bounce surface. Cheapest fix first: `MODE = SHORT`
  (test 11 A/Bs it), then angle the boards apart, then stop ranging all four at
  once — `start()` / read / `stop()` per sensor — then a baffle.
- **status 4 or 6** → not crosstalk. Target too far, too dark, or an edge. Move
  the target and re-run before touching hardware.
- **I²C timeouts, or a sensor going DEAD only in combination** → electrical.
  Duplicate address, bus loading, or the 3V3 rail sagging with four ranging.
  Test 9 and test 10 separate those.

## Standing facts

Addresses live in sensor **RAM**. Every reset drops all four back to 0x29, so
bring-up runs at the top of every session. That is not a bug.

`distance()` blocks for the ranging budget (~100 ms default). That is why the
ToF sensors live on Node 2 and reach Node 1 as finished numbers.
