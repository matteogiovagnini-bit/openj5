"""
OpenJ5 Mock DC Motor Driver - in-process, no GPIO (CI/tests safe).

Implements the ``IMotorDriver`` HAL port (ADR-005) without touching GPIO: it
keeps the last commanded velocity per channel and applies the ramp analytically
via the pure helpers in ``hardware.hal.motor`` (no sleeps), so unit tests run
on any Mac/CI machine.

Per ADR-019 the Raspberry Pi is brain-only (Node 1): the real L298N H-bridge is
driven by the Node 6 ESP32-S3 firmware, never by the Pi. On the host this mock
is the ``IMotorDriver`` implementation (Digital Twin): the same API the
firmware exposes (``firmware/common/include/hal/motor_driver.hpp``), a different
adapter.

``load_driver()`` with no path returns a documented default (limits +/-1.0,
``ramp_step 0.1``, ``ramp_seconds 0.05``, motors ``left``/``right``), exactly
like ``mock_stepper.load_driver``; pass a path to read ``limits``/``ramp_step``/
``ramp_seconds``/``motors`` from JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..hal.motor import (
    IMotorDriver,
    MotorLevels,
    clamp_velocity,
    motor_levels,
    ramp_schedule,
)


class MockMotorChannel:
    """One simulated motor channel: last velocity + brake/closed telemetry."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._velocity = 0.0
        self.braked = False
        self.closed = False

    def set_velocity(self, velocity: float) -> None:
        self._velocity = velocity
        self.braked = False

    def get_velocity(self) -> float:
        return self._velocity

    def brake(self) -> None:
        self._velocity = 0.0
        self.braked = True

    def close(self) -> None:
        self._velocity = 0.0
        self.closed = True


class MockMotorDriver(IMotorDriver):
    """Deterministic DC motor simulation mirroring the H-bridge ramp behavior."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Build the mock from a normalized config dict (see ``load_driver``).

        The ``cfg.get(..., default)`` fallbacks exist only for direct use in
        tests; ``load_driver()`` always passes an explicit config dict, so the
        defaults are documented in exactly one place.
        """
        cfg = config or {}
        self.min_velocity = float(cfg.get("min_velocity", -1.0))
        self.max_velocity = float(cfg.get("max_velocity", 1.0))
        self.ramp_step = float(cfg.get("ramp_step", 0.1))
        self.ramp_seconds = float(cfg.get("ramp_seconds", 0.05))
        names = list(cfg.get("motors", ("left", "right")))
        self.motors: dict[str, MockMotorChannel] = {
            name: MockMotorChannel(name) for name in names
        }
        # Last ramp values applied per channel (inspection/debug, not state).
        self.last_schedule: dict[str, list[float]] = {}

    def initialize(self) -> None:
        for channel in self.motors.values():
            channel.set_velocity(0.0)
            channel.closed = False

    @property
    def motor_names(self) -> list[str]:
        return list(self.motors)

    def set_velocity(self, motor_id: str, velocity: float) -> None:
        """Apply the ramp schedule instantly (no sleeps) up to the clamped target."""
        channel = self.motors[motor_id]
        target = clamp_velocity(velocity, self.min_velocity, self.max_velocity)
        schedule = ramp_schedule(channel.get_velocity(), target, self.ramp_step)
        for value in schedule:
            channel.set_velocity(value)
        self.last_schedule[motor_id] = schedule

    def get_levels(self, motor_id: str) -> MotorLevels:
        """Hardware levels the real H-bridge would apply at the current velocity."""
        return motor_levels(self.motors[motor_id].get_velocity())

    def get_velocity(self, motor_id: str) -> float:
        return self.motors[motor_id].get_velocity()

    def stop_all(self) -> None:
        for channel in self.motors.values():
            channel.set_velocity(0.0)

    def brake_all(self) -> None:
        for channel in self.motors.values():
            channel.brake()

    def shutdown(self) -> None:
        self.stop_all()
        for channel in self.motors.values():
            channel.close()


def load_driver(config_path: str | Path | None = None) -> MockMotorDriver:
    """Build the mock from a JSON config, or from the documented defaults.

    No path -> documented default (limits +/-1.0, ``ramp_step 0.1``,
    ``ramp_seconds 0.05``, motors ``left``/``right``), so the Digital Twin works
    standalone without reading any bench file. With a path, the JSON must carry
    ``limits`` (``min_velocity``/``max_velocity``), ``ramp_step``,
    ``ramp_seconds`` and ``motors``.
    """
    if config_path is None:
        cfg: dict[str, Any] = {
            "min_velocity": -1.0,
            "max_velocity": 1.0,
            "ramp_step": 0.1,
            "ramp_seconds": 0.05,
            "motors": ["left", "right"],
        }
    else:
        raw = json.loads(Path(config_path).read_text())
        limits = raw["limits"]
        cfg = {
            "min_velocity": float(limits["min_velocity"]),
            "max_velocity": float(limits["max_velocity"]),
            "ramp_step": float(raw["ramp_step"]),
            "ramp_seconds": float(raw["ramp_seconds"]),
            "motors": list(raw["motors"]),
        }
    driver = MockMotorDriver(cfg)
    driver.initialize()
    return driver
