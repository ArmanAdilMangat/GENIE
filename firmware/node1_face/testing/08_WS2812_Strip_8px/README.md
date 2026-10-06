# 08 — WS2812 Strip (8 pixels)

The real strip, wired and driven. `07_WS2812_LED` is the bring-up test — run that first, then come here.

TFT stays wired. Add **only** the strip.

---

## Wiring

| Strip wire | Goes to | Note |
|---|---|---|
| **DIN / DI** | **GPIO48** (P2-16) | the **arrow-in** end of the strip |
| **GND** | ESP32 GND | and bench supply GND if you use one |
| **5V / VCC** | ESP32 `5V` pin | fine for 8 pixels at `BRIGHT ≤ 60` |

WS2812 strips are one-way. There is an arrow printed between every LED. Wire the end the arrows point **away** from. Get it backwards and nothing lights — no damage, just silence.

### Two parts worth adding

Not required at 8 pixels, but they kill the two most common flaky-strip faults:

- **330–470 Ω** in series on DIN, as close to the first LED as you can get it
- **470–1000 µF** across the strip's 5V and GND at the input end

---

## Run it

```python
>>> import strip
>>> strip.demo()        # every effect once, ~40 s
>>> strip.states()      # walk the six GENIE states
```

---

## Two ways to use it

| Class | Behaviour | Use it |
|---|---|---|
| `Strip` | Blocking. Call an effect, it runs and returns. | Bench only |
| `Status` | Non-blocking. `set()` a state, `tick()` from your loop. | `genie_live.py` |

```python
s = strip.Status()
s.set("thinking")
while True:
    s.tick()            # self-paces at 25 ms, never sleeps
    ...                 # button and sensors stay responsive
```

Anything that calls `time.sleep()` inside the main loop makes the button feel broken. That is what `Status` exists to prevent.

---

## The six states

Defined once in `STATES` so they cannot drift between `genie_live.py`, the TFT face and this file.

| State | Colour | Effect | Means |
|---|---|---|---|
| `idle` | blue | breathe | listening for the wake word |
| `heard` | green | solid | wake word matched |
| `thinking` | yellow | chase | Whisper + Mistral running |
| `speaking` | cyan | breathe | pyttsx3 talking |
| `alert` | red | flash | a sensor tripped |
| `error` | magenta | flash | something threw |

Plus `meter(value)` — a 0.0–1.0 bar graph, green through yellow to red. For the MQ-2, `meter(ratio / 2.0)` puts the 1.50× alarm threshold at three quarters of the strip.

---

## Symptoms

| What you see | Cause |
|---|---|
| All 8 correct in `wheel()` | PASS — no break, no level problem |
| Nothing at all | DIN on the wrong end, wrong pin, or no 5V |
| Red shows green | Strip is RGB not GRB — set `ORDER_RGB = True` |
| Pixel 0 right, rest random | 3.3V data into a 5V part — fit the 330 Ω and the cap |
| Fewer pixels light than expected | Break at that position |
| Board resets when the strip goes white | Brownout — drop `BRIGHT` or move to the bench supply |

---

## The onboard LED

GPIO48 also drives the DevKitC-1's own RGB LED. Its DOUT is not routed anywhere, so the onboard LED and strip pixel 0 sit in **parallel** — both display pixel 0.

The onboard LED mirroring your first strip LED is correct. Do not go looking for a wiring fault.

---

## Power

8 LEDs at full white is roughly 480 mA. `BRIGHT = 60` caps it near 110 mA, which the ESP32's 5V pin carries without complaint. Leave it capped unless you have moved to the bench supply.

Never run a long strip off the ESP32 5V pin. 60 LEDs at full white is 3.6 A and the board browns out well before that.
