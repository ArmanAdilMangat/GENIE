# Hardware

Pin assignments, power and the constraints that produced them, for the two sensor boards in this repository. Both are ESP32-S3 modules with octal PSRAM running MicroPython.

Pin numbers are GPIO numbers. The single source of truth in code is [`pins.py`](../firmware/node1_face/upload/pins.py) for Node 1 and the constants at the top of [`node2_main.py`](../firmware/node2_presence/upload/node2_main.py) for Node 2.

## Node 1 — face and safety

> **The rule: P1 header is the display. P2 header is the sensors. Nothing crosses.**

### Display — 15 wires on P1, frozen

| Signal | GPIO | Signal | GPIO | Signal | GPIO |
|---|---|---|---|---|---|
| `LCD_D0` | 4 | `LCD_D4` | 15 | `LCD_WR` | 8 |
| `LCD_D1` | 5 | `LCD_D5` | 16 | `LCD_RD` | 9 |
| `LCD_D2` | 6 | `LCD_D6` | 17 | `LCD_RS` / DC | 10 |
| `LCD_D3` | 7 | `LCD_D7` | 18 | `LCD_CS` | 11 |
| | | | | `LCD_RST` | 12 |

Plus 3V3 and GND. The panel is a 2.4" ILI9341 on an Arduino-Uno-style shield with an 8-bit 8080 parallel bus. On the shield, `LCD_D0` and `LCD_D1` sit in a different pin group from `D2`–`D7`, and both groups run backwards — [read every label, never count pads](fault-records/tft-data-pin-order.md).

### Sensors — P2

| Sensor | Signal | GPIO | Type | Supply |
|---|---|---|---|---|
| MQ-2 gas #1 | AO | 1 | Analogue, ADC1 | 5 V (heater) |
| MQ-2 gas #2 | AO | 2 | Analogue, ADC1 | 5 V (heater) |
| Flame | DO | 42 | Digital | 3V3 |
| SW-420 vibration, top | DO | 41 | Digital | 3V3 |
| SW-420 vibration, bottom | DO | 40 | Digital | 3V3 |
| Push button | — | 39 | Digital, internal pull-up | — |
| MPU-6050 ×2 | SCL / SDA | 38 / 47 | I²C at 100 kHz, `0x68` and `0x69` | 3V3 |
| DHT11 | DATA | 21 | Single-wire | 3V3 |
| WS2812B strip, 8 LEDs | DIN | 48 | One-wire | 4.3–4.5 V |

Two of these are forced, not chosen:

- **Flame uses its digital output** because only GPIO1 and GPIO2 are usable analogue inputs, and the two MQ-2 sensors fill them. ADC2 (GPIO 11–20) returns garbage whenever the radio is active.
- **The button is on GPIO39, not GPIO0.** GPIO0 is a strapping pin: a wiring fault that holds it low boots the chip into the bootloader and the REPL becomes unreachable. On GPIO39 the same fault is merely visible.

The two IMUs are told apart by AD0: tied to ground for `0x68`, to 3V3 for `0x69`. Forget one and both answer at `0x68`.

Full wire-by-wire card: [`firmware/node1_face/WIRING.md`](../firmware/node1_face/WIRING.md).

### Power

| Rail | Fed from | Powers | Load |
|---|---|---|---|
| 3V3 | ESP32 3V3 pin | flame, 2× SW-420, DHT11, 2× MPU-6050 | about 90 mA |
| 5 V | Bench supply only | 2× MQ-2 heaters, LED strip | about 300 mA plus the strip |
| GND | ESP32 **and** the bench supply, tied | everything | — |

**Common ground is not optional**, and the path matters as much as the connection: see [the MQ-2 ground reference](fault-records/mq2-ground-reference.md).

**The MQ-2 heater needs 5 V.** Heater power goes with the square of voltage, so at 3.3 V it runs at 44 % of rated power, never reaches operating temperature, and the baseline drifts. A new sensor needs 24–48 hours powered before its baseline means anything.

