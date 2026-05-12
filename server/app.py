"""
GENIE — Generate, Engage, Navigate Intelligent Environments
Phase 1 Server — Flask bridge between ESP32-S3 and the local AI stack

Pipeline:
    ESP32 ──HTTP POST /audio──> Flask
                                   │
                                   ├─ Whisper (STT)
                                   ├─ Mistral 7B via Ollama (LLM)
                                   └─ pyttsx3 (TTS, plays on laptop speakers)

Phase 1 plays the reply on the laptop. In Phase 2, this server returns
a 16kHz mono WAV that the ESP32 plays back through a MAX98357A + 3W speaker.

Author: Arman Adil Mangat
Repo:   https://github.com/ArmanAdilMangat/GENIE
"""

from flask import Flask, request, jsonify
import pyttsx3
import whisper
import requests
import os
import threading
import tempfile
import shutil
import datetime

app = Flask(__name__)

os.makedirs("recordings", exist_ok=True)

print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("✅ Whisper ready!")


def speak_text(text: str) -> None:
    """Speak `text` on the laptop's default audio output."""
    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.setProperty("volume", 1.0)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def ask_mistral(user_text: str) -> str:
    """Send `user_text` to Mistral 7B via the local Ollama server and return the reply."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": (
                    "You are Genie, a smart voice assistant for a student FYP project. "
                    "Answer helpfully and briefly in 1-2 sentences only.\n"
                    f"User: {user_text}\nGenie:"
                ),
                "stream": False,
            },
            timeout=60,
        )
        if response.status_code == 200:
            return response.json()["response"].strip()
        return "I could not process that request."
    except Exception as e:
        print(f"⚠️  Ollama error: {e}")
        return "AI is not available right now."


@app.route("/audio", methods=["POST"])
def process_audio():
    wav_path = None
    try:
        wav_data = request.data
        if not wav_data:
            return jsonify({"error": "No audio received"}), 400

        # Persist raw WAV to a temp file for Whisper
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(wav_data)
        tmp.close()
        wav_path = tmp.name

        # Archive a permanent copy
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f"recordings/rec_{timestamp}.wav"
        shutil.copy(wav_path, save_path)
        print(f"\n💾 Saved: {save_path} ({os.path.getsize(wav_path):,} bytes)")

        # 1) Speech-to-Text
        print("🎙️  Transcribing with Whisper...")
        result = whisper_model.transcribe(wav_path)
        user_text = result["text"].strip()
        print(f"👤 You said: '{user_text}'")

        if not user_text:
            print("⚠️  No speech detected")
            return jsonify({"error": "No speech detected"}), 400

        # 2) LLM
        print("🤖 Asking Mistral...")
        ai_reply = ask_mistral(user_text)
        print(f"🤖 Genie: '{ai_reply}'")

        # 3) Text-to-Speech (laptop output in Phase 1)
        print("🔊 Speaking on laptop...")
        thread = threading.Thread(target=speak_text, args=(ai_reply,))
        thread.start()
        thread.join()  # wait for speech to finish before ESP32 records again
        print("✅ Speech done. ESP32 can record again.")

        return (
            jsonify(
                {
                    "status": "success",
                    "you_said": user_text,
                    "genie_reply": ai_reply,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


@app.route("/")
def home():
    return "GENIE Voice Assistant Running!"


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  GENIE — FYP Phase 1 Flask Server")
    print("=" * 50)
    print("  STT:  Whisper (base)")
    print("  AI:   Mistral via Ollama")
    print("  TTS:  pyttsx3 (laptop speaker)")
    print("  Save: ./recordings/")
    print("=" * 50)
    print("\n⚠️  Make sure Ollama is running in another terminal:")
    print("  ollama run mistral\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
