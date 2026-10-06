# link

`genie_link.py` is the single definition of the ESP-NOW frame that Node 2 sends to Node 1. Upload it to **both** boards.

It exists because the link it replaced packed 10 bytes on one side and checked for 12 on the other — see [the fault record](../../docs/fault-records/espnow-frame-size.md). Here the size is computed from the format string, and both ends import the same file.

```bash
python3 genie_link.py      # runs on a desktop: packs a frame, unpacks it, asserts
```

Frame layout and design choices: [`docs/PROTOCOL.md`](../../docs/PROTOCOL.md).
