# Protocol

Two links with two different transports. Confusing them is the main reason this part looks harder than it is.

```
Node 2  ── ESP-NOW, 14-byte binary frame ──▶  Node 1  ── JSON lines, USB serial ──▶  Host
presence array                                face + safety sensors                  speech pipeline
```

This page is the sensor-side contract as written in late August 2026. [`firmware/link/genie_link.py`](../firmware/link/genie_link.py) is the executable definition of the first link, and [`host/Services/genie_serial.py`](../host/Services/genie_serial.py) is the runnable reader for the second. The integrated build adds self-check flags and state strings to the telemetry (`gas_level`, `gas_ok`, `flame_ok`, `fall_state`, `knock_count`); those are emitted by `firmware/node1_face/upload/node1_report.py` and translated by `host/Services/node_bridge.py`.

**The rule that keeps this working:** whoever changes a field changes this document in the same commit. If it is not here, the other side is not required to handle it.

---

## Link 1 — Node 2 → Node 1, ESP-NOW

### Frame v2, 14 bytes

```python
FMT  = "<BBBBHHHHBB"
SIZE = struct.calcsize(FMT)        # 14 — derived. Change FMT and SIZE follows.
```

| Offset | Field | Type | Meaning |
|---|---|---|---|
| 0 | `ver` | uint8 | `2`. A mismatched version is dropped, not misparsed |
| 1 | `type` | uint8 | `0x01` telemetry · `0x02` event (sent immediately) |
| 2 | `seq` | uint8 | Wraps at 256; gaps mean lost frames |
| 3 | `flags` | uint8 | bit 0 calibrated · bit 1 tof_fault · bit 2 knock |
| 4 | `tof[0]` | uint16 | **front**, mm. `0xFFFF` = no valid reading |
| 6 | `tof[1]` | uint16 | **left** |
| 8 | `tof[2]` | uint16 | **right** |
| 10 | `tof[3]` | uint16 | **rear** |
| 12 | `tof_hit` | uint8 | Bitmask: bit N set = sensor N currently triggered |
| 13 | `vib_mask` | uint8 | Bitmask of vibration switches active |

Sensor order is the XSHUT order, GPIO 10, 11, 12, 13.

The one file is uploaded to **both** boards. A copy on one board only is how two definitions drift apart. Running it on a desktop round-trips a frame and asserts:

```bash
python3 firmware/link/genie_link.py
```

### Design choices

**Binary, not JSON.** ESP-NOW airtime is shared with Wi-Fi on the same radio. Fourteen bytes at 10 Hz is nothing; a JSON blob at the same rate is not. The host link is JSON because it is a wired serial port and the host is the side that should be easy to write against.

**`0xFFFF`, not `0`.** A time-of-flight sensor returns nothing when its range status is bad. Encoding that as zero makes "the sensor failed" indistinguishable from "something is touching the lens" — exactly the reading an intrusion would produce.

**Events are not heartbeats.** A trigger transition or a knock is sent at once, not on the next tick. The one-second heartbeat exists only so Node 1 can tell "nothing is happening" from "Node 2 is dead".

**Never raises.** `unpack()` returns `None` for a short, foreign or wrong-version frame. A stray ESP-NOW packet must not kill the loop that is also drawing the display.

### Staleness

Node 1 declares the link down after 4 s of silence and reports `present: false` — not the last value it saw. A frozen reading that looks live is worse than a visibly dead sensor. Do not raise the timeout to hide a flaky link.

### Both boards on one channel

ESP-NOW and Wi-Fi station mode share one radio. If Node 1 has joined an access point and Node 2 has not, they can be on different channels, and every frame is dropped with no error on either board. Both boards therefore join the same network (`wifi_cfg.py`), so both follow the access point wherever it goes.

---

## Link 2 — Node 1 → host, JSON lines

Newline-delimited JSON at **115200 baud**. One object per line, no pretty-printing, so `readline()` plus `json.loads()` is the whole parser.

### `telemetry` — every 2 s

```json
{"t":"telemetry","temp_c":31.0,"humidity":54.0,"gas_raw":412,"gas_ratio":1.02,
 "gas_alert":false,"gas_alarm":false,"flame":false,"present":false,
 "fall":false,"accel_g":1.00,"tilt":2,
 "node2_link":true,"tof_mm":[412,null,1180,2400],
 "tof_zone":["PRESENT","CLEAR","FAR","CLEAR"],"knock":false}
```

| Field | Meaning |
|---|---|
| `temp_c`, `humidity` | DHT11. **`-99` means the read failed** — never treat it as a temperature |
| `gas_raw` | MQ-2 raw ADC count, 0–4095 |
| `gas_ratio` | Current reading ÷ calibrated clean-air baseline. 1.0 is normal |
| `gas_alert` | Ratio above 1.20 — a mild rise |
| `gas_alarm` | Ratio above 1.50 — act on this |
| `flame` | Flame sensor asserted |
| `fall` | Latched true for 15 s after a confirmed fall |
| `accel_g` | Total acceleration; 1.00 at rest |
| `tilt` | Degrees from flat |
| `node2_link` | **`false` means Node 2 is not talking.** Do not trust `present` or `tof_*` when this is false |
| `present` | Any time-of-flight sensor currently triggered |
| `tof_mm` | Four distances in mm, `null` for a failed read. Order: front, left, right, rear |
| `tof_zone` | `TOUCH` `NEAR` `PRESENT` `FAR` `CLEAR` |
| `knock` | A vibration switch fired |

### `event` — sent immediately, not on the 2 s tick

```json
{"t":"event","event":"fall","peak_g":2.84,"tilt":88}
{"t":"event","event":"wave"}
```

| Event | Meaning |
|---|---|
| `fall` | Three-stage fall signature confirmed. **Rule-based path — never send this to a language model** |
| `wave` | Presence trigger. A wake signal that needs no wake word |

### `boot` and `calibrated` — once at start-up

```json
{"t":"boot","mpu":true}
{"t":"calibrated","gas_base":412,"gas_v":0.50,"flame_base":1800,"tilt":2,"baseline_ok":true}
```

`baseline_ok: false` means the MQ-2 baseline landed above the ADC's linear region: the sensor is not burned in and its readings are not trustworthy. Surface that; do not silently report numbers.

---

## Host → Node 1

### Set the face

```json
{"emotion":"happy"}
```

Valid: `neutral` `happy` `sad` `thinking` `concerned` `alarm`.

**The override expires after 20 s** and the face falls back to sensor-driven. That is deliberate: if the host process dies, GENIE must not sit with a happy face through a gas leak. Re-send on every turn to hold an expression.

**Alarms always win.** A gas, flame or fall alarm forces the alarm face whatever the host asked for.

### Recalibrate

```json
{"cmd":"recalibrate"}
```

Reboots the node and repeats the warm-up and clean-air baseline. Use after moving the unit to another room.

---

## Using it from the host

```python
from genie_serial import GenieNode

node = GenieNode("COM5")              # Linux / macOS: "/dev/ttyUSB0"
node.on_alarm = handle_alarm          # Path A: rule-based, no language model
node.on_wake  = start_listening
node.start()

node.set_emotion("thinking")
prompt = node.sensor_context() + "User: " + transcript
```

`on_alarm` is the bypass that keeps a fire off an 8–15 second pipeline. `sensor_context()` returns a short block of real readings so that a language model answering a general question is not left to invent them. Keep it short: every token there is context a CPU-bound model has to chew through.
