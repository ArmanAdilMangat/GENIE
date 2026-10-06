"""
wifi_cfg.py - the network both sensor boards join.

UPLOAD TO BOTH BOARDS. Same rule as genie_link.py: one copy on one board is
how the two drift apart.

--------------------------------------------------------------------------
WHY NODE 2 ALSO JOINS, WHEN IT ONLY SPEAKS ESP-NOW
--------------------------------------------------------------------------
This is the whole reason this file exists on Node 2 at all, and skipping it
breaks the ToF link in a way that produces no error on either board.

ESP-NOW and WiFi share ONE radio. A board that has associated with an access
point is locked to that AP's channel. A board that has not is on whatever
channel it was left on. If the two do not match, every ESP-NOW frame is
dropped silently -- Node 2 sends happily, Node 1 receives nothing, and both
sides look healthy.

`node2_main.py` used to call `sta.disconnect()` with the comment "ESP-NOW
needs no AP association". That was true right up until Node 1 joined a
network, which it now does.

The fix is NOT to pin a channel number by hand. It works until the router
reboots and auto-selects a different one, and then it is a bad wire again.
Both boards join the SAME AP, so both end up on whatever channel it picked,
and they follow it when it changes.

--------------------------------------------------------------------------
IF YOU CHANGE THE NETWORK
--------------------------------------------------------------------------
Change it here, re-upload to BOTH boards, and change WIFI_SSID /
WIFI_PASSWORD in the laptop's config.py so the three agree. Nothing checks
this for you.
"""

VERSION = "wifi_cfg 1.0  27-08-2026"

# The same network the mic ESP already uses.
SSID = "YOUR_WIFI_SSID"
PASSWORD = "YOUR_WIFI_PASSWORD"

# Seconds to wait for an association before giving up on this attempt.
# Giving up is not the same as failing: both boards retry forever, and both
# keep doing their real job in the meantime -- Node 1 keeps drawing a face
# and printing telemetry to the serial port, Node 2 keeps ranging.
CONNECT_TIMEOUT_S = 15

# How long to wait before trying again after a failed association.
RETRY_S = 10

# Where the laptop is. Left as None on purpose: the boards learn it from the
# UDP discovery broadcast (see net_uplink.py), so a laptop that picks up a
# new DHCP lease does not need anything reflashed. Set a literal like
# "192.168.4.2" only as a fallback for a network with no broadcast.
LAPTOP_IP = None

DISCOVERY_PORT = 9999           # laptop broadcasts GENIE_SERVER_HELLO here
TELEMETRY_PORT = 9005           # laptop's node_bridge listens here


def connect(timeout_s=None, log=print):
    """Join the network. Returns the WLAN object, associated or not.

    NEVER raises and never blocks longer than timeout_s. Both callers sit
    in loops that must keep running whether or not there is a network --
    an assistive device that stops watching for smoke because the router
    rebooted is worse than one that never had WiFi.
    """
    import network
    import time

    timeout_s = CONNECT_TIMEOUT_S if timeout_s is None else timeout_s

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    if sta.isconnected():
        return sta

    try:
        sta.connect(SSID, PASSWORD)
    except OSError as e:
        log("[wifi] connect failed: %r" % e)
        return sta

    deadline = time.ticks_add(time.ticks_ms(), int(timeout_s * 1000))
    while not sta.isconnected():
        if time.ticks_diff(time.ticks_ms(), deadline) > 0:
            log("[wifi] no association after %ds - carrying on without it"
                % timeout_s)
            return sta
        time.sleep_ms(200)

    log("[wifi] joined %s as %s  channel %s"
        % (SSID, sta.ifconfig()[0], channel(sta)))
    return sta


def channel(sta=None):
    """Which WiFi channel this board is on. Both boards must agree or
    ESP-NOW silently drops every frame -- see the note at the top."""
    import network
    sta = sta or network.WLAN(network.STA_IF)
    try:
        return sta.config("channel")
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    # F5 on either board: proves the credentials and prints the channel.
    sta = connect()
    print("connected:", sta.isconnected())
    if sta.isconnected():
        print("ifconfig :", sta.ifconfig())
    print("channel  :", channel(sta))
    print()
    print("Run this on BOTH boards. The two channel numbers MUST match,")
    print("or the ESP-NOW link between them drops every frame in silence.")
