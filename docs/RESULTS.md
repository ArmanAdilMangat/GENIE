# Results

Figures on this page come from the results chapter of the project report (September 2026). Display and sensor-bench figures come from the Phase 2 engineering record (2 September 2026). Nothing has been rounded up, and where something was not measured the page says so.

## On-device handling classifier

The one inference stage with a formal, reproducible accuracy measurement.

**Data.** Two recording sessions on two different days, with the board remounted in between: 1,532 labelled feature windows (853 on 28 August, 679 on 1 September). A window is 50 consecutive accelerometer samples, and a new one starts every 10, so consecutive windows share 80 % of their samples.

| Class (after merge) | Windows | Share | Performed classes merged in |
|---|---|---|---|
| contact | 766 | 50.0 % | tapped, pushed, turned |
| idle | 275 | 17.9 % | — |
| picked_up | 247 | 16.1 % | — |
| shaken | 244 | 15.9 % | — |

**Accuracy.**

| Evaluation | Model | Test windows | Accuracy | Read it as |
|---|---|---|---|---|
| Random split | Decision tree, depth 6 | 383 | 84.1 % | Optimistic |
| Random split | MLP 14-12-4 | 383 | 88.3 % | Optimistic |
| **Session held out** | **MLP 14-12-4** | **679** | **72.6 %** | Trained on session 1, tested on a session it never saw |

The 15.7-point gap is the overlap effect made visible. A window in a random test split can share 40 of its 50 samples with a training window, which makes that score closer to a memory test than a generalisation test. Quoting it would have overstated the headline by more than fifteen points.

**How 31.4 % became 72.6 %.** The first held-out measurement, on the six classes as recorded, was 31.4 % against a 16.7 % chance level. Each improvement came from a diagnosis, not from tuning.

| Change | Reason | Held-out accuracy |
|---|---|---|
| Drop `tilt_mean` | It moved from 85.3° to 78.1° when the board was remounted — two standard deviations, while every other feature stayed inside 1.2 — so 107 of 108 idle windows were misclassified | 53.2 % |
| Drop `acc_mean` | Absolute-valued for the same reason. Every remaining feature is a spread, a difference or a rate, and means the same thing at any mounting angle | 54.6 % |
| Merge tapped, pushed, turned | Rotating the board flat on a desk does not change its angle from flat, so no feature can see it; tapped depends on a per-sample jerk measure that shifted when the loop ran about 8 % slower in session 2 | 72.6 % |

**Confusion matrix, held-out session.**

| Actual ↓ / Predicted → | contact | idle | picked_up | shaken | Recall |
|---|---|---|---|---|---|
| contact | 302 | 7 | 29 | 11 | 86.5 % |
| idle | 16 | 87 | 5 | 0 | 80.6 % |
| picked_up | 72 | 10 | 26 | 0 | 24.1 % |
| shaken | 36 | 0 | 0 | 78 | 68.4 % |

`picked_up` is the weak point, and the cause is a missing sensor, not a missing layer. An accelerometer cannot separate "in a hand, held fairly still" from "on a desk, being touched". A surface-contact signal can: the SW-420 switches hear the desk and go quiet the moment the unit leaves it. Both are fitted to the board and neither is in the feature vector yet. Adding them is the single most valuable change available to this model.

**Confidence gate.**

| Gate | Windows answered | Accuracy when it answers | Left silent |
|---|---|---|---|
| None | 100 % | 72.6 % | 0 % |
| 0.60 | 85.3 % | 79.6 % | 14.7 % |
| **0.70 (shipped)** | **77.8 %** | **82.6 %** | **22.2 %** |
| 0.80 | 69.2 % | 85.5 % | 30.8 % |

0.70 buys ten accuracy points for a fifth of the windows. A device that stays quiet is safe; one that reacts to the wrong thing is not.

**Cost on the device.**

| Property | Value |
|---|---|
| Architecture | 14 inputs → 12 hidden (ReLU) → 4 outputs (softmax) |
| Parameters | 232, stored as plain Python lists |
| Runtime | None. Pure MicroPython — no TensorFlow Lite, no NumPy, no custom firmware |
| Working memory | One fixed ring buffer, about 800 bytes, no per-window allocation |
| Vector rate | Stable across six consecutive recordings (17, 16, 16, 16, 16, 16) with the display loop running |
| Guard | Feature version checked at import; a mismatched model refuses to load |

**Limits of this result.** One unit, one mounting position, a small set of operators, two days. The dataset is imbalanced after merging (766 contact against 244 shaken), which flatters overall accuracy relative to per-class recall — hence the matrix above. The features depend on the board's loop rate, so changing the display frame rate means recording the data again.

## Speech front end and intent layer

No formal word-error-rate or false-accept-rate evaluation on a held-out audio corpus was carried out, and none is claimed. What exists is configuration, data volume and structural coverage.

