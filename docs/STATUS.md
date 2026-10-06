# Status

What works, what is blocked and by what, and what was never built. The backlog view is from the final project report (September 2026). The sensor-side detail is from the Phase 2 engineering record dated 2 September 2026 and has not been re-verified since.

## Backlog

| ID | Requirement | State | Evidence or blocker |
|---|---|---|---|
| EP1-01 | Zero-configuration UDP discovery | Complete | Wi-Fi uplink suite 21/21; nodes find the host on boot |
| EP1-02 | Separate microphone and speaker nodes | Complete | 1,941 dual-channel recordings captured |
| EP2-01 | Dual-microphone capture, confidence routing | Complete | Both channels transcribed and logged for every utterance |
| EP2-02 | Wake-word-gated listening | Complete | Custom model, 0.65 over 3 blocks |
| EP2-03 | Deterministic-first intent routing | Complete | 362 patterns, 0 duplicates; sensor intents never reach the LLM |
| EP3-01 | Voice-controlled appliance switching | Complete | Spoken command to relay actuation confirmed on hardware |
| EP3-02 | Multi-sensor hazard monitoring | **Partial** | 86 assertions pass. Blocked by the presence array's bring-up fault |
| EP3-03 | Autonomous emergency call and SMS | **Partial** | Sequence exercised against the modem. Blocked by SIM registration; calling disabled — see below |
| EP4-01 | Expressive animated face | **Partial** | Display and face work. The host-to-board emotion channel is plumbed but has not been observed on hardware |
| EP5-01 | Sign-in web dashboard | Not started | — |
| EP5-02 | Battery-powered operation | Not started | — |
| EP6-01 | On-device handling classifier | Complete | Handling-chain suite 18/18 |
| EP6-02 | Session-held-out evaluation | Complete | 72.6 % held out, 88.3 % random split, both reported |
| EP6-03 | Confidence gating | Complete | 0.70 gate: 82.6 % on 77.8 % of windows |
| EP6-04 | Learned model versus rule-based baseline | Complete | MLP, decision tree and hand-tuned FSM all reported |
| EP7-01 | Autonomous climate control | Complete | Switches at the act threshold, releases at the lower one, override holds |
| EP7-02 | Spoken reaction to being handled | Complete | Every FSM event has a spoken line |
| EP7-03 | Follow-up window without a second wake word | Complete | 8 s window, capped at 3 turns |
| EP7-04 | Two-way SMS relay and DTMF acknowledgement | **Partial** | Relay and reply path exercised. Same SIM dependency as EP3-03 |
| NFR-01 | Fully offline operation | Complete | Whole loop exercised with the internet disconnected |
| NFR-02 | Sub-second fall and flame alerting | **Partial** | 50–150 ms through the loop test. Timing on assembled hardware pending |
| NFR-03 | Debounced smoke and presence alerting | Complete | 4 s smoke settle; a latched alarm does not re-fire |
| NFR-04 | A silent sensor never reads as safe | Complete | `unknown` in no alerting set; 24/24 default branches |
| NFR-05 | Automated regression coverage without hardware | Complete | 104 assertions, 5 suites |
| NFR-06 | Zero manual network configuration | Complete | No hard-coded addresses in firmware |
| NFR-07 | Battery-backed operation | Not started | — |
| NFR-08 | Inference inside the face board's loop budget | Complete | 232 parameters, ~800-byte buffer |
| NFR-09 | Model / extractor version guard | Complete | Mismatch raises at import |
| NFR-10 | Autonomous actions explained and overridable | Complete | Every relay change spoken with its cause |

21 complete, 5 partial, 3 not started. Every in-scope requirement has an implementation; what remains is a supply fault, a SIM registration and one unobserved display channel.

## The blockers

**Presence array (EP3-02, NFR-02).** Four VL53L1X modules, each proven genuine and each working alone. Brought up together, a different random subset fails on every boot with either a ranging timeout or `ENODEV`. A deterministic code defect would fail the same way each time and a wiring fault would fail on the same sensor; a supply sagging near its threshold is what gives a different answer every run. That hypothesis is the best fit for the data and it has not been confirmed with a meter. The same rail is implicated in a display reset storm on the face board. Full record: [`fault-records/tof-array-bringup.md`](fault-records/tof-array-bringup.md).

