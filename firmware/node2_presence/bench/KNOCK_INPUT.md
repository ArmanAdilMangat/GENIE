# Vibration sensors — knock and tap input

MicroPython on ESP32-S3. SW-420 style modules with a digital DO output.

Purpose: the user taps a surface to issue a command. Single / double / triple
tap are distinguished. This is a genuine accessibility win for GENIE — a tap on
a bedrail works when speech doesn't.

## Wiring

| Module pin | Goes to |
|---|---|
| VCC | 3V3 |
| GND | GND |
| DO | GPIO14 / 15 / 21 / 47 |

Do not use the AO (analogue) pin. ADC2 is dead whenever ESP-NOW is running, and
DO with the on-board comparator is the right tool anyway.

## Tune the hardware first

Each module has a **potentiometer** — that is your primary sensitivity control.
Set it before touching any code:

1. Run `knock.py` (F5).
2. Turn the pot until a firm tap on the mounting surface reliably registers and
   normal desk bumps do not.
3. Only then adjust `DEBOUNCE_MS` / `PATTERN_MS`.

Software cannot rescue a pot set to maximum sensitivity — you'll get continuous
false triggers from the LED strips switching, from your own footsteps, and from
the ESP32's own WiFi bursts.

## Why the code is not just `pin.value()`

A vibration module does **not** give one clean pulse per tap. One physical knock
produces a burst of 5–40 edges over ~30 ms as the spring or piezo rings down.
Read the pin naively and a single tap reports as eight taps.

The chain here is:

```
physical knock
   → burst of edges          (hardware reality)
   → IRQ + DEBOUNCE_MS       collapses the burst into ONE tap
   → PATTERN_MS silence      closes the pattern
   → 1 / 2 / 3 taps          the command
```

## The three numbers

| Constant | Default | Raise it when | Lower it when |
|---|---|---|---|
| `DEBOUNCE_MS` | 40 | One tap reports as 2+ | Fast deliberate taps get merged |
| `PATTERN_MS` | 500 | A double tap splits into two singles | Patterns feel sluggish to confirm |
| `ACTIVE_LOW` | True | — | Your module idles low and pulses high |

Check `ACTIVE_LOW` first. Most SW-420 boards pull DO **low** on vibration, but
some clones invert it. If nothing ever registers, flip this before anything else.

## Verified behaviour

The debounce and pattern logic was simulated against realistic ring-down bursts
(12 edges over 30 ms, and a violent 40-edge case) before hardware:

| Input | Reported |
|---|---|
| One knock | `single` |
| Two knocks 200 ms apart | `double` |
| Three knocks | `triple` |
| Two knocks 900 ms apart | `single`, `single` |
| Violent 40-edge ring-down | `single` |

## Use from other code

```python
from knock import make_all, describe
sensors = make_all()
while True:
    for s in sensors:
        n = s.poll()          # None until a pattern completes
        if n:
            print(s.name, describe(n))
```

`poll()` must be called regularly from the main loop — the ISR only timestamps
edges, it never blocks or allocates. Keep the loop free of long `sleep()` calls
or patterns will close late.

## Symptoms → causes

| Symptom | Cause |
|---|---|
| Nothing ever triggers | `ACTIVE_LOW` wrong, or pot turned fully insensitive |
| Constant triggering with no touching | Pot too sensitive; also check the module isn't resting against the LED strip supply wires |
| One tap counts as many | Raise `DEBOUNCE_MS` |
| Double tap splits into two singles | Raise `PATTERN_MS` |
| Works alone, false-triggers when LEDs run | WS2812 current spikes coupling into the DO line. Separate the wiring, add 100 nF from DO to GND at the module |
| Patterns report late | Main loop blocked — something else is sleeping too long |