**The LED strip runs below 5 V on purpose.** A WS2812 fed 5 V wants 3.5 V for a guaranteed logic high; a 3.3 V GPIO does not deliver it. Dropping the strip supply to about 4.4 V lowers the threshold to about 3.1 V. Random flicker on a WS2812 strip is this, not the code.

## Node 2 — presence

| Signal | GPIO | Note |
|---|---|---|
| I²C SDA | 8 | Shared by all four sensors |
| I²C SCL | 9 | **One** 4.7 kΩ pull-up pair to 3V3 for the whole bus |
| XSHUT front / left / right / rear | 10 / 11 / 12 / 13 | One GPIO per sensor. Order is the address order and the direction order |
| Vibration switch DO | 14, 15, 21, 47 | Two fitted |
| WS2812 status | 5 | |

| Parameter | Value |
|---|---|
| Addresses | `0x30` front, `0x31` left, `0x32` right, `0x33` rear |
| Bus speed | 100 kHz. 400 kHz produced `ENODEV` on all four over dupont wire |
| Supply | 3V3 only. The ESP32-S3 is not 5 V tolerant |
| Range mode | SHORT: about 1.3 m, far better ambient-light immunity than LONG |
| Ranging budget | about 100 ms, so about 10 Hz per sensor |
| Field of view | 27°. With four sensors 90° apart there are blind wedges between the cones |
| Model ID | `0xEACC` confirms a genuine VL53L1X |

### The address problem

Every VL53L1X ships at I²C address `0x29`. Four on one bus answer at once and the bus returns garbage. The only fix is the XSHUT pin, which holds a chip in reset while low:

1. Drive all four XSHUT lines low.
2. Raise the first. It wakes at `0x29`. Write its new address, `0x30`.
3. Raise the second. It wakes at `0x29`, now free. Reassign to `0x31`.
4. Repeat for `0x32` and `0x33`.

**The new addresses live in sensor RAM, not flash.** Every reset and every power cycle drops all four back to `0x29`, so this sequence runs at the top of every boot. When four sensors "stop working" after a reset, this is why.

## Pins that are not what they look like

| GPIO | Committed to | Symptom if used |
|---|---|---|
| 26–32 | SPI flash | Board crashes or will not boot |
| **33–37** | **Octal PSRAM** | Random crashes that look exactly like a power fault. The DevKitC-1 silkscreen shows them as general I/O |
| 19, 20 | Native USB | USB stops enumerating |
| 43, 44 | UART0, the REPL | Loss of the serial console |
| 0, 3, 45, 46 | Boot strapping | GPIO0 low at reset enters the bootloader |
| 11–20 as ADC | ADC2, shared with the radio | No error. Readings silently become meaningless |

## Current budget

Peaks matter more than averages: a brown-out shows up as a reset loop, not an error message.

| Load | Typical | Peak |
|---|---|---|
| ESP32-S3 with radio | 80 mA | 350 mA on a transmit burst |
| VL53L1X ×4 | 80 mA | 160 mA ranging |
| WS2812 ×8 at brightness 40/255 | 60 mA | 480 mA at full white |
| MQ-2 heaters ×2 | 300 mA | — |
| A7670E modem | 100 mA | **2 A** on a transmit burst |

USB alone does not cover either sensor board. Both use an external 5 V supply with grounds tied, and stay on USB only for the REPL. The modem needs its own feed and its own bulk capacitor at the module; it must never be daisy-chained from a sensor rail.

A rail validated before the radio was switched on is not validated. Both sensor boards had their supplies proven with sensors, display and LEDs — then a transmitting radio added 350 mA peaks to the same rail.

## Enclosure

177.8 mm cube, 3 mm clear cast acrylic, sliding back panel. Apertures and positions are in [`enclosure/README.md`](../enclosure/README.md).
