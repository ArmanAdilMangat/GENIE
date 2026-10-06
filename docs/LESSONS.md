# Lessons

The traps this project already paid for, grouped by the kind of mistake. A fault that costs two days usually belongs to a category that will cost two days again.

## Method

**A working handshake does not mean a working sensor.** A fingerprint module answered every protocol command, reproduced its factory parameters byte for byte and lit its indicator ring while failing to capture an image. Four ranging sensors acknowledged on the bus and accepted their full configuration, then never completed a range. Subsystems fail independently. Test the function, not the link.

**Condemn hardware only after electrical proof.** In order: voltage measured at the load, not at the supply; both signal lines proved driven; ground continuity under 1 Ω; the full parameter space swept. Then, and only then, call the part faulty.

**A plain input read cannot prove a wire is connected.** A floating pin holds residual charge and reads high. Configure it with an internal pull-down and read again: only a pin that still reads high has a real external pull-up or driver on it. This one test localised a dead I²C bus to a single broken jumper.

**An instrument is not exempt from testing.** A diagnostic bench scored an uninitialised sensor as a bus error and reported 800 of them; the real figure was zero. The same bench defaulted to a bus speed the firmware had already abandoned, so its headline result was true and misleading at once. Configure the instrument from the system as built.

**Trust the computed size, never the comment.** Two files each carried a comment stating a packet size. Both were wrong, and nobody ran `struct.calcsize()`.

## Wiring

**Read every label; never count pads.** A display shield's data pins were not in numeric order. The code ran, no error appeared, the screen stayed white. Two days.

**Dupont wires break inside the insulation.** They look perfect and test dead, usually at the strain point by the crimp. Replace the wire; do not re-seat it. Root cause twice.

**Breadboard power rails are split in the middle.** Feed one half, draw from the other, and the circuit is correct and unpowered.

**Transmit goes to receive.** Straight-through serial wiring produces a module that is powered, healthy and completely deaf, with no diagnostic. Recorded separately for three different modules.

## Power

**Common ground has a path, and the path matters.** An analogue sensor whose ground reached the microcontroller only through an LED strip's return read ±25 % in clean air. One direct wire brought that to ±0.5 %.

**A rail is validated only under its real load.** The supply was proven before the radio was enabled. The radio added 350 mA peaks.

**Backlight power and controller power are separate.** A display glows white with its controller unpowered, which looks identical to a dead bus.

**A supply fault can look like a protocol fault.** A cellular module with an inadequate supply answers every command and registers on the network, then vanishes the moment it transmits.

## Buses and platform

**An empty I²C scan is ambiguous.** "Not wired", "not powered" and "one device holding the bus low" all return the same nothing. Check the idle line levels first.

**One pull-up pair per bus.** Four breakout boards each with their own pull-ups make a bus too stiff to drive. The signature: works with one or two devices, fails at three or four.

**ESP-NOW and Wi-Fi share one radio.** A board associated to an access point is locked to its channel; one that is not sits wherever it was left. Mismatched, every frame is dropped silently. The fix is not to pin a channel by hand — that works until the router reboots — but to have both boards join the same network.

**Some silkscreen pins are not general-purpose.** GPIO 33–37 are wired to the PSRAM die on octal modules. Using one produces crashes that send the investigation to the power rail.

**ADC2 lies when the radio is on.** It does not error.

**Nothing goes in front of a time-of-flight lens.** Not tape, not clear acrylic, not the film it ships with. The emitter's light reflects into the receiver and the sensor reports a fixed short distance. A baseline under 150 mm with near-zero noise means the lens is obstructed.

## Software

**MicroPython is not CPython, and only fails on the device.** `str` has no `rjust`, `ljust`, `center` or `zfill`; `%` formatting has no dynamic width. Desktop tests pass and the board raises.

**A soft reboot resets the microcontroller, not the peripheral.** Sensors keep their state and their transmit queues; LEDs keep their last colour. Synchronise on a known header and never assume the first byte is the start of a packet.

**An autostarting board must never retry in a loop.** A `main.py` that catches its own startup error and tries again fills the console faster than anyone can type and locks out the REPL. Three-second grace period, one attempt, full traceback, stop.

**Nothing in a shared loop may block.** One cooperative loop drives the display, the sensors and the link. A blocking receive, an HTTP post, a ranging call — each is a frozen face.

**Whenever the signal a threshold applies to changes, recalibrate the threshold.** Detection levels tuned on one microphone were applied to the average of two, which silently made them stricter and cut commands off mid-sentence.

**Shared state needs a rule about who may write nothing.** Two components wrote the same sensor state; one correctly reporting that it had no data erased live readings from the other.

## Mechanical

**A hole a part must enter gets clearance over a verified measurement.** Never a nominal match, never a number from memory. A microphone hole went Ø9, Ø11, Ø12 and failed three times; the module measured 13.1–14.4 mm.

**Where a measurement is disputed, err to the recoverable side.** A hole slightly too large is fixed with foam tape. One slightly too small cannot be fixed.

**Cut the test card first.** The first full sheet was cut before a single component had been offered up to a hole. It cost a sheet and about a week.

**No part smaller than about 40 mm.** Small pieces fall through the laser bed.
