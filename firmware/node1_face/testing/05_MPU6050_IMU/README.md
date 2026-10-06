# 05 — MPU-6050 IMU (x2, one I2C bus)

TFT stays wired. Add **only** the two IMUs.

| Signal | GPIO |
|---|---|
| SCL | 38 (P2-10) |
| SDA | 47 (P2-17) |
| VCC | 3V3 rail |

| Module | AD0 | Address |
|---|---|---|
| top | GND | 0x68 |
| bottom | **3V3** | 0x69 |

```python
>>> import test_mpu6050
>>> test_mpu6050.run()
```

## The one mistake that costs an hour

Forget the bottom module's AD0 → 3V3 wire and **both** answer at 0x68. The scan shows one device and you go looking for a dead sensor that is not dead. `check()` calls this out explicitly when only one address answers.

## Pull-ups

Both modules carry their own 4.7k to 3V3. SDA/SCL reading **floating** means no module has power — check 3V3 before anything else. Do **not** add your own pull-ups on top: four in parallel is 1.2k and the bus starts failing at 400 kHz.

## Sanity

Flat on the desk, `|a|` should read 1.00 g on both. Tilt one module and only its numbers should move. If both change together you are reading one module twice — AD0 again.
