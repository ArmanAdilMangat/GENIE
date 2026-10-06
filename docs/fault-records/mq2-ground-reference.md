# MQ-2: one wire, forty times less noise

**Class:** power · **Solved:** 21 August 2026 · **State:** fixed

## Symptom

The gas sensors' readings in clean air were unusable in two successive ways.

First they were **bimodal**: the raw value flipped between two states with nothing changing in the room.

After that was fixed they were merely **noisy**: 1713 to 2972 counts in still, clean air — about ±25 %. An alarm threshold set at 1.5 × baseline has no meaning on a signal that moves by 1.7 × on its own.

## Cause

The MQ-2's analogue output is a voltage, and a voltage means something only relative to a reference. The reference is the microcontroller's own ground pin, because that is what its converter measures against.

**Stage one — no common ground.** The 5 V bench supply feeding the heaters was not tied to the microcontroller's ground at all. The converter had no shared reference, and the reading sat wherever stray coupling left it.

**Stage two — a common ground with the wrong path.** Once the grounds were joined, the sensor's ground reached the microcontroller only the long way round: through the LED strip's return path and the supply. Every milliamp the strip drew shifted the sensor's ground relative to the chip's, and the converter faithfully reported the difference.

## Fix

One wire: the microcontroller's ground run directly to the junction where the sensors and the supply meet.

| | Before | After |
|---|---|---|
| Spread in clean air | about ±25 % | about ±0.5 % |
| Typical reading | ~2300 counts | ~840 counts |

A forty-fold improvement. The drop in the absolute reading is as informative as the drop in noise: most of the old number was ground offset, not gas.

## Why it is easy to miss

The wire is invisible on a schematic that shows a single "GND" net. Electrically the grounds were connected in both arrangements. What changed is which currents share the path.

## Still open

- A 10 k / 20 k divider on each analogue output was not fitted at the time of the engineering record. A saturated output would put 5 V on a pin rated for 3.6 V, so testing with real gas was held back.
- An occasional 3–5 % single-sample spike remains. 100 nF from each analogue pin to ground at the microcontroller end would remove it: the output impedance is tens of kilohms and the converter's sampling capacitor cannot refill from that in the time it has.
- The heaters need 24–48 hours powered before a baseline is worth recording.

## Rule

Common ground has a path, and the path matters. For an analogue signal, run the reference directly.
