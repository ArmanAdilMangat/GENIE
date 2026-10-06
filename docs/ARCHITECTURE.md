# Architecture

GENIE is one laptop and six ESP32-S3 boards. The laptop runs every model; the boards own the physical world. This page describes the system as delivered in the final project report (September 2026). For which parts of it are in this repository today, see the scope note in the [README](../README.md).

## Why six boards

A single ESP32-S3 asked to stream two I2S microphones, drive an amplifier, refresh an 8-bit parallel display and poll a dozen sensors runs out of three things at once: pins, memory and supply headroom.

Splitting the work so that each board has one job was the answer to all three. The pin conflicts, resource starvation and brown-outs that motivated the split did not recur once the load was distributed.

## Nodes

| Node | Core hardware | Firmware | Talks to the host over |
|---|---|---|---|
| Microphone | ESP32-S3, 2× INMP441 on one I2S bus in stereo mode, 10 cm apart | Arduino-ESP32 (C++) | TCP, one interleaved two-channel PCM stream |
| Speaker | ESP32-S3, MAX98357A class-D amplifier, 5 W 4 Ω driver | Arduino-ESP32 (C++) | TCP, PCM chunks |
| Relay / IoT | ESP32-S3, active-LOW relay board (light, fan), WS2812 status LED | Arduino-ESP32 (C++) | HTTP `GET /relay?light=<0\|1>&fan=<0\|1>` |
| **Node 1** — face and safety | ESP32-S3 with octal PSRAM, 2.4" ILI9341 on an 8-bit parallel bus, 2× MQ-2, flame sensor, DHT11, 2× MPU-6050, 2× SW-420, push button, WS2812 strip | MicroPython | USB serial at 115200 baud, one JSON object per line; the same lines over a held-open TCP socket when Wi-Fi is up |
| **Node 2** — presence | ESP32-S3, 4× VL53L1X time-of-flight, SW-420 knock switches | MicroPython | ESP-NOW to Node 1, and in parallel a direct TCP line to the host |
| Modem | ESP32-S3, SIMCom A7670E | MicroPython | TCP, a dedicated trigger link |

The Wi-Fi nodes find the host by UDP broadcast on port 9999, so no address is written into any firmware and a new DHCP lease needs nothing reflashed.

## The two paths

The single most important decision in the design is that safety never travels through the slow path.

**Path A — safety.** A flame reading is confirmed on Node 1 by three agreeing polls; a fall by a free-fall, impact, stillness sequence. Only then is a line emitted. On the host, one watcher owns the decision to raise an alert: it acts on the rising edge, applies a per-sensor debounce (0 s for flame and fall, 4 s for smoke, about 6 s for presence), and arms a 600 s cooldown so one smoke event cannot ring a phone twice. Speech recognition and the language model are not involved at any point.

**Path B — conversation.** Wake word, capture, transcription, intent routing, synthesis. Eight to fifteen seconds end to end on a consumer laptop. Acceptable for "what is the temperature", unacceptable for a fire — which is why Path A exists.

## Host pipeline

Two operating-system processes, so that a slow transcription or model call cannot starve microphone capture.

| Stage | What it does | Detail that matters |
|---|---|---|
| Capture | De-interleaves the stereo stream, high-pass filters, applies gain | The two microphones share an I2S clock, so the channels are sample-synchronous with no alignment step |
| Wake word | openWakeWord with a custom "Hey Genie" model exported to ONNX | A score above 0.65 must hold for three consecutive 80 ms blocks. One block below resets the count. This rejects knocks and single syllables without raising the threshold and losing range |
| Voice activity | webrtcvad at aggressiveness 3 combined with an RMS floor | Neither is sufficient alone: the detector calls quiet room noise speech, and a level floor cannot tell a bang from a word |
| Transcription | Faster-Whisper base, int8, both channels independently | The channel with the higher `avg_logprob` is forwarded. Clarity and volume are not the same thing |
| Intent | AIML patterns first; Mistral-7B under Ollama only for unmatched, non-sensor queries | Sensor questions never reach the model, and its system prompt forbids reporting a reading, so it cannot invent "no smoke detected" |
| Synthesis | Piper, streamed to the speaker node | A memoryless waveshaping curve narrows the peak-to-average gap so chunked streaming has no seams |
| Follow-up | Eight-second window after GENIE speaks in which speech alone opens a capture | Capped at three chained turns. The cap is a structural guarantee against acoustic feedback; a timing margin would only be a probabilistic one |

