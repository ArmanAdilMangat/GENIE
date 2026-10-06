# R307S fingerprint reader: condemned, then contradicted

**Class:** component · **State:** unresolved; not part of the final system

The fingerprint reader is the best-evidenced subsystem in the sensor work and also the one whose final status the record cannot settle. Both halves are written down here.

## Timeline

| Date (2026) | Event |
|---|---|
| 8 August | First full bring-up. System parameters read with a verified checksum: capacity 1000 templates, security level 3, 128-byte packets, 57600 baud. Finger detection working |
| 8–15 August | Supply rails reorganised |
| 15 August | Handshake refused |
| 24 August | Rebuilt on the 5 V rail with a common ground: 5.2 V measured at the module, handshake restored, parameters byte-for-byte identical to 8 August. Capture then failed across 140 consecutive polls. Module condemned |
| 25 August | Decision: no replacement. It was not one of the project's remaining gates, and a shipping delay on a non-gate part days before a demonstration was the wrong trade |
| 29 August | A fresh two-stage verification suite written to settle the question independently |
| 2 September | An event log recovered from the board records one enrolment and matches at scores 87 and 165 |

## The fault tree behind the condemnation

Every layer above the suspected part was proved healthy before the part was blamed.

| Test | Result | Conclusion |
|---|---|---|
| Supply measured at the module | 5.2 V, stable | Power confirmed, not inferred |
| Both UART lines proved driven | Read against an internal pull-down | Wiring is real |
| Baud and pin-order sweep | Five rates × two orders | Configuration space exhausted |
| Protocol | Password verify, parameter read and ring control all returned success | Controller functional |
| Parameter reproducibility | Identical to the 8 August baseline | No drift or corruption |
| Indicator ring | Lit on command | The module's LED driver works |
| Capture illuminator | Did not fire across 140 consecutive image requests, in a dim room, on clean glass, with a moistened finger | Capture path dead |

The observation that isolated it: the indicator ring lit and the capture illuminator did not, and the same controller drives both.

## The evidence that points the other way

A log pulled off the board on 2 September shows a user enrolled and matched. A working capture path is exactly what the 24 August diagnosis said did not exist. The pin-configuration file from the same board still carries a block headed "DEAD SECTION".

These cannot both be right, and the files alone do not say which is. The log has not been reproduced under observation. Until it is, the honest position is that the module was condemned on good evidence and that later evidence contradicts it.

The instrument for settling it is in [`firmware/r307s_fingerprint/`](../../firmware/r307s_fingerprint/): a life-check that sweeps every legal baud rate in both pin orientations with a full hex dump, then a health test covering enrolment, search, a 200-packet soak, flash verification and image quality. Its pass criteria are strict on purpose — anything less is "it works today", not "it works".

## Faults found and fixed along the way

| Fault | Cause and fix |
|---|---|
| Silence on first bring-up | The 3.3 V touch-supply and touch-output conductors were swapped; these two are commonly documented backwards. Pin order was re-established from the PCB |
| Image transfer hangs at about half | The image is 256 × 288 pixels but only 36,864 bytes cross the wire — two pixels per byte. A script waiting for 73,728 bytes waits forever, which looks exactly like a wiring fault |
| Last image row missing | The end packet has a different identifier but carries real image data. The loop exited before appending it |
| Memory exhaustion | A 73 KB buffer held in RAM; replaced by streaming to a file |
| First command silently dropped | The driver spoke to the module immediately. It needs a few hundred milliseconds after any power or line disturbance |
| Five false "alive" verdicts on a reversed pin order | See below |
| A 200-byte blob before an acknowledgement | Image data left in the module's output queue by a previous session. A soft reboot resets the microcontroller, not the peripheral |

### The packet echo

A probe reported the module alive on five configurations, including a reversed pin order that cannot work. Everything "received" on the reversed order was the packet just transmitted, byte for byte: the ESP32-S3 pin matrix had not fully released a GPIO from its previous role as a UART transmit pin, so the peripheral was hearing itself.

The tell is byte 6, the packet identifier. `0x01` is a command — ours. `0x07` is an acknowledgement — the module's. All five false replies carried `0x01`. The validator now requires `0x07` before accepting anything as a reply.

## Design note

Template matching runs on the module's own processor and templates live in its own flash. The microcontroller only ever learns "slot 7 matched, score 152". No biometric data leaves the sensor, and none is in this repository.

## Lesson

A working handshake does not mean a working sensor — and a diagnosis, however carefully built, is still a claim that later evidence can overturn. Write down both.
