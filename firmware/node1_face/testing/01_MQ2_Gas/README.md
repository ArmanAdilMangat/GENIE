# 01 — MQ-2 Gas / Smoke (x2)

TFT stays wired. Add **only** the two MQ-2 modules.

| Signal | GPIO | Rail |
|---|---|---|
| MQ-2 #1 AO | 1 (P2-4) | VCC 5V bench |
| MQ-2 #2 AO | 2 (P2-5) | VCC 5V bench |

```python
>>> import test_mq2
>>> test_mq2.run()      # check -> 90s warm-up -> baseline -> live
>>> test_mq2.check()    # just the channel sanity check
```

## Non-negotiable

- **Common ground.** Bench supply GND must tie to ESP32 GND. Without it the ADC has no reference and readings flip between two levels for no reason. This was the "bimodal" fault — it was never the sensor.
- **GPIO1/GPIO2 only.** They are the only usable ADC1 pins. ADC2 (GPIO11–20) returns garbage whenever WiFi or ESP-NOW is running.
- **90 s warm-up from cold.** The heater drifts the whole time. Nothing you read before it ends means anything.

## Reading the output

| raw | means |
|---|---|
| < 60 | AO not connected, or module has no 5V |
| 60 – 3040 | plausible, linear region |
| > 3040 | ADC saturated — fit the 10k/20k divider |

Ratio is against the clean-air baseline: 1.20x = alert, 1.50x = alarm. Hold an **unlit** lighter near a module and release gas — the ratio should climb past 1.20 in a couple of seconds.
