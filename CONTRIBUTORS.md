# Contributors

GENIE was built by four students of the Department of Artificial Intelligence, University of Management and Technology, Lahore, as their final-year project (November 2025 – September 2026), supervised by **Mr. Mahmood Hussain**.

Work was divided by subsystem, not by sprint, so that each part of the system had one owner from first wiring to acceptance.

| Member | Subsystems |
|---|---|
| **Arman Adil Mangat** — lead developer | Node 1 (face and safety sensing) and Node 2 (presence array): hardware, wiring and MicroPython firmware. ILI9341 parallel display driver and the animated face. The ESP-NOW frame contract between the two boards and the JSON telemetry contract to the host. Per-sensor bench tests, calibration and fault isolation. `relay.aiml` and `sensor.aiml` pattern authoring. Recording and curating the "Hey Genie" wake-word corpus. Dual INMP441 capture bring-up on the microphone node. Design, generation tooling and fabrication of the laser-cut enclosure |
| **Muhammad Suhaib Mamoon** | The microphone-to-speaker pipeline on the host: UDP discovery, audio server, wake-word training and gating, voice-activity capture, Faster-Whisper transcription and channel selection, deterministic-first intent routing with the Mistral-7B fallback, Piper synthesis and speaker streaming, FastAPI backend, and integration of every module in the speech pipeline |
| **Arman and Suhaib, jointly** | Integration of the sensing side with the host. The seams are defined by written contracts — [`firmware/link/genie_link.py`](firmware/link/genie_link.py) and [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — so that neither side depends on a verbal agreement |
| **M. Farhal Raza** | The IoT relay box: firmware, wiring and delivery of the appliance-control node |
| **Suhaib and Farhal, jointly** | SIMCom A7670E cellular emergency module: driver, firmware, wiring and testing |
| **Muhammad Huzaifa Furqan** | Project documentation |

## Where each person's code lives

| Area | Location in this repository |
|---|---|
| Sensor nodes, link, enclosure, engineering record | `firmware/node1_face/`, `firmware/node2_presence/`, `firmware/link/`, `enclosure/`, `docs/` |
| Host pipeline, edge-AI stack, audio / relay / modem firmware | `host/` and `firmware/` — pending import, see [`host/README.md`](host/README.md) |
| Phase 1 prototype | `legacy/phase1/` |

## Acknowledgements

The fellow students who lent their voices to the wake-word training corpus. A keyword-spotting model is only as good as the range of speakers it has heard.

The Department of Artificial Intelligence and the School of Systems and Technology at UMT for laboratory access and equipment.
