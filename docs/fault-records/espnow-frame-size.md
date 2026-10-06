# The ESP-NOW frame that could never have worked

**Class:** protocol · **Found:** 25 August 2026 · **State:** fixed structurally

## Symptom

Both boards healthy. No exception, no log line, nothing on either console. And nothing crossing between them.

## Cause

```python
# sender
frame = struct.pack("<BBhHHBB", ...)      # struct.calcsize("<BBhHHBB") == 10

# receiver
def parse(frame):
    if len(frame) != 12:                   # rejects every frame
        return None
```

Ten bytes were sent, twelve were expected, and the parser returned `None` without a word. The link did nothing, and both sides looked fine.

## Why it survived

Both files carried a comment stating the packet size. Both comments were wrong. Each file looked reasonable on its own, and each had been checked against a hand-written idea of what the other one sent. Nobody had computed the size.

## Fix

Not a corrected constant. A structure in which the constant cannot be wrong:

```python
FMT  = "<BBBBHHHHBB"
SIZE = struct.calcsize(FMT)        # derived. Change FMT and SIZE follows.
```

and one module, [`genie_link.py`](../../firmware/link/genie_link.py), uploaded to both boards, so the two ends import the same definition and cannot drift. Run on a desktop it packs a frame, unpacks it and asserts:

```bash
python3 firmware/link/genie_link.py
```

## What it changed downstream

The host-side test suites inherited the lesson. Most tests check one side against a hand-coded example of what the other should send — the exact arrangement that let this through. The wire-loop suite never writes a protocol line by hand: bytes are produced by the emitter that runs on the board and consumed by the reader that runs on the laptop. Rename a field on either side and the suite goes red.

## Rule

Trust the computed size, never the comment.
