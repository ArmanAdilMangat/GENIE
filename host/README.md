# Host

The laptop side of GENIE: everything that runs a model. Written by Muhammad Suhaib Mamoon. The two AIML files and the telemetry parser originated on the sensor side.

Nothing here needs a board. `Services/fake_node.py` simulates both sensor boards, including their failure modes, so the sensor store, the alert policy and every deterministic answer can be exercised on a laptop alone.

## Layout

```
host/
├── api.py                   sensor store, relay control, board telemetry listener, UDP discovery
├── AudioServer.py           microphone stream → wake word → voice-activity capture → recordings/
├── config.py                every setting, with the reason for each value
├── relay.aiml               light and fan commands, emergency phrases        (27 patterns)
├── sensor.aiml              every spoken sensor answer                       (335 patterns)
├── hey_genie.onnx           the custom wake-word model
├── make_emergency_clip.py   renders the clip the modem board plays into a call
├── probe_modem.py           AT-command diagnostic for the A7670E
├── requirements.txt
├── Services/                the pipeline, the watchers and the operator tools
└── tests/                   alert-policy regression tests
```

[`Services/README.md`](Services/README.md) describes the sixteen modules.

## Quick start, no hardware

```bash
cd host
python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # Python 3.11 to 3.13 — see docs/SETUP.md for why not 3.14

python api.py                                    # terminal 1
python Services/fake_node.py --scenario smoke    # terminal 2
python Services/sensor_monitor.py                # terminal 3
```

`python Services/fake_node.py --list` prints the twelve scenarios. `blind`, `dead-mq2`, `dead-tof` and `dead-imu` are the ones worth running: they show that a sensor which cannot be read is reported as `unknown` and never as clear.

The speech pipeline additionally needs Ollama with `mistral` pulled and the Piper voice. Full instructions: [`docs/SETUP.md`](../docs/SETUP.md).

## Checks that need no models and no board

```bash
python Services/genie_serial.py      # telemetry contract, alarm separation, emotion-tag stripping
python Services/node_bridge.py       # board vocabulary → API vocabulary
python Services/climate_watch.py     # two-threshold fan control and the spoken override
python Services/reaction_watch.py    # handling events → spoken reactions
python tests/test_alert_policy.py    # alert edge, debounce, cooldown; unknown is never clear
python ../tools/check_aiml.py        # well-formed, no duplicate patterns, every condition has a default
```

These run in CI on every push. They need `requests` and `aiml.py` and nothing else.

## Not in the repository

| Item | Why | How to get it |
|---|---|---|
| `piper_voices/en_US-amy-medium.onnx` and `.onnx.json` | 63 MB | `rhasspy/piper-voices` on Hugging Face, under `en/en_US/amy/medium/`. Put both files in `host/piper_voices/` |
| Whisper `base` | 142 MB | Downloaded by `faster-whisper` on first run, then cached |
| Mistral-7B | 4.4 GB | `ollama pull mistral` |
| Wake-word training audio | 242 voice recordings of five people | Not published. The trained model is here |
| `har_train.py`, `har_record.py`, `har_data.csv` | Not in the code this folder was imported from | The exported model is [`firmware/node1_face/upload/har_model.py`](../firmware/node1_face/upload/har_model.py); the figures for it cannot be reproduced from this repository |
| `test_sensor_integration.py`, `test_wire_loop.py`, `test_wifi_uplink.py`, `test_handling_chain.py`, `check_pack.py` | Same | The module self-tests above stand in for them |

## Before running it for real

`config.py` ships with placeholders. Set `WIFI_PASSWORD`, `EMERGENCY_CONTACTS` and `IOT_ESP_IP` for your own network and do not commit the result; `tools/check_secrets.py` fails the build if a literal password or phone number is committed.

