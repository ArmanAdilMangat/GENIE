# Clean reflash — Node 2, before the final ToF try

Windows. Node 2 is the ESP32-S3 DevKitC-1 with the four ToF sensors.
Do **not** run any of this against Node 1 (the TFT board).

Purpose: eliminate software as a variable completely. After step 6 the board
holds exactly two files and a stock firmware. If bring-up still fails at three
sensors after that, software is ruled out and the cause is electrical — that is
a real result, not a wasted evening.

Budget: 20 minutes. Steps 1–3 are the ones that can teach you something. Do not
let the reflash eat the whole session.

---

## 0. Tools

```
pip install mpremote esptool
```

Find the port — Device Manager > Ports (COM & LPT), or:

```
mpremote connect list
```

Everything below assumes `COM7`. Substitute yours. Close Thonny first; it holds
the port and every command will fail with "access denied" while it is open.

---

## 1. Full flash image — the undo button

Take this **before** anything else. It is a byte-for-byte image of the whole
chip: firmware, filesystem, NVS, the lot. If the reflash goes wrong you write
this back and you are exactly where you started.

```
py -m esptool --chip esp32s3 --port COM7 --baud 921600 read_flash 0 ALL node2_full_backup.bin
```

esptool 5.x renamed the subcommand — if that errors, use `read-flash` with a
hyphen. Expect an 8 MB or 16 MB file and about two minutes.

Restore, if ever needed:

```
py -m esptool --chip esp32s3 --port COM7 write_flash 0 node2_full_backup.bin
```

---

## 2. Copy the filesystem out, readable

```
mkdir esp32_node2_backup
mpremote connect COM7 fs ls
mpremote connect COM7 cp -r :/ ./esp32_node2_backup/
```

If the recursive copy is unhappy on your mpremote version, pull them by name —
`fs ls` gave you the list:

```
mpremote connect COM7 fs cp :boot.py ./esp32_node2_backup/
mpremote connect COM7 fs cp :main.py ./esp32_node2_backup/
mpremote connect COM7 fs cp :vl53l1x.py ./esp32_node2_backup/
```

---

## 3. READ WHAT IS THERE BEFORE YOU ERASE IT

This is the step with the actual diagnostic value. From the output of `fs ls`:

- **Is there a `boot.py` or a `main.py`?** Open them. Anything that runs at
  startup and touches GPIO 8, 9, 10, 11, 12, 13, or brings up WiFi or ESP-NOW,
  is a real suspect. WiFi active also raises the board's current draw, which
  would make a marginal 3V3 rail worse in exactly the way you are seeing.
- Any leftover `tof_multi.py`, `sensors.py`, `espnow_*.py`, `genie_link.py`
  auto-running or importing at boot.
- An old `vl53l1x.py` is harmless now — the bench imports `vl53l1x_testing`.

If you find a `main.py` that starts ESP-NOW, stop here and just delete that one
file. You may already have your answer and you will not need steps 4–6.

---

## 4. Erase

```
py -m esptool --chip esp32s3 --port COM7 erase_flash
```

---

## 5. Flash stock MicroPython

Download the current `ESP32_GENERIC_S3` `.bin` from
<https://micropython.org/download/ESP32_GENERIC_S3/>.

```
py -m esptool --chip esp32s3 --port COM7 --baud 921600 write_flash -z 0 ESP32_GENERIC_S3-<version>.bin
```

Offset is **0** on the S3, not `0x1000` — that is the ESP32 classic value and
it will produce a board that does not boot.

Take the plain `ESP32_GENERIC_S3` build, not the `SPIRAM_OCT` variant. Node 2
runs no AI and no display, so PSRAM buys nothing here and the generic build is
one less thing to be wrong.

Unplug, replug, open Thonny. You should get a bare `>>>` and an empty
filesystem.

---

## 6. Upload exactly two files. Nothing else.

```
mpremote connect COM7 fs cp vl53l1x_testing.py :
mpremote connect COM7 fs cp tof_final_test.py :
```

No `boot.py`. No `main.py`. No `zones.py`. Nothing runs unless you run it.

---

## 7. The final try

1. Power-cycle the board.
2. Open `tof_final_test.py` in Thonny, Run.
3. Test **2** — expect 4/4 genuine.
4. Test **13** (cumulative load). This is the whole point of the sitting.

Read test 13 like this:

| Test 13 says | Meaning |
|---|---|
| 4/4 at every step | Software was the problem. Done. |
| solid at 1–2, fails at 3 or 4 | Supply. Software is now ruled out. Add 100 µF + 100 nF across 3V3/GND **at the sensor cluster**, re-run. |
| random, different sensor each run, even at 2 | Still supply, worse. Feed the sensors from their own 3V3 sharing GND. |

While test 13 sits at 4 sensors, put a multimeter across 3V3 and GND **at the
furthest sensor**, not at the ESP32 header. Below about 3.0 V and you have
measured the fault directly rather than inferred it.

---

## What this does and does not rule out

**Ruled out after step 6:** a stale `boot.py`/`main.py`, a half-uploaded
module, a corrupt filesystem, an old driver being imported, firmware left in a
strange state by earlier ESP-NOW work.

**Not ruled out:** the 3V3 rail, decoupling, wire length, a marginal breakout.
A wire short is unlikely — a short is deterministic, and test 2 passing 4/4
across five runs is not what a short looks like.
