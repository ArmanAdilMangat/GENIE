# Host

The laptop side of GENIE: everything that runs a model.

## Here now

| Path | What |
|---|---|
| [`serial_reader/genie_serial.py`](serial_reader/genie_serial.py) | A runnable reference reader for the Node 1 telemetry contract in [`docs/PROTOCOL.md`](../docs/PROTOCOL.md). Threaded serial reader, alarm events separated from telemetry, expression control with tag stripping. Needs only `pyserial` |

```bash
python3 serial_reader/genie_serial.py     # offline self-test, no board and no pyserial required
```

It was written from the sensor side so that the contract had a second implementation to be checked against. The property it is built around: an alarm event is delivered to `on_alarm` and never enters the path that feeds a language model.

## Pending import

The speech pipeline and everything built around it was developed in the team's integration tree by Muhammad Suhaib Mamoon. It is being brought into this repository; until it lands, the figures quoted for it elsewhere come from the project report.

| Component | Role |
|---|---|
| Audio server | Stereo capture over TCP, de-interleave, high-pass and gain, wake-word scoring with a run-length gate, voice-activity capture, follow-up window |
| Wake-word model | Custom "Hey Genie" model for openWakeWord, exported to ONNX |
| Transcription service | Faster-Whisper base / int8 on both channels; the higher-confidence transcript is forwarded |
| Intent layer | PyAIML over `relay.aiml` and `sensor.aiml`, with a Mistral-7B fallback under Ollama for unmatched non-sensor queries |
| Synthesis | Piper, streamed to the speaker node |
| API | FastAPI: relay control, sensor state, a TCP listener for board telemetry, UDP discovery, the handling-event log |
| Bridge | Translates board telemetry fields into the API's sensor state |
| Watchers | Alert policy, autonomous climate control, spoken reactions to handling |
| Edge-AI stack | Shared feature extractor, data-collection harness, trainer and exporter, the exported 232-parameter model, and the rule-based baseline |
| Verification tooling | A hardware-free board simulator with twelve scenarios, a terminal monitor, a standalone serial bridge, and a pre-flash consistency checker |
| Tests | Five suites, 104 assertions, none needing a board |

How these fit together: [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
