# Third-party notices

The code in this repository is released under the MIT License (see `LICENSE`) unless a file says otherwise. Two files build on other people's work, and one design idea is borrowed:

| File | Origin | Note |
|---|---|---|
| `firmware/node2_presence/upload/vl53l1x.py` and its bench copy `vl53l1x_testing.py` | A compact MicroPython port of STMicroelectronics' VL53L1X Ultra Lite Driver | Register names and the default configuration block follow ST's driver. ST's own licence terms apply to that material |
| `firmware/node1_face/upload/eyes.py` | Independent MicroPython implementation. The eye geometry model — an eye as a rounded rectangle with each mood a preset of width, height, corner radius and eyelid coverage — is adapted from the [FluxGarage RoboEyes](https://github.com/FluxGarage/RoboEyes) design | No RoboEyes source is included. RoboEyes itself is GPL-3.0 |
| `firmware/r307s_fingerprint/` | Written against the published R30x / ZFM-20 serial protocol | No vendor library is used |

## Runtime dependencies (not vendored)

The host side of the system depends on these projects, each under its own licence: [MicroPython](https://micropython.org/), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [openWakeWord](https://github.com/dscripka/openWakeWord), [Piper](https://github.com/rhasspy/piper), [Ollama](https://ollama.com/) with Mistral-7B, PyAIML, FastAPI, webrtcvad, scikit-learn and NumPy. The enclosure tooling uses [ezdxf](https://ezdxf.mozman.at/) and matplotlib.

MicroPython firmware images and model weights are not stored in this repository.
