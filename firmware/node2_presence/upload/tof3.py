
# tof3.py
# GENIE - 4x VL53L1X hardware bring-up and reading
#
# ESP32-S3:
#   SDA  = GPIO 8
#   SCL  = GPIO 9
#   XSHUT = GPIO 10,11,12,13
#
# Sensors:
#   FRONT = 0x30
#   LEFT  = 0x31
#   RIGHT = 0x32
#   REAR  = 0x33

from machine import I2C, Pin
import time
from vl53l1x import VL53L1X, MODEL_ID, SHORT, LONG

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

SDA_PIN = 8
SCL_PIN = 9

XSHUT_PINS = (10, 11, 12, 13)
ADDRESSES  = (0x30, 0x31, 0x32, 0x33)
NAMES      = ("FRONT", "LEFT", "RIGHT", "REAR")

N_SENSORS = 4

I2C_FREQ = 100_000

# SHORT is better for indoor testing and reduces ambient-light problems.
DISTANCE_MODE = SHORT

BOOT_SETTLE_MS = 30
RETRY_DELAY_MS = 50

# ------------------------------------------------------------
# I2C
# ------------------------------------------------------------

def make_i2c():
    return I2C(
        0,
        sda=Pin(SDA_PIN),
        scl=Pin(SCL_PIN),
        freq=I2C_FREQ
    )


def scan(i2c):
    found = i2c.scan()
    print("I2C:", [hex(x) for x in found])
    return found


# ------------------------------------------------------------
# XSHUT
# ------------------------------------------------------------

def all_shutdown():
    """Put every sensor into hardware shutdown."""
    pins = []

    for gpio in XSHUT_PINS:
        p = Pin(gpio, Pin.OUT)
        p.value(0)
        pins.append(p)

    time.sleep_ms(100)
    return pins


# ------------------------------------------------------------
# SINGLE SENSOR INITIALIZATION
# ------------------------------------------------------------

def initialize_sensor(i2c, xshut_pin, new_address, name):
    """
    Bring up ONE sensor.

    IMPORTANT:
        1. Sensor wakes at 0x29.
        2. Verify 0x29.
        3. Verify model ID.
        4. Initialize while still at 0x29.
        5. Change address.
        6. Verify new address.
        7. Start ranging.
    """

    print()
    print("--------------------------------------------")
    print("%s" % name)
    print("--------------------------------------------")

    print("XSHUT GPIO%d -> HIGH" % xshut_pin)
    Pin(xshut_pin, Pin.OUT).value(1)

    time.sleep_ms(BOOT_SETTLE_MS)

    # --------------------------------------------------------
    # Check factory address
    # --------------------------------------------------------

    found = i2c.scan()

    if 0x29 not in found:
        print("FAIL: 0x29 did not appear")
        print("BUS:", [hex(x) for x in found])
        return None

    print("0x29 detected")

    # --------------------------------------------------------
    # Create driver at FACTORY address
    # --------------------------------------------------------

    sensor = VL53L1X(i2c, 0x29)

    # --------------------------------------------------------
    # Model ID
    # --------------------------------------------------------

    try:
        model = sensor.model_id()
    except Exception as e:
        print("FAIL: could not read model ID:", e)
        return None

    print("Model ID: 0x%04X" % model)

    if model != MODEL_ID:
        print("FAIL: wrong model!")
        print("Expected: 0x%04X" % MODEL_ID)
        return None

    print("Model OK")

    # --------------------------------------------------------
    # INITIALIZE WHILE STILL AT 0x29
    # --------------------------------------------------------

    try:
        print("Initializing at 0x29...")
        sensor.init(DISTANCE_MODE)
    except Exception as e:
        print("FAIL: init:", e)
        return None

    print("Initialization OK")

    # --------------------------------------------------------
    # CHANGE ADDRESS
    # --------------------------------------------------------

    try:
        print(
            "Changing address 0x29 -> 0x%02X"
            % new_address
        )

        sensor.set_address(new_address)

    except Exception as e:
        print("FAIL: address change:", e)
        return None

    time.sleep_ms(50)

    # --------------------------------------------------------
    # VERIFY NEW ADDRESS
    # --------------------------------------------------------

    found = i2c.scan()

    if new_address not in found:
        print(
            "FAIL: 0x%02X not found after address change"
            % new_address
        )
        print("BUS:", [hex(x) for x in found])
        return None

    print(
        "Address OK: 0x%02X"
        % new_address
    )

    # 0x29 should no longer belong to this sensor.
    # If another sensor is asleep, 0x29 should be absent.
    print("BUS:", [hex(x) for x in found])

    # --------------------------------------------------------
    # START RANGING
    # --------------------------------------------------------

    try:
        sensor.start()
    except Exception as e:
        print("FAIL: start ranging:", e)
        return None

    print("Ranging started")
    print("%s -> READY" % name)

    return sensor


