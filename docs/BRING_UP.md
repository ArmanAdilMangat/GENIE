# Bring-up

How to get the two sensor boards from blank to talking. Follow the order the first time; each step proves the one before it, and skipping is how a day disappears.

## Toolchain

Both boards run **MicroPython**. Development used [Thonny](https://thonny.org/); `mpremote` works equally well. Only one tool can hold a serial port at a time.

Flash the **`ESP32_GENERIC_S3-SPIRAM_OCT`** build on a module with octal PSRAM. The plain build boots, reports that PSRAM is not connected, and leaves about 100 KB of heap instead of 8 MB — which later shows up as unexplained out-of-memory errors once Wi-Fi is on.

**Modules are uploaded; test scripts are run.** Anything that is imported must physically be on the board, flat in the device root — the imports are flat and a folder breaks them. Bench scripts are run from the editor and inline everything they need, so a half-finished upload cannot break them.

| Board | Upload to the device root | Autostart |
|---|---|---|
| Node 1 | everything in `firmware/node1_face/upload/`, plus `firmware/link/genie_link.py` | `main.py` |
| Node 2 | everything in `firmware/node2_presence/upload/`, plus `firmware/link/genie_link.py` | `main.py` |

For Node 2, copy `wifi_cfg.example.py` to `wifi_cfg.py`, set the network name and password, and upload that. `wifi_cfg.py` is git-ignored.

If a file is on a board and not in its upload folder, delete it. MicroPython imports whatever it finds first, so a stale module shadows the new one. `firmware/node1_face/tools/cleanup.py` audits the device and lists what does not belong.

## Order

1. **One ToF sensor.** `node2_presence/bench/tof_multi.py`, menu option 4. Proves the driver and the bus.
2. **Four ToF sensors.** `node2_presence/calibration/QUICK_CHECK.py`: bring-up, a 3 s baseline, a live loop. Wave a hand and the LED goes red. If bring-up fails, `tof_multi.py` option 3 names the bad XSHUT wire.
3. **Calibrated.** `node2_presence/calibration/CALIBRATE_AND_DETECT.py`, option 6. Robust thresholds, hysteresis, drift, saved baseline. Method: [`calibration/README.md`](../firmware/node2_presence/calibration/README.md).
4. **Node 1 display.** `node1_face/testing/00_TFT_Display/test_tft.py`. The panel must answer with ID `0x9341` before anything else is wired.
5. **Node 1 sensors, one at a time, display always connected.** Work through `node1_face/testing/` in number order. Never add two modules at once.
6. **The face.** Upload the Node 1 modules; `main.py` starts `genie_ui` after a three-second window in which Ctrl-C gives a clean REPL.
7. **The link.** Run `node1_link.py` on Node 1 — it prints its station MAC. Put that in `NODE1_MAC` at the top of `node2_main.py`. Start Node 2. Distances print on Node 1 within a second. Broadcast (`ff:ff:ff:ff:ff:ff`) works for a first test, and every ESP-NOW device in the room receives it.
8. **The host.** `python3 host/serial_reader/genie_serial.py` runs an offline self-test; then point `GenieNode` at the real port.

## Gates

Do not move past a gate because time is short. These are the ones that have already cost days.

**Presence array**

- [ ] Calibration completes clean from a **cold boot** — unplug and replug, not a soft reset — three times in a row
- [ ] Yield at least 90 % on every sensor
- [ ] Walking into each side triggers only that side's sensor
- [ ] Standing still for 60 s stays detected; drift must not absorb a person
- [ ] Empty room, five minutes, zero false triggers

The five-minute test is the one people skip and the one that embarrasses them in a demonstration.

**Link**

- [ ] `python3 firmware/link/genie_link.py` passes on the desktop
- [ ] Node 1 prints distances with Node 2 running
- [ ] Power Node 2 down: Node 1 reports the link down within 4 s, not a frozen last reading
- [ ] Sequence numbers advance without large gaps

**Integrated**

- [ ] The eyes stay smooth with the link polling and every sensor live
- [ ] A gas alarm forces the alarm face whatever the host requested
- [ ] A host-set expression expires after 20 s

## When something does not start

| Symptom | First thing to check |
|---|---|
| White screen, no error | Read the shield's labels. `LCD_D0` and `LCD_D1` are not next to `D2`–`D7` |
| White screen after it worked | Controller power. The backlight is a separate supply and glows with the controller dead |
| All four ToF sensors gone after a reset | Addresses live in sensor RAM. Bring-up must run on every boot |
| ToF works with one or two sensors, fails at three or four | Too many pull-ups in parallel, or the 3.3 V rail sagging under load |
| ToF baseline under 150 mm with almost no noise | Something is in front of the lens |
| `ImportError` on a module that exists on the laptop | It is not on the board. This is never a wiring fault |
| ESP-NOW silent, both boards healthy | The two boards are on different Wi-Fi channels |
| MQ-2 reading swings in clean air | Ground reference. Run the microcontroller's ground directly to the sensor's |
| Random crashes that look like a power fault | A wire on GPIO 33–37 |
| A pin reads "connected" but nothing works | Re-read it with an internal pull-down |
| Locked out of the REPL | Ctrl-C repeatedly while pressing reset; failing that, hold BOOT while plugging in |

More in [`LESSONS.md`](LESSONS.md) and the [fault records](fault-records/).
