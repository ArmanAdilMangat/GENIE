# Firmware

| Folder | Board | Language | State in this repository |
|---|---|---|---|
| [`link/`](link/) | both sensor boards | MicroPython / CPython | The ESP-NOW frame definition. Uploaded to both boards |
| [`node1_face/`](node1_face/) | Node 1 — face and safety sensing | MicroPython | Display driver, face, sensor reader, UI, link receiver, per-sensor benches |
| [`node2_presence/`](node2_presence/) | Node 2 — presence array | MicroPython | As recovered from the board on 2 September 2026, plus calibration and the diagnostic bench |
| [`r307s_fingerprint/`](r307s_fingerprint/) | bench only | MicroPython and Arduino C++ | Verification suite and driver. Not part of the final system |
| `mic_node/` | Microphone node | Arduino-ESP32 C++ | Pending import |
| `speaker_node/` | Speaker node | Arduino-ESP32 C++ | Pending import |
| `relay_node/` | Relay / IoT node | Arduino-ESP32 C++ | Pending import |
| `modem_node/` | Cellular modem node | MicroPython | Pending import |

## What is and is not here for Node 1

`node1_face/` is the face board as it stood when the sensing side was handed over for integration on 27 August 2026: the display, the face, every sensor reader, the one-button UI, and the receiving half of the ESP-NOW link.

The integrated build adds a telemetry emitter, the fall and handling state machines as separate modules, the shared feature extractor and the exported on-device model. Those were developed in the team's integration tree and arrive with the host import.

## Conventions

- **Modules are uploaded; bench scripts are run.** Everything in an `upload/` folder goes flat into the device root. Scripts under `testing/`, `bench/` and `calibration/` are run from the editor and inline what they need, so a half-finished upload cannot break them.
- **`main.py` never retries.** Three-second grace period, one attempt, full traceback, stop. A boot loop on an autostarting board locks out the REPL.
- **One pin map per board.** `pins.py` on Node 1 fails loudly if a signal lands on a display pin or in the PSRAM range.
- **Credentials stay out of git.** Copy `wifi_cfg.example.py` to `wifi_cfg.py`; the latter is ignored.

Flashing and bring-up order: [`docs/BRING_UP.md`](../docs/BRING_UP.md). Pin maps and power: [`docs/HARDWARE.md`](../docs/HARDWARE.md).
