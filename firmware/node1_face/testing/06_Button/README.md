# 06 — The Button

TFT stays wired. Add **only** the button.

| Signal | GPIO |
|---|---|
| button | 39 (P2-9), other side to GND |

No external resistor — the internal pull-up handles it. Pressed = 0.

```python
>>> import test_button
>>> test_button.run()
```

## Why GPIO39 and not GPIO0

GPIO0 is a strapping pin. Any wiring fault that holds it low boots the board into the ROM bootloader and Thonny cannot connect at all — the fault hides itself. On GPIO39 the same fault is merely visible.

## Gesture decoder

`gestures()` runs the same single / double / long logic the GENIE UI uses, so anything that misfires here misfires there.

| gesture | window |
|---|---|
| double | second press starts within 350 ms |
| long | held ≥ 700 ms |
| debounce | 30 ms |

Reads 0 with nothing pressed = stuck button, or wired to 3V3 instead of GND.