# ------------------------------------------------------------
# FOUR SENSOR BRING-UP
# ------------------------------------------------------------

def bring_up():

    print()
    print("=" * 60)
    print("       VL53L1X FOUR-SENSOR HARDWARE TEST")
    print("=" * 60)

    i2c = make_i2c()

    print()
    print("Initial I2C scan:")
    scan(i2c)

    # --------------------------------------------------------
    # EVERYTHING OFF
    # --------------------------------------------------------

    print()
    print("Putting ALL sensors into shutdown...")

    xshut = all_shutdown()

    time.sleep_ms(100)

    found = i2c.scan()

    print(
        "Bus with ALL XSHUT LOW:",
        [hex(x) for x in found]
    )

    if found:
        print()
        print("!!! WARNING !!!")
        print("Bus is NOT silent with all XSHUT LOW.")
        print("This means at least one sensor is NOT responding")
        print("to its XSHUT line.")
        print()
        print("Check:")
        print("  GPIO10 -> FRONT XSHUT")
        print("  GPIO11 -> LEFT XSHUT")
        print("  GPIO12 -> RIGHT XSHUT")
        print("  GPIO13 -> REAR XSHUT")
        print("  3V3 / VIN")
        print("  GND")
        print()

    # --------------------------------------------------------
    # SENSOR WALK
    # --------------------------------------------------------

    sensors = []

    for i in range(N_SENSORS):

        gpio = XSHUT_PINS[i]
        address = ADDRESSES[i]
        name = NAMES[i]

        sensor = initialize_sensor(
            i2c,
            gpio,
            address,
            name
        )

        if sensor is None:

            print()
            print("!!! %s FAILED !!!" % name)

            # IMPORTANT:
            # A failed sensor must be shut down.
            # Otherwise it remains at 0x29 and collides
            # with the next sensor.
            xshut[i].value(0)

            time.sleep_ms(100)

            sensors.append(None)

        else:
            sensors.append(sensor)

    # --------------------------------------------------------
    # FINAL BUS CHECK
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("FINAL I2C BUS")
    print("=" * 60)

    found = i2c.scan()

    print(
        [hex(x) for x in found]
    )

    print()

    expected = list(ADDRESSES)

    missing = [
        a for a in expected
        if a not in found
    ]

    if not missing:
        print("SUCCESS: ALL FOUR SENSOR ADDRESSES PRESENT")
    else:
        print(
            "MISSING:",
            [hex(x) for x in missing]
        )

    alive = sum(
        1 for s in sensors
        if s is not None
    )

    print()
    print("%d / %d sensors initialized" %
          (alive, N_SENSORS))

    return i2c, sensors


# ------------------------------------------------------------
# READ ONE SENSOR
# ------------------------------------------------------------

def read_sensor(sensor):

    if sensor is None:
        return None

    try:

        if not sensor.data_ready():
            return None

        return sensor.distance()

    except Exception:
        return None


# ------------------------------------------------------------
# CONTINUOUS DISTANCE TEST
# ------------------------------------------------------------

def distance_test(i2c, sensors):

    print()
    print("=" * 60)
    print("        LIVE DISTANCE TEST")
    print("=" * 60)
    print()
    print("Move an object in front of each sensor.")
    print("Press Ctrl+C to stop.")
    print()

    # Give sensors time to produce first measurements.
    time.sleep_ms(200)

    while True:

        values = []

        for sensor in sensors:
            values.append(
                read_sensor(sensor)
            )

        output = []

        for i in range(N_SENSORS):

            if values[i] is None:
                text = "----"
            else:
                text = "%4d" % values[i]

            output.append(
                "%-5s %s mm"
                % (NAMES[i], text)
            )

        print(" | ".join(output))

        time.sleep_ms(100)


# ------------------------------------------------------------
# MAIN TEST
# ------------------------------------------------------------

def test():

    i2c, sensors = bring_up()

    alive = sum(
        1 for s in sensors
        if s is not None
    )

    if alive == 0:

        print()
        print("=" * 60)
        print("NO SENSOR INITIALIZED")
        print("=" * 60)
        return

    print()
    print("Starting distance test...")
    print()

    try:
        distance_test(i2c, sensors)

    except KeyboardInterrupt:

        print()
        print("Distance test stopped.")

    finally:

        for sensor in sensors:

            if sensor is not None:
                try:
                    sensor.stop()
                except Exception:
                    pass

        print("Ranging stopped.")


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------

test()