Around the pipeline sit three watchers, each asking a different question of the sensor state:

- `sensor_watch` — *is something bad?* Edge-triggered, debounced, cooled down. Raises alerts and triggers the modem.
- `climate_watch` — *should the fan be on?* One decision over all readings, two thresholds per condition (act at 32 °C, release at 26.5 °C; act at 70 % RH, release at 67 %). Every relay change is spoken with the reading that caused it, and a spoken override holds until the situation itself changes.
- `reaction_watch` — *did something just happen?* Drains an append-only event log with a cursor, speaks only the newest handling event, and drops a reaction outright if GENIE is already talking.

## On-device classifier

The only inference that does not happen on the laptop.

Node 1 pushes each accelerometer sample into a fixed ring buffer of 50 magnitudes and 50 tilts — about 800 bytes, no allocation per window. Every 10 samples a window closes and yields 16 features. A 14→12→4 multilayer perceptron, stored as 232 plain numbers with frozen standardisation constants, classifies it in pure MicroPython: no TensorFlow Lite, no NumPy, no custom firmware build. Below a softmax confidence of 0.70 the board emits nothing.

One file computes the features, and both the board and the training script import it. Training and serving therefore cannot compute features differently, and a version stamp checked at import makes a mismatched model refuse to load. A hand-tuned finite-state machine producing the same events is kept alongside as the baseline the learned model has to beat.

## Sensor nodes in detail

Node 1 is a single cooperative loop — MicroPython has no threads — with 33.3 ms per frame at 30 fps.

| Operation | Cost |
|---|---|
| Both eyes | 15.6 ms |
| Full sensor strip repaint | 14.1 ms |
| One value field | 2–4 ms |
| All sensor reads together | about 1.6 ms |

Text repaints cost frames and sensor reads do not, so the rule that holds the frame rate is repaint discipline: a value is redrawn only when its rendered string changes. Nothing in the loop may block. That is why the time-of-flight sensors, whose ranging call waits about 100 ms, live on a second board and arrive as finished numbers.

Node 2 sends its readings two ways at once: ESP-NOW to Node 1, so distances can be drawn on the face and folded into its telemetry, and a direct TCP line to the host, so the array keeps reporting while the face board is off or being reflashed. Both boards join the same access point, which is what keeps them on the same radio channel — ESP-NOW and Wi-Fi share one radio, and a channel mismatch drops every frame without an error on either side.

The frame and telemetry formats are specified in [`PROTOCOL.md`](PROTOCOL.md).

## Rules the design holds to

- **The absence of a reading is not a reading.** A disconnected or failed sensor reports `unknown`. It belongs to no alerting state, so it cannot raise an alarm, and every conditional in the spoken-answer file has a default branch, so it cannot produce an all-clear.
- **Zero is a measurement.** A failed distance read is encoded as `0xFFFF`, never `0`, because zero is exactly what an object pressed against the lens returns.
- **Alarms outrank the host.** An expression pushed from the laptop expires after 20 seconds, and a gas, flame or fall alarm overrides it immediately. If the host process dies, the face must not sit smiling through a gas leak.
- **One owner per measurement.** The two sensor boards never read the same physical quantity. Two boards reporting room temperature is how two different numbers end up on one screen.
- **Contracts are files, not conversations.** The ESP-NOW frame is a single module uploaded to both boards. Its size is computed from its format string.

## Emergency escalation

On a confirmed alert the modem node sends an SMS naming what happened, then opens a 45-second window for an acknowledgement before dialling. During a call the contact can press 1 to acknowledge or 2 to pass the alert to the next contact. Once triggered, the modem node completes the sequence on its own; only the spoken announcement in the room needs the host.

Inbox polling for remote SMS commands is suspended for the duration of an alert. Both readers consume the same unread list, and an acknowledgement answered by the language model instead of cancelling the call is the failure this prevents.

The state of this path on hardware is in [`STATUS.md`](STATUS.md).
