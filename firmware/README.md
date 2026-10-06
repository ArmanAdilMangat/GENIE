# Firmware

| Folder | Board | Language | State in this repository |
|---|---|---|---|
| [`link/`](link/) | both sensor boards | MicroPython / CPython | The three files that must be identical on both boards: the ESP-NOW frame (`genie_link.py`), the Wi-Fi uplink (`net_uplink.py`) and the network settings template (`wifi_cfg.example.py`) |
| [`node1_face/`](node1_face/) | Node 1 — face and safety sensing | MicroPython | The integrated build: display driver, face, sensor reader, UI, link receiver, telemetry emitter, fall and handling state machines, on-device classifier. Plus per-sensor benches |
| [`node2_presence/`](node2_presence/) | Node 2 — presence array | MicroPython | The integrated build, plus calibration and the diagnostic bench |
| [`r307s_fingerprint/`](r307s_fingerprint/) | bench only | MicroPython and Arduino C++ | Verification suite and driver. Not part of the final system |
| [`audio_nodes/`](audio_nodes/) | Microphone node and speaker node | MicroPython | One file each. Stereo capture to the host; opcode-framed playback from it |
| [`modem_node/`](modem_node/) | Cellular modem node | MicroPython | Board main loop and settings template. The driver is shared with the host and lives at `host/Services/modem.py` |
| — | Relay / IoT node | — | **Not in this repository.** `host/config.py` refers to it as `IoT_esp.py`; the file was not in the code this repository was assembled from |

## What integration added on Node 1

The display driver, the face, every sensor reader, the one-button UI, the diagnostics menu and the receiving half of the ESP-NOW link are the sensing side as handed over for integration on 27 August 2026. Integration added the telemetry emitter (`node1_report.py`), the fall and handling state machines (`fall_fsm.py`, `handling_fsm.py`), the feature extractor and the exported on-device model (`har_features.py`, `har_model.py`), and reworked `main.py` and `genie_ui.py` to run them.

## Conventions

- **Modules are uploaded; bench scripts are run.** Everything in an `upload/` folder goes flat into the device root. Scripts under `testing/`, `bench/` and `calibration/` are run from the editor and inline what they need, so a half-finished upload cannot break them.
- **`main.py` never retries.** Three-second grace period, one attempt, full traceback, stop. A boot loop on an autostarting board locks out the REPL.
- **One pin map per board.** `pins.py` on Node 1 fails loudly if a signal lands on a display pin or in the PSRAM range.
- **Credentials stay out of git.** Copy `link/wifi_cfg.example.py` to `wifi_cfg.py` and `modem_node/settings.example.py` to `settings.py`; both results are ignored. The two audio-node files carry the network name and password at the top; set them before flashing and do not commit.

Flashing and bring-up order: [`docs/BRING_UP.md`](../docs/BRING_UP.md). Pin maps and power: [`docs/HARDWARE.md`](../docs/HARDWARE.md).
