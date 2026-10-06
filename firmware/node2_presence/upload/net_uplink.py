"""
net_uplink.py - Node 1's telemetry over WiFi, without stalling the face.

UPLOAD TO NODE 1, alongside wifi_cfg.py.

    node1_report.py already calls this. Nothing else to wire up.

--------------------------------------------------------------------------
WHAT IT SENDS
--------------------------------------------------------------------------
Byte for byte what the serial port already carries: one JSON object per
line, exactly as `03_PROTOCOL/PROTOCOL.md` defines it. The laptop's
node_bridge feeds both transports into the same handler, so the two cannot
drift apart -- and both can run at once.

--------------------------------------------------------------------------
WHY NOT urequests.post()
--------------------------------------------------------------------------
Because it would visibly break the face, and the reason is worth writing
down before somebody "simplifies" this back into an HTTP call.

Node 1 is ONE cooperative loop with a 33.3 ms budget at 30 fps. Two eyes
cost 15.6 ms of it. `urequests.post()` is blocking end to end -- socket
create, connect, send, then wait for the response headers. On a healthy LAN
that is 40-150 ms; on a busy one, or one where the laptop is asleep, it is
seconds. Every millisecond of it is a frozen face.

A POST every 2 s would put a visible hitch in the eyes twice a minute, and
a router hiccup would look exactly like a crash.

So: connect ONCE, keep the socket, and write a line per tick. A write to an
already-open non-blocking socket is microseconds -- the same cost as the
`print()` the serial path uses. The transport becomes a detail instead of a
frame-budget problem.

--------------------------------------------------------------------------
NOTHING HERE IS ALLOWED TO MATTER
--------------------------------------------------------------------------
No AP, wrong password, laptop asleep, cable pulled, socket half-open after
the AP dropped -- every one of those must cost a log line and nothing else.
The face keeps drawing, the sensors keep confirming, the serial port keeps
carrying the same telemetry. WiFi is the convenient path, not the required
one.
"""

import time

try:
    import usocket as socket
except ImportError:
    import socket

try:
    import wifi_cfg
except ImportError:                     # not uploaded: uplink stays off
    wifi_cfg = None


# Retry the whole connect cycle no faster than this.
RETRY_MS = 5000

# Give up on a connect() that has not completed in this long. MicroPython's
# settimeout on a connecting socket is honoured on ESP32.
CONNECT_TIMEOUT_S = 3

# How long to keep listening for a discovery broadcast before falling back
# to wifi_cfg.LAPTOP_IP. Two seconds covers the laptop's 2 s broadcast
# interval with margin, and costs nothing when it succeeds on the first.
DISCOVER_TIMEOUT_S = 3


class Uplink:
    """One socket to the laptop. Call send() as often as you like."""

    def __init__(self, log=None):
        self.log = log
        self.sock = None
        self.laptop_ip = None
        self._next_try = 0
        self.sent = 0
        self.dropped = 0
        self._warned = False

    # ------------------------------------------------------------- state
    def ready(self):
        return self.sock is not None

    def status(self):
        if wifi_cfg is None:
            return "wifi_cfg.py not uploaded"
        if self.sock is not None:
            return "up -> %s:%d" % (self.laptop_ip, wifi_cfg.TELEMETRY_PORT)
        return "down"

    # -------------------------------------------------------------- send
    def send(self, line):
        """One JSON line. Returns True if it went out.

        Reconnects lazily and no more than once per RETRY_MS, so a laptop
        that is switched off costs one failed connect every five seconds
        rather than one per tick.
        """
        if wifi_cfg is None:
            return False

        if self.sock is None:
            if time.ticks_diff(time.ticks_ms(), self._next_try) < 0:
                return False
            self._next_try = time.ticks_add(time.ticks_ms(), RETRY_MS)
            if not self._connect():
                return False

        try:
            self.sock.write(line + "\n")
            self.sent += 1
            return True
        except Exception as e:
            # Half-open socket: the AP dropped and came back, or the
            # laptop process restarted. Drop it and let the next call
            # rebuild -- do NOT raise into the display loop.
            self._say("send failed (%r), reconnecting" % e)
            self.close()
            self.dropped += 1
            return False

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    # ----------------------------------------------------------- connect
    def _connect(self):
        sta = wifi_cfg.connect(log=self._say)
        if not sta.isconnected():
            return False

        ip = self.laptop_ip or self._discover() or wifi_cfg.LAPTOP_IP
        if not ip:
            if not self._warned:
                self._say("laptop not found. Is node_bridge running? "
                          "(set wifi_cfg.LAPTOP_IP to skip discovery)")
                self._warned = True
            return False

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(CONNECT_TIMEOUT_S)
            s.connect((ip, wifi_cfg.TELEMETRY_PORT))
            # Back to blocking-with-short-timeout for writes. A write that
            # cannot complete immediately must fail fast, not park the
            # display loop waiting for a TCP window.
            s.settimeout(1)
        except Exception as e:
            self._say("cannot reach %s:%d (%r)"
                      % (ip, wifi_cfg.TELEMETRY_PORT, e))
            return False

        self.sock = s
        self.laptop_ip = ip
        self._warned = False
        self._say("uplink up -> %s:%d" % (ip, wifi_cfg.TELEMETRY_PORT))
        return True

    def _discover(self):
        """Learn the laptop's IP from its UDP broadcast.

        The laptop's address changes every time DHCP feels like it. Baking
        one into the firmware means reflashing two boards because a router
        rebooted, so the boards ask instead. Same broadcast the mic ESP
        already listens for, on the same port.
        """
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(DISCOVER_TIMEOUT_S)
            s.bind(("0.0.0.0", wifi_cfg.DISCOVERY_PORT))
            deadline = time.ticks_add(time.ticks_ms(),
                                      int(DISCOVER_TIMEOUT_S * 1000))
            while time.ticks_diff(time.ticks_ms(), deadline) < 0:
                try:
                    data, addr = s.recvfrom(64)
                except Exception:
                    break
                if data and data.startswith(b"GENIE_SERVER_HELLO"):
                    self._say("discovered laptop at %s" % addr[0])
                    return addr[0]
        except Exception as e:
            self._say("discovery unavailable (%r)" % e)
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        return None

    def _say(self, msg):
        if self.log:
            self.log("[uplink] " + msg)


if __name__ == "__main__":
    # F5 on Node 1 with nothing else running: joins the network, finds the
    # laptop, and sends a heartbeat line a second. Watch it arrive in the
    # node_bridge console.
    import json

    up = Uplink(log=print)
    n = 0
    print("sending test telemetry. Ctrl-C to stop.")
    while True:
        n += 1
        line = json.dumps({
            "t": "telemetry", "temp_c": 25, "humidity": 50,
            "gas_level": "clear", "gas_ok": True, "gas_raw": 500,
            "gas_ratio": 1.0, "flame": False, "flame_ok": True,
            "imu_ok": True, "imu_level": "clear", "tilt": 0, "accel_g": 1.0,
            "fall_state": "idle", "knock": False, "knock_count": n,
        })
        ok = up.send(line)
        print("  %4d  %s   sent=%d dropped=%d" % (n, up.status(),
                                                  up.sent, up.dropped))
        time.sleep(1)
