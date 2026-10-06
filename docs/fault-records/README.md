# Fault records

Faults met on real hardware, written up with what was observed, what was proved, and where the evidence stops. A component removed for a stated reason is an engineering decision; one that quietly disappears is a gap in the record.

| Record | Class | Outcome |
|---|---|---|
| [ESP-NOW frame size](espnow-frame-size.md) | Protocol | Fixed so that it cannot recur |
| [Time-of-flight array bring-up](tof-array-bringup.md) | Power (suspected) | Diagnosed, not fixed; array left out of the demonstration unit |
| [R307S fingerprint reader](r307s-fingerprint.md) | Component | Condemned, then contradicted by later evidence; not in the final system |
| [MQ-2 ground reference](mq2-ground-reference.md) | Power | Fixed with one wire |
| [Display data pin order](tft-data-pin-order.md) | Wiring | Fixed; rule recorded |

Two of these are the same fault in different subsystems: a device that answered every command perfectly while the physical function behind it did not work. Recognising the pattern the second time took hours, not days.

## Summary of smaller faults

| Fault | Class | State |
|---|---|---|
| Single broken SDA jumper killing an I²C bus | Wiring | Fixed. Found with the pull-down test, once the right test was used |
| Floating pin misread as connected | Method | Technique adopted: read against an internal pull-down |
| Dupont wire fractured inside the insulation | Wiring | Fixed. Root cause twice |
| UART packet echo on a reversed pin order | Protocol | Fixed. Replies are validated on the packet-identifier byte, not on a non-empty buffer |
| Residual peripheral queue after a soft reboot | Protocol | Fixed. Synchronise on the header |
| Fingerprint handshake lost after a 3V3 / 5 V rail rework | Power | Fixed. Supply restored and measured at the module |
| LED strip current coupling into a knock-sensor line | Power | Fix specified: separate the runs, 100 nF at the module |
| Push button soldered across its internally joined pair | Assembly | Fallback in place; detected at boot |
| Zone hysteresis gated on the zone being entered, not the one being left | Logic | Fixed. It had created a dead band no reading could enter |
| Partial file upload causing an import error | Process | Fixed. Every module carries a version and boot prints a manifest |
| Wrong MicroPython build on an octal-PSRAM module | Platform | Fixed by reflashing the correct build |
