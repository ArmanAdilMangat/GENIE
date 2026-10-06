# 04 — SW-420 Vibration / Knock (x2)

TFT stays wired. Add **only** the two SW-420 modules.

| Signal | GPIO |
|---|---|
| top DO | 41 (P2-7) |
| bottom DO | 40 (P2-8) |
| VCC | 3V3 rail |

```python
>>> import test_sw420
>>> test_sw420.run()
```

## The SW-420 chatters

It is a rolling-ball switch, not an accelerometer. One tap produces a **burst** of edges. Anything counting raw edges over-counts by 5–20x. `test_sw420.py` debounces in the ISR with a 120 ms window — that is what makes the count mean anything.

Tuning `DEBOUNCE_MS`:

- one firm tap adds 3–4 → raise it
- two deliberate taps add 1 → lower it

A count of zero on one module means it never fired: turn that module's pot counter-clockwise for more sensitivity and re-run.

Floating pin = power or wiring. Never the pot.
