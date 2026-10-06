#!/usr/bin/env python3
"""Regression tests for the alert policy and the all-sensors summary.

    cd host
    python tests/test_alert_policy.py

No board, no api.py, no models. SensorWatcher is driven with canned readings
and a fake clock; the AIML kernel is the real one, loaded with the real
relay.aiml and sensor.aiml.

Two of these exist because the behaviour they pin was wrong in the code as
first imported:

  * a watcher on a machine that had been up for less than the cooldown
    dropped its first alert (test_first_alert_on_a_cold_machine)
  * "check all sensors" answered all clear while smoke was elevated
    (test_summary_elevated_smoke_is_not_all_clear)
"""
import os
import sys

HOST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HOST, "Services"))
sys.path.insert(0, HOST)
os.chdir(HOST)

import sensor_watch                                             # noqa: E402
from config import SENSOR_ALERT_COOLDOWN, SENSOR_ALERT_DEBOUNCE  # noqa: E402


class Clock:
    """Stands in for the `time` module inside sensor_watch."""

    def __init__(self, now):
        self.now = float(now)

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def readings(smoke="clear", flame="clear", motion="false", fall="idle"):
    return {
        "SMOKE": {"status": smoke},
        "FLAME": {"status": flame},
        "MOTION": {"status": motion},
        "FALL": {"status": fall},
        "TEMPERATURE": {"value": 27},
        "HUMIDITY": {"value": 55},
    }


def watcher(start_at):
    """A SensorWatcher on the shipped configuration, with a clock we own."""
    clock = Clock(start_at)
    sensor_watch.time = clock
    alerts = []
    w = sensor_watch.SensorWatcher(
        on_alert=lambda sensor, message: alerts.append(sensor),
        log=lambda *_: None)
    state = {"now": readings()}
    w._fetch = lambda: state["now"]

    def poll(**kw):
        state["now"] = readings(**kw)
        return w.poll_once()

    return clock, poll, alerts


# ------------------------------------------------------------- alert policy
def test_first_alert_on_a_cold_machine():
    # time.monotonic() counts from boot on Windows. Three seconds of uptime
    # is far inside the cooldown, and must not look like "an alert just fired".
    clock, poll, alerts = watcher(start_at=3.0)
    assert poll(flame="alarm") == "FLAME", "the first alert after boot was dropped"
    assert alerts == ["FLAME"]


def test_a_latched_alarm_fires_once():
    clock, poll, alerts = watcher(start_at=5000.0)
    assert poll(flame="alarm") == "FLAME"
    for _ in range(20):
        clock.sleep(1.5)
        assert poll(flame="alarm") is None
    assert alerts == ["FLAME"], "a fire that keeps burning is one emergency"


def test_unknown_never_alerts():
    clock, poll, alerts = watcher(start_at=5000.0)
    for _ in range(10):
        clock.sleep(1.5)
        assert poll(smoke="unknown", flame="unknown", motion="unknown", fall="unknown") is None
    assert alerts == []


def test_elevated_smoke_is_a_warning_not_an_alert():
    clock, poll, alerts = watcher(start_at=5000.0)
    for _ in range(10):
        clock.sleep(1.5)
        assert poll(smoke="elevated") is None
    assert alerts == []


def test_smoke_must_hold_before_it_alerts():
    clock, poll, alerts = watcher(start_at=5000.0)
    assert poll(smoke="alarm") is None                 # first sight starts the clock
    clock.sleep(SENSOR_ALERT_DEBOUNCE - 0.1)
    assert poll(smoke="alarm") is None                 # still settling
    clock.sleep(0.1)
    assert poll(smoke="alarm") == "SMOKE"


def test_a_twitch_restarts_the_settle_clock():
    clock, poll, alerts = watcher(start_at=5000.0)
    assert poll(smoke="alarm") is None
    clock.sleep(2.0)
    assert poll(smoke="clear") is None                 # the MQ-2 twitched back
    clock.sleep(1.0)
    assert poll(smoke="alarm") is None                 # clock restarts here
    clock.sleep(SENSOR_ALERT_DEBOUNCE - 0.5)
    assert poll(smoke="alarm") is None
    clock.sleep(0.5)
    assert poll(smoke="alarm") == "SMOKE"


def test_flame_is_not_debounced_a_second_time():
    clock, poll, alerts = watcher(start_at=5000.0)
    assert poll(flame="alarm") == "FLAME", "the board already confirmed it over three polls"


def test_cooldown_covers_every_sensor():
    # Deliberate, and stated at the top of sensor_watch.py: after any alert
    # every sensor is ignored for the cooldown, so one event cannot place a
    # second call the moment the first hangs up. The cost is pinned here so
    # nobody changes it by accident: a different hazard inside the window
    # is not announced.
    clock, poll, alerts = watcher(start_at=5000.0)
    assert poll(flame="alarm") == "FLAME"
    clock.sleep(30.0)
    assert poll() is None
    clock.sleep(1.0)
    assert poll(smoke="alarm") is None
    clock.sleep(SENSOR_ALERT_DEBOUNCE + 1.0)
    assert poll(smoke="alarm") is None, "inside the cooldown"
    assert alerts == ["FLAME"]


def test_a_new_episode_after_the_cooldown_alerts_again():
    clock, poll, alerts = watcher(start_at=5000.0)
    assert poll(flame="alarm") == "FLAME"
    clock.sleep(5.0)
    assert poll() is None                              # cleared
    clock.sleep(SENSOR_ALERT_COOLDOWN + 1.0)
    assert poll(flame="alarm") == "FLAME"
    assert alerts == ["FLAME", "FLAME"]


def test_suppressed_alarm_does_not_fire_when_the_cooldown_lifts():
    # A reading swallowed by the cooldown has to go low and high again.
    clock, poll, alerts = watcher(start_at=5000.0)
    assert poll(flame="alarm") == "FLAME"
    clock.sleep(5.0)
    assert poll() is None
    clock.sleep(5.0)
    assert poll(flame="alarm") is None                 # suppressed, edge consumed
    clock.sleep(SENSOR_ALERT_COOLDOWN + 1.0)
    assert poll(flame="alarm") is None                 # same episode, still latched
    assert alerts == ["FLAME"]


# ------------------------------------------------------ all-sensors summary
_classifier = None


def summary(**kw):
    global _classifier
    if _classifier is None:
        import ai
        _classifier = ai.IntentClassifier()
    return _classifier.build_all_sensors_reply(readings(**kw)).lower()


ALL_CLEAR = ("all clear", "everything looks fine")


def test_summary_all_clear():
    reply = summary()
    assert any(p in reply for p in ALL_CLEAR), reply


def test_summary_elevated_smoke_is_not_all_clear():
    reply = summary(smoke="elevated")
    assert not any(p in reply for p in ALL_CLEAR), reply
    assert "elevated" in reply, reply


def test_summary_unreadable_sensor_is_not_all_clear():
    for dead in ("smoke", "flame", "fall", "motion"):
        reply = summary(**{dead: "unknown"})
        assert not any(p in reply for p in ALL_CLEAR), (dead, reply)
        assert "full safety reading" in reply, (dead, reply)


def test_summary_alarm_wins_over_a_blind_spot():
    reply = summary(flame="alarm", smoke="unknown")
    assert "safety alarm" in reply, reply


def test_summary_smoke_alarm():
    assert "safety alarm" in summary(smoke="alarm")


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok    %s" % name)
        except AssertionError as exc:
            failed += 1
            print("FAIL  %s  %s" % (name, exc))
    print("%d tests, %d failed" % (len(tests), failed))
    raise SystemExit(1 if failed else 0)
