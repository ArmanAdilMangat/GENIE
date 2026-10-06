# FINAL WIRING CARD — every wire on the board

**Print this. Check every wire against it BEFORE the heat gun.**
Generated from `pins.py`, 13-08-2026.

> **THE RULE: P1 = display. P2 = sensors. Nothing crosses.**

---

## P1 header — the display (15 wires, FROZEN)

Counting from the `3V3` end.

| Pos | Board label | Goes to | Notes |
|---|---|---|---|
| 1 | `3V3` | **TFT VCC** | controller power — missing this = white screen |
| 2 | `3V3` | **3.3 V rail feed** | this is what powers every 3V3 sensor |
| 3 | `RST` | — | |
| 4 | `4` | **LCD_D0** | |
| 5 | `5` | **LCD_D1** | |
| 6 | `6` | **LCD_D2** | |
| 7 | `7` | **LCD_D3** | |
| 8 | `15` | **LCD_D4** | |
| 9 | `16` | **LCD_D5** | |
| 10 | `17` | **LCD_D6** | |
| 11 | `18` | **LCD_D7** | |
| 12 | `8` | **LCD_WR** | |
| 13 | `3` | — | strapping, leave open |
| 14 | `46` | — | strapping, leave open |
| 15 | `9` | **LCD_RD** | |
| 16 | `10` | **LCD_RS** (DC) | |
| 17 | `11` | **LCD_CS** | |
| 18 | `12` | **LCD_RST** | |
| 19 | `13` | — | free (was IR obstacle, dropped) |
| 20 | `14` | — | free |
| 21 | `5V` | — | not used; 5 V comes from the bench supply |
| 22 | `G` | **TFT GND + ground rail** | |

**Data pins are NOT in numeric order.** D4–D7 sit at positions 8–11 as GPIO
15–18, *before* WR at position 12. Read every label; do not count pads.

**Do not heat-shrink this bundle.** It has to stay serviceable, and heat near
this ribbon risks the one thing that already cost two days.

---

## P2 header — the sensors

Counting from the `G` end (the one near TX/RX).

| Pos | GPIO | Goes to | Rail |
|---|---|---|---|
| 1 | `G` | **GND rail feed** | — |
| 2 | `TX` | leave open — serial console | |
| 3 | `RX` | leave open — serial console | |
| **4** | **1** | **MQ-2 #1 — AO** | 5 V bench |
| **5** | **2** | **MQ-2 #2 — AO** | 5 V bench |
| **6** | **42** | **Flame — DO** | 3V3 |
| **7** | **41** | **SW-420 top — DO** | 3V3 |
| **8** | **40** | **SW-420 bottom — DO** | 3V3 |
| **9** | **39** | **Button** | — |
| **10** | **38** | **I²C SCL** — both MPUs | 3V3 |
| 11 | `37` | **PSRAM — never use** | |
| 12 | `36` | **PSRAM — never use** | |
| 13 | `35` | **PSRAM — never use** | |
| 14 | `0` | free — onboard BOOT button lives here | |
| 15 | `45` | strapping, leave open | |
| **16** | **48** | **WS2812 strip — DIN** | 5 V bench |
| **17** | **47** | **I²C SDA** — both MPUs | 3V3 |
| **18** | **21** | **DHT11 — DATA** | 3V3 |
| 19 | `20` | native USB, leave open | |
| 20 | `19` | native USB, leave open | |
| 21 | `G` | ground rail | — |
| 22 | `G` | ground rail | — |

Signals run **4-5-6-7-8-9-10** contiguously, then **16-17-18**. Wire in header
order and a misplaced jumper is obvious.

---

## Per-module wiring — check each one off