**Cellular module (EP3-03, EP7-04).** The SIM is not registered with the Pakistan Telecommunication Authority's device registry, so the network would block the module after its grace period. Separately, autonomous calling was implemented, shown to work, and then disabled: the module's supply could not hold a 2 A GSM transmit burst without resetting. The emergency path ships as SMS only. The radio was pinned to 2G after LTE-to-GSM handover dropped every call. Re-enabling calling is one configuration flag once the supply is fixed.

**Emotion channel (EP4-01).** The laptop sends an expression after each reply and the firmware accepts it. Nobody has yet watched it arrive on the physical display.

## Sensor nodes

As recorded on 2 September 2026.

| Subsystem | State | Note |
|---|---|---|
| ILI9341 display and face | Working | 118 fps soak, memory stable. A faint flickering line on one panel edge is a known cosmetic defect |
| MQ-2 gas ×2 | Online, uncalibrated | Baselines captured (1943 and 1567 counts). Voltage dividers on the analogue outputs were not fitted, which gates any test with real gas: a saturated 5 V output on a 3.6 V-rated pin |
| Flame | Online, uncalibrated | No false positives in the last recorded run. Trim pot not set, no lighter test recorded |
| DHT11 | Working | Read every 30 s, declared stale after three misses |
| MPU-6050 ×2 | Working | Resting magnitude 1.00 g self-check passed on the bench; not re-run on the final build |
| Fall detection | Algorithm validated, not field-validated | Three-stage signature. Sample-starved on hardware: needs 20 ms, gets about 50 ms because it shares the display loop |
| SW-420 knock ×2 | Working, untrimmed | 11 knocks counted on the top sensor against 7 on the bottom in the last run — suspected chatter, soak test outstanding |
| Push button | Broken in hardware, working through fallback | Soldered across the switch's internally joined pair, so it reads constant 0. Firmware detects this at boot and falls back to keyboard control over serial |
| WS2812 status strip | Working | Run at 4.3–4.5 V so a 3.3 V GPIO meets the logic-high threshold |
| ESP-NOW link, Node 2 → Node 1 | Working | Frame round-trips; link declared down after 4 s of silence |
| VL53L1X array | Not in the demonstration unit | See above |
| Knock patterns on Node 2 | Simulated only | 1, 2 and 3-tap recognition validated against synthetic ring-down bursts; the ten-out-of-ten hardware test was not run |
| R307S fingerprint | Not in the final system | Status contested — see [`fault-records/r307s-fingerprint.md`](fault-records/r307s-fingerprint.md) |

**Known mismatch.** The zone bands that turn a distance into a word are desk-scale in the production path (touch < 40 mm, near < 300, present < 800, far < 1500) and room-scale in the bench tools (100 / 500 / 1500 / 3000). A person two metres away triggers correctly and is then reported as `CLEAR`. The detection is right and the word is wrong; the two band sets need to be made to agree.

## What GENIE must not be claimed to do

| Claim | The defensible version |
|---|---|
| "It detects falls" | It implements a three-stage fall signature, tuned on one person, one surface and one mounting position. No labelled dataset exists, so no sensitivity or specificity can be quoted. As mounted it senses the device falling, not a person |
| "It detects gas" | Baselines are captured and the ratio logic works. The baseline has not been calibrated against a real source |
| "Two vibration sensors localise a knock" | Acrylic carries vibration at about 2,200 m/s — 68 µs across the box. They give redundant, orientation-independent coverage |
| "It can call for help" | It can send an SMS, once the SIM is registered. Calling is disabled |
| "The microphone array beamforms" | It averages two channels. No benefit was measured |

## Next

1. Fit a low-impedance supply to the cellular module and re-test the transmit burst. This is the one remaining test that could reverse the decision to disable calling.
2. Move fall detection off the display loop, or onto a timer, so it gets its 20 ms sample.
3. Add the SW-420 signal to the handling classifier's feature vector — the identified fix for `picked_up`.
4. Measure 3.3 V at the furthest ToF sensor with all four ranging; fit local decoupling at the cluster.
5. Power the gas sensors for 24–48 hours, then record the baseline against a real source.
6. Log the score of every false wake-word activation, then retrain with partial phrases as explicit negatives.
7. Build the two declared gates: the sign-in dashboard and battery operation.
