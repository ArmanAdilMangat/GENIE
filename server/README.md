# GENIE Server — Flask + Whisper + Mistral + pyttsx3 (Phase 1)

The bridge between the ESP32-S3 client and the local AI stack.

```
ESP32 ──HTTP POST /audio──> Flask ──> Whisper ──> Mistral 7B ──> pyttsx3
```

In Phase 1 the reply plays on the laptop's speakers (`pyttsx3`). The HTTP
response back to the ESP32 is a JSON status payload, not audio. Phase 2
will return a 16 kHz mono WAV that the ESP32 plays through a MAX98357A.

## Prerequisites

| Tool | Why | Notes |
| --- | --- | --- |
| **Python 3.10 or 3.11** | Runtime | 3.12 works but Whisper wheels lag |
| **ffmpeg** | Whisper decodes audio via ffmpeg | Add to `PATH` on Windows |
| **Ollama** | Hosts Mistral 7B locally | `ollama pull mistral` once |
| GPU with CUDA | 10× faster Whisper | Optional but strongly recommended |

## Install

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
# In one terminal — start Ollama with Mistral
ollama run mistral

# In another terminal — start the Flask server
python app.py
```

The server listens on `0.0.0.0:5000`. Find the IP your ESP32 should target with
`ipconfig` (Windows) or `ip addr` (Linux / macOS) and put it in
`firmware/include/secrets.h` as `FLASK_IP`.

## Endpoints

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| `GET` | `/` | — | Plain-text liveness check |
| `POST` | `/audio` | Raw WAV bytes (16 kHz mono 16-bit) | `{"status":"success", "you_said":"...", "genie_reply":"..."}` |

## Where do my recordings go?

Every inbound request is archived in `server/recordings/rec_YYYYMMDD_HHMMSS.wav`.
This directory is in `.gitignore` — your voice never leaves your machine, but you
should still clean it out periodically.