| Module | VCC | GND | Signal → GPIO | Special |
|---|---|---|---|---|
| **MQ-2 #1** | 5 V bench | GND rail | AO → **1** | own 10k/20k divider ⚠ not fitted |
| **MQ-2 #2** | 5 V bench | GND rail | AO → **2** | own 10k/20k divider ⚠ not fitted |
| **Flame** | 3V3 rail | GND rail | **DO** → **42** | AO unconnected |
| **SW-420 top** | 3V3 rail | GND rail | DO → **41** | |
| **SW-420 bottom** | 3V3 rail | GND rail | DO → **40** | |
| **MPU top** | 3V3 rail | GND rail | SCL **38**, SDA **47** | **AD0 → GND** = 0x68 |
| **MPU bottom** | 3V3 rail | GND rail | SCL **38**, SDA **47** | **AD0 → 3V3** = 0x69 |
| **DHT11** | 3V3 rail | GND rail | DATA → **21** | mount **outside** the box |
| **Button** | — | GND rail | one leg → **39** | ⚠ currently on the wrong leg pair |
| **WS2812B-8** | 5 V bench | GND rail | **IN** → **48** | left side only; OUT end unused |

Both MQ-2 `DO` pins: **unconnected**. Both MPU `INT` pins: **unconnected**.

---

## The three rails

| Rail | Fed from | Powers | Load |
|---|---|---|---|
| **3V3** | ESP32 **3V3, P1 pos 2** | flame, 2× SW-420, DHT11, 2× MPU | ~90 mA |
| **GND** | ESP32 `G` (P2-1/21/22) **AND** bench supply `−` | everything | — |
| **5 V** | **bench supply only** | 2× MQ-2 heaters, LED strip | ~300 mA + strip |

**Common ground is not optional.** The bench supply's ground must tie to the
ESP32's. Without it the ADC has no reference — that was the bimodal MQ-2 fault,
and joining the grounds is what fixed it.

**Never feed the MQ-2 heaters or the LED strip from the ESP32's 3V3.**

---

## Count before you seal

| | Wires |
|---|---|
| TFT bundle (P1) | 15 |
| Sensor signals (P2) | 10 |
| 3V3 rail feed | 1 |
| GND rail feeds | 1–3 |
| Bench supply + and − | 2 |
| Module VCC/GND (2 per module × 10) | 20 |
| **Total, roughly** | **~50** |

---

## Before the heat gun — leave these reachable

| Leave exposed | Why |
|---|---|
| **Flame trim pot** | you re-trim if the room changes |
| **Both SW-420 pots** | sensitivity is what you'll keep adjusting |
| **MQ-2 divider positions** | resistors not fitted yet — you still need access |
| **AD0 wires on both MPUs** | address changes are a real possibility |
| **The button** | wrong leg pair, needs re-soldering |

### Heat gun technique

1. **Keep the gun away from sensor bodies.** MQ-2 plastic bases, the DHT11
   housing and MPU headers deform below the temperature the tubing needs.
   Shrink mid-wire, not against a module.
2. **Leave a 3–4 cm service loop** near each module.
3. **Do not shrink the P1 / TFT bundle.**
4. **Label or colour-code before sealing.** After this, `pins.report()` is your
   only map.
5. **Shrink one bundle, then re-run `genie_menu.live()`.** Not all of them and
   then test — you want to know which bundle broke it.

---

## Verify from the REPL

```python
import pins
pins.report()
pins.check()
```

`check()` fails loudly if any signal has landed on a TFT pin, in the PSRAM
range (26–37), or off the P2 header.

```python
import genie_menu
genie_menu.live()
```

Expect every sensor to report a live value.

---

## Still outstanding at seal time

- **MQ-2 dividers** — not fitted. `DIVIDER = 1.0`. **No butane until fitted**,
  then set `DIVIDER = 1.5`.
- **Button** — wrong leg pair; keyboard fallback active (`a` `b` `k` `t`).
- **LED strip** — run at **4.3–4.5 V**, not 5 V.
- **Flame pot, SW-420 pots, IMU self-check** — all uncalibrated.
