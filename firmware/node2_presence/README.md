# Node 2 — presence array

A second ESP32-S3 carrying four VL53L1X time-of-flight sensors (front, left, right, rear) and vibration switches for knock input. MicroPython. It runs no models and reads nothing that Node 1 reads.

It exists because a ranging call blocks for about 100 ms, and Node 1's display loop has 33 ms per frame. The sensors live here and reach Node 1 as finished numbers.

> **State.** Each sensor works alone. The four together fail bring-up non-deterministically, and the array is not in the demonstration unit. The firmware below is complete; comments inside the files refer to folder names from the working tree it came from. Read [the fault record](../../docs/fault-records/tof-array-bringup.md) before trusting or changing any of it.

## Layout

| Folder | Contents |
|---|---|
| `upload/` | The running modules |
| `calibration/` | Baseline, noise estimate, thresholds, hysteresis and drift — with the method written up |
| `bench/` | Per-stage bench tools: bus scan, single sensor, multi-sensor, knock patterns |
| `bench/final_fault_isolation/` | The thirteen-test instrument written to isolate the bring-up fault |

### `upload/`

| File | Role |
|---|---|
| `main.py` | Autostart. Three-second grace period, one attempt, then stop with the traceback. Names any module missing from the board |
| `node2_main.py` | Bring-up, per-sensor calibration, detection loop, ESP-NOW transmit |
| `vl53l1x.py` | Compact VL53L1X driver: init, model-ID check, address reassignment, distance mode, ranging |
| `zones.py` | Distance-to-zone classification with hysteresis |
| `pins3.py`, `tof3.py` | Pin map and array helpers. `bench/tof_bench.py` and `bench/run_tof_test.py` import `tof3` |

`genie_link.py` and `net_uplink.py` from [`../link/`](../link/) are uploaded alongside these, together with a `wifi_cfg.py` made from `../link/wifi_cfg.example.py`. Nine files on the device in all.

The board as it was read back on 2 September 2026 differed from this set in two ways, both left over from fault isolation: the read loop in `node2_main.py` printed which sensor had failed, and `tof3.py` had been replaced by a self-contained bring-up script. That script is kept as [`bench/tof_bringup_standalone.py`](bench/tof_bringup_standalone.py).

## What it does on every boot

1. Holds all four sensors in reset, then releases them one at a time and moves each from the factory address `0x29` to `0x30`–`0x33`. Those addresses live in sensor RAM, so this happens on every boot, forever.
2. Takes a baseline per sensor and derives a detection margin from that sensor's own noise.
3. Ranges at 10 Hz. A trigger transition or a knock is sent immediately; otherwise a heartbeat goes out once a second so Node 1 can tell quiet from dead.

Readings leave two ways at once: ESP-NOW to Node 1, and TCP directly to the host. The second path keeps the array reporting while the face board is off, crashed or being reflashed. Both boards join the same access point, which is also what keeps them on one radio channel.

## Calibration in one paragraph

Eighty samples per sensor of the empty scene. The **median** is the baseline and the **median absolute deviation × 1.4826** is a robust estimate of the noise — a single wild reading moves neither, where it would wreck a mean and a standard deviation. The trigger margin is `max(6σ, 80 mm)`. Entering detection needs `baseline − margin`; leaving needs the object to retreat past `baseline − 0.6 × margin`; either change needs two consecutive frames. While clear, the baseline creeps toward the current reading at 2 % per frame so a chair moved for good becomes the new normal — and it cannot creep while detecting, so a person standing still is not absorbed.

Detail: [`calibration/README.md`](calibration/README.md).

## Known issues in this code

Left as found, and listed so nobody trips on them.

- **Two copies of the pin map.** `node2_main.py` declares its own pins and does not import `pins3.py`. They agree; nothing enforces it.
- **Three sets of zone bands.** The bench tools use room-scale bands (100 / 500 / 1500 / 3000 mm); `zones.py` and Node 1's link use desk-scale ones (40 / 300 / 800 / 1500 mm). In the production path a person two metres away triggers correctly and is then labelled `CLEAR`. Make the band sets agree; do not widen one alone.
- **Fingerprint constants in `pins3.py`** are marked dead in the file itself. See [the fingerprint record](../../docs/fault-records/r307s-fingerprint.md).
- **Bus speed.** The firmware runs I²C at 100 kHz for a recorded reason. The final bench defaults to 400 kHz; set it to 100 kHz before reading anything into its results.

## Wiring

| Signal | GPIO |
|---|---|
| I²C SDA / SCL | 8 / 9 — one 4.7 kΩ pull-up pair for the whole bus |
| XSHUT front / left / right / rear | 10 / 11 / 12 / 13 |
| Vibration switches | 14, 15, 21, 47 |
| Sensor supply | 3V3 only |

Nothing goes in front of a lens: not tape, not clear acrylic, not the film the module ships with.
