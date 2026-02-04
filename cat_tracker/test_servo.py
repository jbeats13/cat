#!/usr/bin/env python3
"""
Test script for PCA9685 pan/tilt servos (e.g. Arducam).

Runs a sweep: pan left–right, then tilt up–down. Use this to confirm
the servos and I2C wiring work before running the full cat tracker.

Usage:
  python3 test_servo.py              # Sweep, repeat until Ctrl+C
  python3 test_servo.py --once      # Sweep once and exit
  python3 test_servo.py --mock      # No hardware; print angles only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

# Same port convention as cat_tracker
PAN_PORT = 0
TILT_PORT = 1
PAN_RANGE = (30, 150)
TILT_RANGE = (50, 130)
CENTER_PAN = 90
CENTER_TILT = 90
STEP_DEG = 5
STEP_DELAY = 0.05


def get_servo(mock: bool):
    """Return an object with set_angle(port, angle)."""
    if mock:
        class Mock:
            def set_angle(self, port: int, angle: int | float) -> None:
                print("  [mock] servo %d -> %d" % (port, int(angle)))
        return Mock()
    try:
        import adafruit_servokit
    except ImportError:
        print("adafruit_servokit not found.")
        print("Run:  %s test_servo.py --install   (installs into this Python, then try again)" % sys.executable)
        print("Or:  %s -m pip install lgpio adafruit-circuitpython-servokit adafruit-circuitpython-pca9685 adafruit-blinka" % sys.executable)
        print("Or:  python3 test_servo.py --mock     (test without hardware)")
        sys.exit(1)
    kit = adafruit_servokit.ServoKit(channels=16)
    kit.servo[PAN_PORT].angle = CENTER_PAN
    kit.servo[TILT_PORT].angle = CENTER_TILT

    class Wrapper:
        def set_angle(self, port: int, angle: int | float) -> None:
            a = max(0, min(180, int(angle)))
            kit.servo[port].angle = a
    return Wrapper()


def main():
    parser = argparse.ArgumentParser(description="Test PCA9685 pan/tilt servos")
    parser.add_argument("--once", action="store_true", help="Sweep once then exit")
    parser.add_argument("--mock", action="store_true", help="No hardware; print angles only")
    parser.add_argument("--install", action="store_true", help="Install Adafruit libs into this Python, then exit")
    args = parser.parse_args()

    if args.install:
        pkgs = [
            "lgpio",  # Required by adafruit_blinka on Raspberry Pi
            "adafruit-circuitpython-servokit",
            "adafruit-circuitpython-pca9685",
            "adafruit-blinka",
        ]
        print("Installing into %s ..." % sys.executable)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs)
        print("Done. Run: python3 test_servo.py --once")
        return

    print("Servo test (pan port %d, tilt port %d)" % (PAN_PORT, TILT_PORT))
    if args.mock:
        print("Mock mode: no hardware.")
    else:
        print("Using PCA9685 over I2C. Press Ctrl+C to stop.")
    print()

    servo = get_servo(mock=args.mock)

    try:
        while True:
            print("Sweeping pan %d -> %d -> %d ..." % (PAN_RANGE[0], PAN_RANGE[1], PAN_RANGE[0]))
            for angle in range(PAN_RANGE[0], PAN_RANGE[1] + 1, STEP_DEG):
                servo.set_angle(PAN_PORT, angle)
                time.sleep(STEP_DELAY)
            for angle in range(PAN_RANGE[1], PAN_RANGE[0] - 1, -STEP_DEG):
                servo.set_angle(PAN_PORT, angle)
                time.sleep(STEP_DELAY)
            print("Sweeping tilt %d -> %d -> %d ..." % (TILT_RANGE[0], TILT_RANGE[1], TILT_RANGE[0]))
            for angle in range(TILT_RANGE[0], TILT_RANGE[1] + 1, STEP_DEG):
                servo.set_angle(TILT_PORT, angle)
                time.sleep(STEP_DELAY)
            for angle in range(TILT_RANGE[1], TILT_RANGE[0] - 1, -STEP_DEG):
                servo.set_angle(TILT_PORT, angle)
                time.sleep(STEP_DELAY)
            if args.once:
                servo.set_angle(PAN_PORT, CENTER_PAN)
                servo.set_angle(TILT_PORT, CENTER_TILT)
                print("Done. Centered.")
                break
            print()
    except KeyboardInterrupt:
        servo.set_angle(PAN_PORT, CENTER_PAN)
        servo.set_angle(TILT_PORT, CENTER_TILT)
        print("\nStopped. Centered.")


if __name__ == "__main__":
    main()
