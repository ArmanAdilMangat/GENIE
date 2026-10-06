# Setting up the host

Installing the laptop side from nothing. Adapted from the setup guide written for the project's assessors. Two levels, and you can stop after the first.

| | What you get | What it needs |
|---|---|---|
| **Level 1 — laptop only** | The sensor store, the alert policy, every AIML answer and, optionally, the full voice pipeline against simulated boards | About 5 GB of downloads for the voice pipeline; a few MB without it |
| **Level 2 — with the boards** | The device | Level 1, MicroPython on each board, a 5 V 3 A supply |

## Python version

**Use Python 3.11, 3.12 or 3.13.** Not 3.14.

The reason is one package. `webrtcvad-wheels` publishes Windows binaries for 3.11 to 3.13 and none for 3.14, where pip falls back to compiling C and fails with a wall of Microsoft Visual C++ Build Tools errors.

The package is `webrtcvad-wheels`, not `webrtcvad`. Both import as `webrtcvad`; the plain one is source-only everywhere. `requirements.txt` already names the right one.

## Install

```bash
cd host
python -m venv .venv
.venv\Scripts\activate            # Linux / macOS: . .venv/bin/activate
pip install -r requirements.txt
python -c "import fastapi, faster_whisper, openwakeword, webrtcvad, piper, aiml, serial, numpy; print('all imports OK')"
```

Tick **Add python.exe to PATH** in the Windows installer. Every later command needs the `(.venv)` prefix in the prompt.

## Models

| Model | Size | How |
|---|---|---|
| Wake word, `hey_genie.onnx` | 0.2 MB | In the repository |
| Piper voice, `en_US-amy-medium` | 63 MB | Download `en_US-amy-medium.onnx` and `en_US-amy-medium.onnx.json` from `rhasspy/piper-voices` on Hugging Face (`en/en_US/amy/medium/`) into `host/piper_voices/`. Both files are required |
| Whisper `base` | 142 MB | Fetched by `faster-whisper` on first start, then cached. That one start needs a connection |
| Mistral-7B | 4.4 GB | Install [Ollama](https://ollama.com/download), then `ollama pull mistral` |

Without Mistral, sensor questions and light / fan commands still work; they are answered by AIML. Only open conversation needs the model.

## Run

Always from `host/`. The voice, the wake-word model and the recordings folder are located relative to the working directory.

| Terminal | Command | Notes |
|---|---|---|
| 1 | `python api.py` | Sensor store and relay control. A complete sensor rig on its own |
| 2 | `python AudioServer.py` | Only with the real microphone board |
| 3 | `python Services/whisper_service.py` | The voice pipeline. Silent for about a minute while three models load |
| — | `ollama serve` | Often already running as a background service; "address already in use" means it is |

Open `http://127.0.0.1:8000/sensors`. With no boards connected most channels read `unknown`. That is correct: an unreadable sensor is never reported as a safe one.

## Simulated boards

```bash
python Services/fake_node.py --list
python Services/fake_node.py --scenario smoke
python Services/sensor_monitor.py
```

`--scenario` is required; a bare name is ignored and `idle` runs instead.

| Scenario | Shows |
|---|---|
| `idle` | A quiet room |
| `smoke` | The MQ-2 climbing past the alert line, then the alarm |
| `fire` | Flame confirmed, the fastest alarm path |
| `fall` | The fall detector confirmed and latched |
| `person` | Someone standing to the left, 65 cm away |
| `approach` | Someone walking towards the front sensor |
| `moved` | The unit picked up: `MOTION`, not `PRESENCE` |
| `knock` | Taps on the case, the counter climbing |
| `blind` | Every safety sensor unreadable. It must not say "all clear" |
| `dead-mq2` | Gas wire off: `unknown`, never `clear` |
| `dead-tof` | The ToF board gone, the face board fine |
| `dead-imu` | Both IMUs gone |

## Settings to change

All in `host/config.py`. The repository ships placeholders.

| Setting | Set it to |
|---|---|
| `WIFI_SSID`, `WIFI_PASSWORD` | Your access point. The same pair goes in `wifi_cfg.py` on both sensor boards, the top of both audio-node files and `settings.py` on the modem node. A mismatch is silent |
| `EMERGENCY_CONTACTS` | The numbers the escalation should reach, in order |
| `IOT_ESP_IP` | The relay node's current address |
| `LLM_MODEL_NAME` | Leave as `mistral` unless you want another Ollama model |

Do not commit the edited file. `python tools/check_secrets.py` catches it if you try.

## When it does not start

| Symptom | Cause |
|---|---|
| `'python' is not recognized` | Installed without "Add python.exe to PATH" |
| `ModuleNotFoundError` | The `(.venv)` prefix is missing. Activate the environment |
| C compiler errors about Visual C++ Build Tools | Python 3.14, or `webrtcvad-wheels` changed back to `webrtcvad` |
| `whisper_service.py` silent for a minute | Normal. Three models are loading |
| `Connection refused` on 11434 | Ollama is not running |
| Every sensor reads `unknown` | No boards connected. Use `fake_node.py` |
| `FileNotFoundError: piper_voices` | Run from `host/`, and keep `piper_voices` a sub-folder |
| AIML answers nothing | `relay.aiml` and `sensor.aiml` must sit beside `config.py` |

## Hardware notes for Level 2

- **The external 5 V 3 A supply is not optional, and the grounds must be tied.** USB alone does not carry four ranging ToF sensors, the radio and the amplifier. The symptoms look like software faults: a different subset of sensors working on each boot, and a display that resets.
- **The face board needs the `ESP32_GENERIC_S3-SPIRAM_OCT` MicroPython build**, v1.27.0. The plain build boots and then fails to bring up Wi-Fi with an out-of-memory error.
- **Calibrate the gas baseline in clean air** before a demonstration: `genie_menu.run()`, option 9. Without it smoke can never cross the alarm threshold. A new MQ-2 needs 24 to 48 hours powered before its baseline settles.

Board bring-up: [`BRING_UP.md`](BRING_UP.md). Current faults: [`STATUS.md`](STATUS.md).
