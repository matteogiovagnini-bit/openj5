"""
OpenJ5 L298N Motor Driver - real IMotorDriver implementation (bench bring-up).

Drives two DC motors via an L298N dual H-bridge from Raspberry Pi GPIO.
Velocity is normalized (-1.0 .. +1.0) and mapped to PWM duty on the ENA/ENB
pins; direction via IN1..IN4 pairs.

This is the bench prototype of Node 6 (tracks). It implements ``IMotorDriver``
(``hardware.hal.motor``), so the same application code runs real GPIO on the Pi
and a mock (``hardware.drivers.mock_motor``) on Mac/CI. The same interface will
be implemented by the ESP-IDF C++ driver for the real node.

``gpiozero``/``lgpio`` are imported lazily by the channel factory, so this module
imports (and the driver can be unit-tested with a fake ``channel_factory``)
without any GPIO library installed. Config is the only source of values (zero
magic numbers): ``config/bench/tracks.json``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Protocol

from ..hal.motor import IMotorDriver, clamp_velocity, motor_levels, ramp_schedule

_pin_factory_configured = False


def _ensure_pin_factory() -> None:
    """Select the lgpio pin factory once, importing gpiozero lazily (real HW only)."""
    global _pin_factory_configured
    if _pin_factory_configured:
        return
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory

    Device.pin_factory = LGPIOFactory()
    _pin_factory_configured = True


class MotorChannel(Protocol):
    """Duck-typed motor channel used by the driver (real or fake in tests)."""

    name: str

    def set_velocity(self, velocity: float) -> None: ...

    def get_velocity(self) -> float: ...

    def brake(self) -> None: ...

    def close(self) -> None: ...


ChannelFactory = Callable[..., MotorChannel]


class L298NMotor:
    """Single motor channel: one PWM enable + two direction GPIOs.

    After ``close()`` the channel is inert: ``set_velocity()`` and ``brake()``
    become safe no-ops instead of touching closed gpiozero devices (which would
    raise ``DeviceClosed``). This makes any post-shutdown command through the
    driver harmless, without relying on the caller.
    """

    def __init__(
        self,
        name: str,
        enable_gpio: int,
        in_a_gpio: int,
        in_b_gpio: int,
        pwm_frequency_hz: float,
    ) -> None:
        _ensure_pin_factory()
        from gpiozero import DigitalOutputDevice, PWMOutputDevice

        self.name = name
        self._enable = PWMOutputDevice(
            enable_gpio, frequency=pwm_frequency_hz, initial_value=0.0
        )
        self._in_a = DigitalOutputDevice(in_a_gpio, initial_value=False)
        self._in_b = DigitalOutputDevice(in_b_gpio, initial_value=False)
        self._velocity = 0.0
        self._closed = False

    def set_velocity(self, velocity: float) -> None:
        """Apply the signed velocity via ``motor_levels`` (direction pins + duty)."""
        if self._closed:
            return
        levels = motor_levels(velocity)
        self._in_a.value = levels.forward
        self._in_b.value = levels.reverse
        self._enable.value = levels.duty
        # Store the clamped velocity actually driven (sign * duty).
        self._velocity = -levels.duty if levels.reverse else levels.duty

    def get_velocity(self) -> float:
        return self._velocity

    def brake(self) -> None:
        if self._closed:
            return
        self._in_a.value = True
        self._in_b.value = True
        self._enable.value = 0.0
        self._velocity = 0.0

    def close(self) -> None:
        if self._closed:
            return
        self.set_velocity(0.0)
        self._enable.close()
        self._in_a.close()
        self._in_b.close()
        self._closed = True


class L298NDriver(IMotorDriver):
    """Two-channel DC motor driver configured from JSON (zero magic numbers)."""

    def __init__(
        self,
        config_path: str | Path,
        channel_factory: ChannelFactory = L298NMotor,
    ) -> None:
        cfg = json.loads(Path(config_path).read_text())
        if cfg.get("driver") != "l298n":
            raise ValueError(f"expected l298n config, got: {cfg.get('driver')}")
        limits = cfg["limits"]
        self.min_velocity = float(limits["min_velocity"])
        self.max_velocity = float(limits["max_velocity"])
        self.pwm_frequency_hz = float(cfg["pwm_frequency_hz"])
        self.ramp_seconds = float(cfg["ramp_seconds"])
        self.ramp_step = float(cfg["ramp_step"])
        self._motor_pins: dict[str, dict[str, int]] = {
            name: dict(pins) for name, pins in cfg["motors"].items()
        }
        self._channel_factory = channel_factory
        self.motors: dict[str, MotorChannel] = {}
        self._config_path = Path(config_path)
        # Idempotency guard for shutdown(): the IMotorDriver contract promises
        # "safe to call twice" (see hardware.hal.motor).
        self._closed = False

    def initialize(self) -> None:
        self._closed = False
        for name, pins in self._motor_pins.items():
            self.motors[name] = self._channel_factory(
                name=name,
                enable_gpio=int(pins["enable_gpio"]),
                in_a_gpio=int(pins["in_a_gpio"]),
                in_b_gpio=int(pins["in_b_gpio"]),
                pwm_frequency_hz=self.pwm_frequency_hz,
            )

    @property
    def motor_names(self) -> list[str]:
        return list(self.motors)

    def set_velocity(self, motor_id: str, velocity: float) -> None:
        motor = self.motors[motor_id]
        target = clamp_velocity(velocity, self.min_velocity, self.max_velocity)
        schedule = ramp_schedule(motor.get_velocity(), target, self.ramp_step)
        if not schedule:
            return
        step_seconds = self.ramp_seconds / len(schedule)
        for value in schedule:
            motor.set_velocity(value)
            time.sleep(step_seconds)

    def get_velocity(self, motor_id: str) -> float:
        return self.motors[motor_id].get_velocity()

    def stop_all(self) -> None:
        for motor in self.motors.values():
            motor.set_velocity(0.0)

    def brake_all(self) -> None:
        for motor in self.motors.values():
            motor.brake()

    def shutdown(self) -> None:
        """Release every resource; safe to call twice (second call is a no-op)."""
        if self._closed:
            return
        self.stop_all()
        for motor in self.motors.values():
            motor.close()
        self._closed = True


def load_driver(
    config_path: str | Path | None = None,
    channel_factory: ChannelFactory = L298NMotor,
) -> L298NDriver:
    default = Path(__file__).resolve().parents[3] / "config" / "bench" / "tracks.json"
    driver = L298NDriver(config_path or default, channel_factory=channel_factory)
    driver.initialize()
    return driver


if __name__ == "__main__":
    d = load_driver()
    print("motors:", d.motor_names)
    d.shutdown()
