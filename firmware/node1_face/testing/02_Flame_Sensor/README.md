# 02 — Flame Sensor (IR, digital out)

TFT stays wired. Add **only** the flame module.

| Signal | GPIO |
|---|---|
| DO | 42 (P2-6) |
| VCC | 3V3 rail |

```python
>>> import test_flame
>>> test_flame.run()
```

**DO is active low.** 0 = flame, 1 = clear.

| pin state | means |
|---|---|
| floating | module unpowered or signal wire out — **not** a sensitivity problem |
| driven high | module present, no flame — correct idle |
| driven low | module present, sees flame, or the pot is maxed |

A floating pin is never fixed by turning the potentiometer. Check 3V3 and GND **at the module pins** first.

Test: a lighter at ~20 cm should trip it instantly. If it never trips, turn the pot until the module's second LED just goes out with no flame present — that is the threshold.
