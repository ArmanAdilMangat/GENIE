# GENIE Firmware — ESP32-S3 (Phase 1)

The ESP32-S3 client. Captures push-to-talk audio from an INMP441 I2S microphone
and POSTs a 16 kHz mono WAV to the [Flask server](../server/).

## Layout

```
firmware/
├── platformio.ini              ← board, framework, build flags
├── src/
│   └── main.cpp                ← the firmware
└── include/
    ├── secrets.h.example       ← committed template
    └── secrets.h               ← your real creds (gitignored)
```

## Build & flash

```bash
# First time only — fill in your WiFi + Flask IP
cp include/secrets.h.example include/secrets.h
$EDITOR include/secrets.h

# Build, flash, monitor
pio run -t upload
pio device monitor -b 115200
```

> **Board variant:** `platformio.ini` is tuned for the ESP32-S3 DevKitC-1 **N16R8**
> (16 MB flash, 8 MB PSRAM). If you have a non-PSRAM revision, drop
> `-DBOARD_HAS_PSRAM` from `build_flags` — Phase 1 doesn't actually require PSRAM,
> but the flag keeps the binary forward-compatible with Phase 2.

## Pin map

See [`../docs/wiring.md`](../docs/wiring.md) for the full table. Short version:

| INMP441 | ESP32-S3 |
| :-: | :-: |
| WS  | GPIO 6 |
| SCK | GPIO 7 |
| SD  | GPIO 5 |
| L/R | GND |
| VDD | 3V3 |
| GND | GND |

Push-to-talk uses the built-in **BOOT** button on GPIO 0.

## Serial commands

| Key | Action |
| :-: | --- |
| BOOT button or `r` | Start recording (up to 7 s) |
| `s` | Stop recording early |
| `p` | Pause / resume the main loop |
| `m` | Test microphone — speak for 3 s, see peak level |
| `w` | Test WiFi connectivity and RSSI |
| `f` | Test Flask server reachability |
| `g` | Test Ollama (Mistral) availability |
| `a` | Run all four component tests in sequence |
| `h` | Reprint the help menu |