| Stage | Measured | Result |
|---|---|---|
| Wake word | Training data and gate | 242 clips from 5 speakers. Fires on 3 consecutive 80 ms blocks above 0.65; the block count was raised from 2 after false accepts persisted |
| Wake word | Bench test, one speaker on axis | Score 0.94 at 1 m; a partial phrase ("Genie") peaked at 0.57 and did not trigger; no trigger in three minutes of unrelated conversation in that test; 9/10 detections at 2 m, 6/10 at 3 m |
| Wake word | Known weakness | Roughly one false activation per minute in a room with ongoing conversation. About one miss in ten at half a metre |
| Voice activity | Gate design | webrtcvad at aggressiveness 3 with a per-frame RMS floor of 275 |
| Recognition | Rejection behaviour | Faster-Whisper base / int8. Segments above `no_speech_prob` 0.6 or below `avg_logprob` −1.0 are discarded |
| Intent routing | Structural scan | `sensor.aiml`: 335 categories, 335 unique patterns, valid XML. `relay.aiml`: 27 categories. 0 duplicates across 362 patterns. All 24 conditional blocks carry a bare default branch |
| Corpus | Real audio processed | 1,941 recordings captured through the full wake-word and voice-activity chain |

**Beamforming — a negative result.** Delay-and-sum across the two microphones was measured for detection range and false-accept rate and produced no improvement that could be demonstrated on either. With 10 cm spacing and no delay compensation the array favours sound from directly in front and comb-filters sound from the side (first null at 6.6 kHz at 15° off axis, 1.7 kHz at 90°). It is recorded as unproven.

## Correctness

Five automated suites, all runnable with no board attached. The table is the report's. Only the first row can be re-run from this repository: the other four suite files were not in the code it was assembled from.

| Suite | Proves | Assertions |
|---|---|---|
| Bridge self-tests | Board-to-API field translation in isolation | counted below |
| Sensor integration | Alert policy end to end: edge detection, per-sensor debounce, cooldown, unknown versus clear | 51 |
| Wire loop | The real firmware emitter → a fake serial port → the real reader → the real bridge → the real API | 14 |
| Wi-Fi uplink | The telemetry path against a real socket | 21 |
| Handling chain | Every handling event the board can emit has a spoken line and is accepted by the API; unknown events yield silence | 18 |
| **Total** | | **104 passing** |

The wire-loop suite is the one that matters most. Every other test checks one side against a hand-written example of what the other side sends — which is precisely how the [ESP-NOW frame-size fault](fault-records/espnow-frame-size.md) survived. The wire loop never writes a protocol line by hand: the bytes come from the emitter that runs on the board and are read by the reader that runs on the laptop.

**Structural invariants checked against the source.**

| Invariant | Why it matters | Verified |
|---|---|---|
| Every conditional in the spoken-answer file has a default branch | An unreadable sensor cannot produce silence or a false all-clear | 24 of 24 |
| No duplicate AIML patterns | A duplicate silently shadows the earlier category | 0 in 362 |
| `unknown` appears in no alerting state set | A dead sensor can neither raise an alarm nor clear one | Confirmed |
| A failed ToF read encodes as `0xFFFF`, never `0` | `0` is what an object touching the lens returns | Confirmed |
| The ESP-NOW frame size is derived from its format string | The 10-versus-12-byte silent drop cannot recur | Confirmed |

**The safety answer.** What GENIE says to "check all sensors" while part of its own sensing is dark:

| smoke | flame | fall | motion | Answer |
|---|---|---|---|---|
| clear | clear | idle | false | "All clear." |
| clear | clear | idle | true | "One of my safety sensors is slightly elevated." |
| clear | clear | idle | unknown | "I do not have a full safety reading right now." |
| alarm | clear | idle | unknown | "There is a safety alarm active." |

The third row was wrong at first. With the presence array disconnected, every channel read `unknown`, none matched an alarm test, and the reply fell through to "everything looks fine" — while the system could see nothing. A fourth status value was added so that any unreadable safety channel routes to the hedged answer, with a real alarm still taking precedence.

## Latency

| Path | Chain | Time |
|---|---|---|
| Fall, flame | Node 1 confirms → serial line → bridge → API → alert decision | 50–150 ms |
| Smoke | As above plus the deliberate MQ-2 debounce | about 4 s |
| On-board confirmation | Three consecutive agreeing polls before a status changes | flame ≈ 150 ms, smoke ≈ 600 ms |
| Conversation | Wake word → Faster-Whisper → Mistral-7B → Piper | 8–15 s |

The fall and flame figure was measured through the loop test. End-to-end timing on the assembled hardware is still outstanding.

## Display

| Measurement | Result |
|---|---|
| Raw fill rate | 2,477 kpx/s |
| Eye engine, soak | 118 fps, memory stable |
| Full application loop | about 34 fps, free heap flat at 152,928 bytes |

## Backlog completion

29 items: 19 functional stories across seven epics and 10 non-functional requirements.

| State | Meaning | Count |
|---|---|---|
| Complete | Acceptance criteria met and demonstrated | 21 (72.4 %) |
| Partial | Code written and passing its automated tests; a named external dependency blocks demonstration | 5 (17.2 %) |
| Not started | Declared out of scope for this iteration | 3 (10.3 %) |

The five partial items and what holds each back are listed in [`STATUS.md`](STATUS.md).

## Not measured

- Word error rate and false-accept rate on a held-out audio corpus.
- Gas response: baselines were captured, but they have not been calibrated against a real smoke or gas source and no quantified response test is recorded.
- Fall detection sensitivity or specificity: no labelled fall dataset exists.
- Sub-second alert latency on the assembled unit.