Known defects in this code are listed in [`docs/STATUS.md`](../docs/STATUS.md#defects-found-in-the-code-as-imported).

---

## The three programs

### `api.py` — the sensor store and the boards' front door

Run it with `python api.py`. It starts three things at once:

| | |
|---|---|
| **FastAPI on :8000** | the HTTP endpoints below |
| **TCP listener on :9005** | where both sensor boards connect and stream |
| **UDP broadcast on :9999** | tells the boards this laptop's address, so no board carries the laptop's IP |

**`python api.py` on its own is a complete sensor rig.** You do not need the
speech pipeline to read sensors, which matters because `whisper_service.py`
takes about a minute to load its models.

It holds twelve channels:

| Channel | From | Values |
|---|---|---|
| `SMOKE` | 2× MQ-2 | `clear` `elevated` `alarm` `unknown`, plus raw ADC and ratio |
| `FLAME` | flame sensor | `clear` `alarm` `unknown` |
| `TEMPERATURE` `HUMIDITY` | DHT11 | °C, % |
| `FALL` | MPU-6050 state machine | `idle` `freefall` `impact` `fallen` |
| `MOTION` | 2× MPU-6050 | the unit itself was moved |
| `TILT` `ACCEL` | MPU-6050 | degrees, g |
| `KNOCK` | 2× SW-420 | tap, plus a lifetime counter |
| `PRESENCE` | ToF, any side | somebody nearby |
| `IR` | ToF, **front only** | something ahead |
| `DISTANCE` | nearest ToF | mm, and which side |

**Endpoints**

| Method | Path | Purpose |
|---|---|---|
| GET | `/sensors` | all twelve, plus link health and the ToF block |
| GET | `/tof` | four directions: mm, zone, nearest |
| GET | `/links` | are the boards actually talking, and how stale |
| POST | `/telemetry` | a board's raw line — also usable from `curl` |
| POST | `/update_sensors` | bulk push, used by the serial bridge |
| POST | `/sensor` | read one channel (used by `ai.py`) |
| GET/POST | `/status` `/relays` `/relay` | the light and fan |

**Why `MOTION` and `PRESENCE` are separate.** "Did you move?" asks about the
device. "Is anyone in the room?" asks about a person. They were briefly the
same channel, and GENIE would claim it had been picked up because somebody
walked past it.

---

### `AudioServer.py` — microphone to recording

Accepts the microphone board on **TCP :9000** as one stereo stream, and
broadcasts its own address on UDP :9999 so the board can find it.

```
stereo PCM16 → high-pass 120 Hz → gain ×6 → beamform (both mics summed)
   → wake word "Hey Genie"  (openWakeWord, 0.65, three hits in a row)
   → speech detection       (webrtcvad, 20 ms frames, 2 s of silence ends it)
   → recordings/recording_<timestamp>_A.wav  and  _B.wav
```

Two decisions in there worth knowing:

**The wake word and the speech detector are separate jobs.** The wake word
decides *when to start listening*; webrtcvad decides *when you stopped
talking*. Loudness decides neither — a silent room throws noise spikes as loud
as speech, so no volume threshold can separate the two. webrtcvad classifies by
acoustic signature instead.

**Both microphones are summed.** The speech is the same in both and adds up;
each microphone's own electrical noise is not, and partly cancels. Worth about
3 dB, which is range.

---

### `config.py` — every setting in the project

Around a thousand lines, and most of them are comments explaining *why* a
number is what it is. Read this before changing behaviour anywhere.

Sections: network ports · audio and gain · wake word · speech detection ·
Whisper confidence gates · the LLM system prompt · Piper · the relay API ·
the sensor board links · alert thresholds and cooldowns · the emergency
escalation · the modem's wiring.

**Ports, all in one place**

| Port | Who listens | For |
|---|---|---|
| 8000 | `api.py` | HTTP |
| 9000 | `AudioServer.py` | microphone audio |
| 9001 | `whisper_service.py` | speaker audio |
| 9002 | `whisper_service.py` | emergency trigger to the modem |
| 9003 / 9004 | both | listening cues, speech-finished signal |
| 9005 | `api.py` | sensor board telemetry |
| 9999 | UDP broadcast | "the laptop is here" |
| 11434 | Ollama | Mistral |

---

## The data files

| File | Notes |
|---|---|
| `sensor.aiml` | Every spoken sensor answer. ~850 lines. Each question has a fallback line, so an unreadable sensor says *"I cannot read that right now"* — never silence, never a false all-clear |
| `relay.aiml` | Light and fan commands, plus the spoken emergency phrases |
| `hey_genie.onnx` | The wake-word model: openWakeWord, trained on 242 clips from five speakers |
| `piper_voices/` | The TTS voice, 63 MB, **not in the repository** — see below. Both files are required; the `.json` carries the voice's configuration |
| `requirements.txt` | 12 packages. `scikit-learn` is commented out because it is only needed to retrain the handling model, not to run the system |

---

## Paths — the thing that breaks if you move files

`config.py` resolves paths **two different ways**, and mixing them up is the
most common way to get a working-looking project that will not start.

```python
AIML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relay.aiml")
```
Found next to **`config.py` itself**. Move `config.py`, and the AIML files must
move with it.

```python
WAKE_MODEL       = "hey_genie.onnx"
PIPER_MODEL_PATH = "piper_voices/en_US-amy-medium.onnx"
OUTPUT_DIR       = "recordings"
```
Found relative to **wherever you started Python**. So always run from
this folder:

```
cd host
python api.py
```

Not `python path/to/host/api.py` from somewhere else — that starts, then fails
to find the voice.

---

## Editing AIML safely

`sensor.aiml` and `relay.aiml` are XML. Two traps:

1. **A comment can never contain `--`.** `<!-- a -- b -->` is invalid XML and
   breaks the whole file. This has happened once already.
2. **No two categories may share a pattern.** A duplicate makes the matcher
   pick one at random, and the wrong answer appears intermittently.

Check both after any edit:

```
python -c "import xml.etree.ElementTree as ET; ET.parse('sensor.aiml'); print('ok')"
```
