# 07 — WS2812 Status LED / Strip

TFT stays wired. Add **only** the strip.

| Signal | GPIO |
|---|---|
| DIN | 48 (P2-16) |
| 5V | bench supply |

```python
>>> import test_ws2812
>>> test_ws2812.run()      # 1 pixel — onboard RGB LED only
>>> test_ws2812.run(8)     # 8-pixel strip wired
```

## Free test before you wire anything

GPIO48 is also the DevKitC-1's **onboard RGB LED**. With nothing connected, `run()` still lights it — that proves the pin before a single wire goes in. With a strip attached the onboard LED becomes pixel 0 and the strip starts at pixel 1.

## Symptoms

| what you see | cause |
|---|---|
| all four colours in order | PASS |
| red shows green, etc. | strip is RGB not GRB — swap the tuple order |
| nothing at all | DIN on the wrong pin, or no 5V to the strip |
| pixel 0 right, rest random | 3.3V data into a 5V strip — add a diode or a 74HCT125 |
| fewer pixels light in `chase()` than expected | break at that position |

## Power

Never run a long strip off the ESP32's 5V pin. 60 LEDs at full white is 3.6 A and it browns out the board. `BRIGHT` is capped at 40 on purpose.

## Status colours GENIE uses

| colour | state |
|---|---|
| blue | IDLE — listening for the wake word |
| green | HEARD — wake word matched |
| yellow | THINKING — Whisper + Mistral running |
| red | ALERT — a sensor tripped |
