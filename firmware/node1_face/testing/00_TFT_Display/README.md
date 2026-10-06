# 00 — TFT Display

ILI9341, 8-bit 8080 parallel. **Only the display wired. Nothing on P2.**

```python
>>> import test_tft
>>> test_tft.run()
```

## Wiring (frozen — P1 header)

| Signal | GPIO |
|---|---|
| D0 D1 D2 D3 | 4, 5, 6, 7 |
| D4 D5 D6 D7 | 15, 16, 17, 18 |
| WR | 8 |
| RD | 9 |
| RS / DC | 10 |
| CS | 11 |
| RST | 12 |

VCC → **5V** (MCUFRIEND-style shields regulate 5V down themselves). GND → GND.

## The five tests

1. **`t1_pins()`** — releases all 13 lines, then reads each with a pull-up and a pull-down. Only meaningful with the ribbon **unplugged**; with the panel connected the panel's own bus holds lines and that is normal.
2. **`t2_id()`** — turns the bus around and reads the controller ID back. This is the test that answers *"is my white screen a wiring fault or the wrong driver?"* An ID of `0x9341` means ILI9341 and the project driver is correct. `0x9486`, `0x7789`, anything else → `ili9341_par.py` will give a white screen forever, and no amount of re-soldering fixes it.
3. **`t3_fills()`** — red, green, blue, white, black, full screen, slow bit-bang. Which colour comes out wrong names the broken data lines.
4. **`t4_bars()`** — 8 colour bands. All correct and in order = the bus is good.
5. **`t5_driver()`** — loads the real `ili9341_par.py` viper driver and times a full-screen fill. Under ~120 ms means viper compiled and the bus runs at speed. Needs `ili9341_par.py` uploaded.

## White screen — read in this order

| Symptom | Cause |
|---|---|
| Backlight on, never changes, `t2_id()` returns a non-`0x9341` ID | Wrong driver. Not a wiring problem. |
| Backlight on, `t2_id()` reads nothing, `t3` stays white | RST (GPIO12) never pulsed, or WR/RS/CS not wired |
| One colour wrong, others fine | That colour's data lines — see the mapping `t3_fills()` prints |
| Bands smeared or repeated | WR (GPIO8) timing or a bad joint on WR |
| Screen dark, no backlight at all | VCC on 3.3V instead of 5V |

## Do not trust a pin check after a soft reboot

`MPY: soft reboot` does not reset GPIO. Pins left as outputs by the last script still read as driven, and that reads as "shorted to a rail." Ten simultaneous rail shorts on a hand-soldered board is not a real fault — it is leftover output state. Hard-reset (`import machine; machine.reset()`) before believing any pin reading.
