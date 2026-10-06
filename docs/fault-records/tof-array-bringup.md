# Time-of-flight array: four working sensors, one array that would not start

**Class:** power (suspected, not proven) · **Decision:** left out of the demonstration unit, 2 September 2026 · **State:** diagnosed, not fixed

## What was proved

| Finding | Evidence |
|---|---|
| All four modules are genuine VL53L1X | Model ID `0xEACC` read individually on every one, across four separate runs |
| All four work alone | Each enabled by itself from a real reset: 4 of 4, across five runs |
| XSHUT wiring is correct | Driving all four lines low silences the entire bus |
| Addresses assign correctly | `0x30`–`0x33` in isolation |
| No real I²C errors | 0 in 200 reads on every sensor that came up — measured at 400 kHz; see the caveat below |

## The failure

Confined to bring-up. The first sensor came up nearly every time. Sensors two, three and four failed non-deterministically — a different one each run, giving one, two or three working sensors out of four — with either `no data ready` or `ENODEV`.

Which error appears is the useful part. `no data ready` is a timeout inside initialisation, *after* the chip has acknowledged on the bus and accepted its full 91-byte configuration block. The link is working and the function is failing: the laser stage never completes a range.

## Hypothesis

The original bring-up called `start()` on each sensor as soon as it had been addressed. Sensor three therefore had to boot and complete its first range while sensors one and two were already pulsing their emitters. The proposed cause is the 3.3 V rail sagging under stacked emitter current, delivered through about 20 cm of dupont wire with no local decoupling at the sensor cluster.

The reasoning that points at the supply and away from everything else: a different random subset of four independent chips failing on each boot cannot be a code defect, which would fail identically every time, nor a wiring fault, which would fail on the same sensor. A supply sitting near its threshold is what gives a different answer on every run.

**This is not proven.** A clean reflash and a revised two-phase bring-up were prepared and never run to a result. The hypothesis is the best fit for the data. It is not a measurement.

## Two things found afterwards

Neither overturns the decision; both narrow the diagnosis.

**The bench measured a configuration the project had already rejected.** The diagnostic instrument defaulted to a 400 kHz bus, and the "clean bus" result was taken there. The firmware on the board had been running at 100 kHz since 27 August, precisely because all four sensors began failing bring-up at the higher speed. The instrument had a speed-sweep test that would have shown this; it was never run to a result. The clean-bus finding means *clean at 400 kHz for the sensors that came up*, not that the bus is sound.

**A radio was on the same rail.** Node 2 sends its readings to the host directly as well as to Node 1, so it associates with Wi-Fi in normal operation. That adds roughly 350 mA of peaks to the supply the sensors draw from — load that was not there when the rail was first validated, and consistent with the hypothesis.

## The one saved measurement

A single calibration file was recovered from the board:

```
name   yield  mode  noise  base  margin
front  0      open  0.0    1200  0.0
left   0      open  0.0    1200  0.0
right  0      open  0.0    1200  0.0
rear   0      open  0.0    1200  0.0
```

A yield of zero means no sensor returned a single valid sample in that run. The base of 1200 is the open-space fallback constant, not a measurement. It records a total failure, and it is included because leaving it out would suggest a partial calibration existed.

## Ruled out

Duplicate addresses, XSHUT wiring, dead or counterfeit parts, and pull-up configuration. An intermediate figure of "800 bus errors" was a counting defect in the bench itself, which scored an uninitialised sensor as a bus error.

## If it is picked up again

1. Set the bus to 100 kHz first, and re-take every result gathered at 400 kHz.
2. Run the cumulative-load test: bring up one sensor and read it, then two, three, four. The count at which the array falls over separates a supply problem from a bus problem in about two minutes.
3. Fit 100 µF and 100 nF across 3V3 and ground **at the sensor cluster**, not at the microcontroller end of the wires.
4. Address all four sensors before starting ranging on any of them, so peak current during the fragile phase stays near idle.
5. Measure 3.3 V at the furthest sensor while all four range. Below about 3.0 V is the fault measured, not inferred.

The bench that does all of this is in [`firmware/node2_presence/bench/final_fault_isolation/`](../../firmware/node2_presence/bench/final_fault_isolation/).

## What the decision touched

- **Enclosure:** nothing. The sensors were to mount internally and the released cut file has no time-of-flight geometry.
- **Frame format:** nothing. The four distance fields stay in the 14-byte frame and carry `0xFFFF`, the existing no-valid-reading value. Changing the frame would have meant re-synchronising both boards days before the demonstration.
- **Host:** presence reads as `unknown`, which the safety layer already treats as neither an alarm nor an all-clear.

## Lesson

A working handshake does not mean a working sensor. The chips answered, identified themselves and accepted their configuration, and still did not range.
