# Wiring Reference

GENIE Phase 1 uses one ESP32-S3 DevKitC-1 and one INMP441 I2S MEMS
microphone. The reply audio plays back on the laptop speakers, so no
speaker amplifier is required at this stage. Phase 2 adds the MAX98357A +
3W speaker module — that wiring is included below for forward reference.

---

## INMP441 → ESP32-S3 (Phase 1)

| INMP441 pin | ESP32-S3 GPIO | Role                                 |
| :---------: | :-----------: | ------------------------------------ |
|    VDD      |     3.3 V     | Power                                |
|    GND      |      GND      | Ground                               |
|    L/R      |      GND      | Channel select — pull LOW for right  |
|    WS       |    GPIO 6     | I2S word select (LRCLK)              |
|    SCK      |    GPIO 7     | I2S bit clock (BCLK)                 |
|    SD       |    GPIO 5     | I2S serial data (SDIN to MCU)        |

> The firmware configures I2S0 in `I2S_CHANNEL_FMT_ONLY_RIGHT` mode, which
> matches `L/R = GND`. If you tie L/R to 3.3 V instead, change the channel
> format to `ONLY_LEFT` in `setupMic()`.

### Push-to-talk

| Function | Pin | Notes |
| -------- | :--: | ----- |
| Push-to-talk button | GPIO 0 (built-in **BOOT** button) | Active low, `INPUT_PULLUP` |

No external button is needed — the on-board BOOT button doubles as the
record trigger. A typed `r` in the serial monitor works too.

---

## I2S signal-conditioning notes

The INMP441 outputs 24-bit samples padded into a 32-bit I2S frame. The
firmware right-shifts each sample by 13 bits before truncating to 16-bit
PCM:

```cpp
audioBuf[idx++] = (int16_t)(buf[i] >> 16);   // truncate to upper 16 bits
// (in testMic) abs(buf[i] >> 14)             // for level metering only
```

Experimentally, `>>13` gave the best balance between dynamic range and
clipping for typical conversational volume in a quiet room. Use the `m`
serial command to verify a peak above 2000 before recording.

---

## MAX98357A → ESP32-S3 (Phase 2 — reference only)

Not used in Phase 1, but documented here so the Phase 1 build is
forward-compatible with the Phase 2 wiring loom.

| MAX98357A pin | ESP32-S3 GPIO | Role                |
| :-----------: | :-----------: | ------------------- |
|     VIN       |      5 V      | Power               |
|     GND       |      GND      | Ground              |
|     BCLK      |    GPIO 10    | I2S bit clock       |
|     LRC       |    GPIO 11    | I2S word select     |
|     DIN       |    GPIO 12    | I2S serial data     |
|     GAIN      |      GND      | +9 dB (default)     |
|     SD        |      —        | Leave floating      |

A 100 µF electrolytic capacitor across the speaker's VIN/GND pins is
strongly recommended to suppress the high-current transients that caused
the early "WiFi audio crackle" issue.

---

## Power

A single USB-C cable from the laptop powers the dev board for both phases.
Phase 3 will move to a 18650 + boost converter for portable operation.
