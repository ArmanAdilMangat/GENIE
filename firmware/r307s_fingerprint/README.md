# R307S fingerprint sensor — independent verification

> **Status.** The fingerprint reader is not part of the final system. It was condemned on 24 August 2026, and evidence recovered later contradicts that diagnosis. This suite is the instrument for settling the question; the history is in [the fault record](../../docs/fault-records/r307s-fingerprint.md).

MicroPython on ESP32-S3. No libraries — raw R30x protocol, so there is nothing to install and nothing to go out of date.

Purpose: establish whether the module is **alive, healthy and reliable**, not just "it responded once".

```
r307s_fingerprint/
├── r307s_lifecheck.py     run this first — dead or alive
├── r307s_fulltest.py      then this — is it healthy
├── arduino_version/       the same suite in C++ / Arduino
└── driver/                the driver and probe used during bring-up
    ├── r307.py            R30x protocol driver
    ├── fp_probe.py        baud and pin-order sweep that validates on the packet identifier
    └── fp_bringup.py      first-contact script
```

---

## Wiring under test

| Wire   | Goes to             | Function                              |
|--------|---------------------|---------------------------------------|
| Red    | +5V external        | Main power (4.5–6.0 V, ~120 mA peaks) |
| Black  | GND (ESP32)         | Ground                                |
| Yellow | GPIO18              | Sensor **TX** → ESP **RX**            |
| Green  | GPIO17              | Sensor **RX** ← ESP **TX**            |
| Blue   | GPIO4               | Touch / wake-up output                |
| White  | 3V3                 | Touch-circuit power                   |
| ESP GND| External supply GND | **Mandatory common ground**           |

> ⚠️ **R307 cable colours are not standardised.** Some sellers ship Green=TX /
> Yellow=RX. `r307s_lifecheck.py` tests **both orientations in software**, so you
> never have to guess or rewire to find out.

Do **not** power the sensor from the ESP32's 3V3 rail. Red must be the external 5 V.
White on 3V3 is correct — that pin only powers the touch detector.

In MicroPython `UART(1, tx=17, rx=18)` means *the ESP32's* TX and RX,
so `rx=18` listens to Yellow and `tx=17` drives Green. That is already set.

---

## Step 1 — `r307s_lifecheck.py` : is it dead or alive?

Open in Thonny, **F5**. Fully automatic, ~40 s. It:

1. Tests whether GPIO4 is **floating** — proves Blue/White are actually connected
2. Sweeps **all 12 legal R30x baud rates** (9600 … 115200), not just 57600
3. Repeats the sweep with **TX/RX swapped in software**
4. **Hex-dumps every byte** heard, so *silence* and *garbage* are told apart —
   they are completely different faults
5. Prints a **VERDICT**, then decodes the full system parameters

Write down the two answers it gives you: **baud** and **swapped or not**.

---

## Step 2 — `r307s_fulltest.py` : is it healthy?

Edit the two lines at the top, then **F5**:

```python
BAUD    = 57600    # from lifecheck
SWAPPED = False    # True if lifecheck said SWAPPED
```

You get a menu. Type `a` for the full non-destructive sweep, or single keys.
Every function is also callable straight from the Thonny Shell afterwards —
`enroll(3)`, `search()`, `soak(500)`, `monitor(300)`.

| Key | Test | What it actually proves |
|-----|------|-------------------------|
| `a` | Run all non-destructive tests | one-shot health verdict |
| `p` | System parameters | MCU + config EEPROM readable; system ID must be `0x0009` |
| `t` | Template count | Library accessible |
| `i` | List enrolled IDs | Index table intact |
| `e5`| Enroll to slot 5 | Optics + DSP + **flash write**, end to end |
| `s` | 1:N search | Full biometric match path |
| `v5`| 1:1 verify vs slot 5 | LoadChar + Match path |
| `d5`| Delete slot 5 | Flash erase path |
| `x` | Erase all (type `ERASE`) | — destructive |
| `q` | 10 image captures | **Optics + glass condition**, feature quality |
| `k` | 200-packet soak | **Wiring / power reliability** — the test everyone skips |
| `f` | Flash notepad R/W | Non-volatile memory verified byte-for-byte |
| `g` | LED / aura | Illumination ring |
| `b` | Touch pin monitor | Blue/White path |
| `L` | ESP32 UART loopback | Isolates **ESP32 vs sensor** (jumper 17↔18, sensor unplugged) |
| `r` | Continuous alive monitor | Catches **intermittent** faults and brownouts |

