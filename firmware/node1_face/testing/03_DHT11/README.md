# 03 — DHT11 Temperature / Humidity

TFT stays wired. Add **only** the DHT11.

| Signal | GPIO |
|---|---|
| DATA | 21 (P2-18) |
| VCC | 3V3 rail |

Bare 3-pin sensor needs a 4.7k–10k pull-up from DATA to 3V3. The 4-pin breakout already has one.

```python
>>> import test_dht11
>>> test_dht11.run()
```

## `OSError(116,)` = ETIMEDOUT

Causes, in order of likelihood:

1. Reading faster than **once per 2 s**. The DHT11 will simply not answer. This is the cause about 70% of the time.
2. No pull-up on DATA.
3. DATA on the wrong pin.
4. Sensor wants 5V — most take either, a few insist.
5. Dead sensor.

Idle DATA should read **held high**. Floating means no pull-up and no module.

4–5 reads out of 5 = PASS. Intermittent is almost always the pull-up or a long unshielded DATA wire — shorten it.
