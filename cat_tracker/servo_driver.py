"""
Servo driver abstraction for cat tracker.

Supports:
  - PCA9685 via adafruit_servokit (e.g. Arducam pan-tilt). Use when hardware is present.
  - Mock driver when --no-servo is used (no adafruit dependency required).
"""

from __future__ import annotations


class MockServo:
    """No-op servo for running without hardware."""

    def __init__(self, num_ports: int = 4) -> None:
        self._angles = [90] * num_ports

    def set_angle(self, port: int, angle: int | float) -> None:
        self._angles[port] = max(0, min(180, int(angle)))

    def get_angle(self, port: int) -> int | float:
        return self._angles[port]


def create_servo_driver(use_servo: bool = True, num_ports: int = 4):
    """
    Create a servo driver. If use_servo is False or adafruit_servokit is missing,
    returns a MockServo. Otherwise returns a wrapper around ServoKit (PCA9685).
    """
    if not use_servo:
        return MockServo(num_ports=num_ports)
    try:
        import adafruit_servokit
    except ImportError:
        return MockServo(num_ports=num_ports)

    class PCA9685Servo:
        def __init__(self) -> None:
            self._kit = adafruit_servokit.ServoKit(channels=16)
            self._num_ports = num_ports
            for i in range(num_ports):
                self._kit.servo[i].angle = 90

        def set_angle(self, port: int, angle: int | float) -> None:
            a = max(0, min(180, int(angle)))
            self._kit.servo[port].angle = a

        def get_angle(self, port: int) -> int | float:
            return self._kit.servo[port].angle or 90

    return PCA9685Servo()
