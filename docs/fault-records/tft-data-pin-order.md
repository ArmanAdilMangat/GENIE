# Two days on a white screen

**Class:** wiring · **Cost:** two days · **State:** fixed; rule recorded

## Symptom

The display driver runs. No exception, no error of any kind. The screen stays white.

## Cause

The panel is an ILI9341 on an Arduino-Uno-style shield with an 8-bit parallel bus. On that shield, `LCD_D0` and `LCD_D1` sit inside the SD-card pin group, physically separate from `LCD_D2`–`LCD_D7` — and both groups run backwards.

Wiring by counting header positions, not by reading the printed labels, puts the SD chip-select line where `LCD_D0` belongs.

## Why it cost so much

The failure is completely silent. With one data lane wrong the controller receives corrupted bytes and never initialises. There is nothing to catch and nothing to log. And a white screen has a second, unrelated cause that looks identical: the backlight is a separate supply from the controller and glows with the controller unpowered.

## Fix

Rewired from the labels. The wiring document now states, in these words: *the data pins are NOT in numeric order.*

The bundle is frozen. Thirteen signal wires plus power and ground on one header, never reassigned, and never heat-shrunk — heat near that ribbon risks the one thing that already cost two days.

## Two tests that came out of it

**Ask the panel who it is.** If the controller answers with ID `0x9341`, the bus is proven good, whatever any static pin reading says. The diagnostic script checks this first and suppresses the rest.

**A static pin reading never outranks a functional test.** Thirteen display lines that read "tied low" are the shield's level-shifter network — about 2 kΩ to ground against a 45 kΩ internal pull-up — not thirteen solder bridges.

## A related wrong turn

During the same period the display was declared impossible to drive from MicroPython: no maintained driver exists for parallel shields, and bit-banging eight lines per pixel from Python was expected to take seconds per redraw. The project moved to a C++ toolchain on that premise.

The premise was then disproved by measurement. A hand-written driver whose hot loops are compiled with `@micropython.viper` and write the GPIO registers directly fills at 2,477 kpx/s and sustains 118 fps in the face engine's soak test. What made it viable was less the bus speed than repaint discipline: a value is redrawn only when its rendered string changes.

The driver is [`ili9341_par.py`](../../firmware/node1_face/upload/ili9341_par.py).

## Rule

Read every label. Never count pads.