---

## Pass criteria — call it "confirmed working" only if ALL of these hold

- System ID reads `0x0009`; capacity, baud and security level look sane
- Soak test: **200 / 200**, zero timeouts, zero checksum errors
- Flash notepad test: **VERIFY OK**
- Image quality: **≥ 8/10 images**, **≥ 7/10 usable features**
- `enroll(1)` succeeds, then `search()` finds it with confidence **> 60**
- **Power-cycle the board**, run `t` again — the template is **still there**

Anything less is "it works today", not "it works".

---

## Failure decision tree

**No response on any baud, either orientation**

1. Multimeter Red↔Black *at the sensor connector*, powered, under load → 4.5–6.0 V
2. Is ESP GND actually tied to the external supply GND? Without it, UART cannot work
3. Does the ring glow at power-up? No glow + correct voltage = dead module
4. Continuity-test the 6-pin JST; broken solder on the flying leads is the #1 cause
5. Run `L` (loopback) to clear the ESP32 pins themselves
6. Weak 5 V rail → brownout on the ~120 mA capture peak → never answers

**Garbage bytes, no valid packet** → baud mismatch, or long/unshielded wires.
Keep the run under 20 cm, add 100 nF across the sensor's Red/Black.

**Checksum errors in the soak test** → electrically marginal. Do not ship it.
Shorten wires, add decoupling, use a stiffer 5 V supply.

**`0x18 FLASH ERROR` on enroll** → the module's flash is worn or faulty. Replace it.

**Images OK but features poor (`0x07`)** → dirty/scratched glass or dry fingers,
not an electrical fault. Clean with isopropyl.

**`0x21` / `0x13` password errors** → the module has a non-zero password set.
It is alive; the password just isn't `0x00000000`.

**`MemoryError` in Thonny** → soft-reboot the board (Ctrl-D) before re-running.

---

## Confirmation codes quick reference

| Code | Meaning | | Code | Meaning |
|------|---------|-|------|---------|
| 0x00 | OK | | 0x0C | Invalid template |
| 0x01 | Packet receive error | | 0x0D | Template upload error |
| 0x02 | No finger on sensor | | 0x10 | Delete failed |
| 0x03 | Failed to capture image | | 0x11 | Clear library failed |
| 0x06 | Image too disorderly | | 0x13 | Wrong password |
| 0x07 | Too few feature points | | 0x15 | No valid image in buffer |
| 0x08 | No match | | 0x18 | **Flash read/write error** |
| 0x09 | Not found in library | | 0x1A | Invalid register |
| 0x0A | Two scans did not combine | | 0x20 | Address code incorrect |
| 0x0B | PageID beyond capacity | | 0x21 | Password must be verified first |

---

## Notes for GENIE integration

- UART1 on GPIO17/18 avoids the ESP32-S3 USB pins (19/20) and the I2S mic/amp
  pins — no conflict with the existing audio path.
- The R307's 120 mA capture peak on a shared 5 V rail is exactly the sag that
  shows up as I2S crackle. Test fingerprint **and** audio together on the final
  supply before believing either one.
- Blue (touch) on GPIO4 can drive `esp32.wake_on_ext0()` later — the sensor wakes
  the board instead of being polled.
- Both scripts were validated against a simulated R307 that verifies every
  outgoing packet's checksum, so the protocol layer itself is known-correct.
  Anything that fails on the bench is hardware, not the code.

