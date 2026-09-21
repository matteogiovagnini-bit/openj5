"""
OpenJ5 Mock Stepper Driver - in-process, no GPIO (CI/tests safe).

Implements the same IStepperDriver HAL port (ADR-005/ADR-017) but integrates
motion analytically, so unit tests can run on any machine. Position advances
toward the target with bounded velocity/acceleration when ``step(dt)`` is
called; ``step_until_reached()`` fast-forwards to the commanded position.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..hal.stepper import IStepperDriver, trapezoid_velocity


class MockStepperDriver(IStepperDriver):
    """Deterministic stepper simulation mirroring the A4988 ramp behavior."""

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self._position_steps = 0.0
        self._velocity_steps_s = 0.0
        self._enabled = bool(cfg.get("enabled", False))
        self.max_speed_steps_s = float(cfg.get("max_speed_steps_s", 1600.0))
        self.max_accel_steps_s2 = float(cfg.get("max_accel_steps_s2", 800.0))
        self._dt = float(cfg.get("control_dt_s", 0.02))

    def initialize(self) -> None:
        self._position_steps = 0.0
        self._velocity_steps_s = 0.0
        self._enabled = True

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False
        self._velocity_steps_s = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_position_steps(self, steps: int) -> None:
        """Acceleration-limited move to an absolute position (no I/O, instant)."""
        self._enabled = True
        target = float(steps)
        while abs(target - self._position_steps) > 0.0:
            remaining = target - self._position_steps
            v = trapezoid_velocity(
                remaining, self.max_speed_steps_s, self.max_accel_steps_s2, self._dt
            )
            advance = v * self._dt
            if abs(advance) >= abs(remaining):
                self._position_steps = target
                break
            self._position_steps += advance
        self._velocity_steps_s = 0.0

    def set_velocity_steps_s(self, steps_s: float) -> None:
        self._velocity_steps_s = max(
            -self.max_speed_steps_s, min(self.max_speed_steps_s, steps_s)
        )
        if steps_s != 0.0:
            self._enabled = True

    def step(self, dt: float) -> None:
        """Integrate the commanded velocity over dt (caller owns the profile)."""
        if not self._enabled:
            return
        self._position_steps += self._velocity_steps_s * dt

    def step_until_reached(self) -> None:
        target = getattr(self, "_target_steps", self._position_steps)
        if abs(target - self._position_steps) > 0.0:
            self.set_position_steps(int(target))

    def get_position_steps(self) -> int:
        return int(round(self._position_steps))

    def get_velocity_steps_s(self) -> float:
        return self._velocity_steps_s

    def home(self) -> None:
        self.set_position_steps(0)

    def brake(self) -> None:
        self.set_velocity_steps_s(0.0)
        self._enabled = True

    def shutdown(self) -> None:
        self.disable()


def load_driver(config_path: str | Path | None = None) -> MockStepperDriver:
    """Build a mock driver from a JSON config (same contract as a4988).

    No config path -> default bench values (mirror of config/bench/balance.json).
    """
    if config_path is None:
        config = {
            "max_speed_steps_s": 1600.0,
            "max_accel_steps_s2": 800.0,
            "control_dt_s": 0.02,
        }
        return MockStepperDriver(config)
    cfg = json.loads(Path(config_path).read_text())
    limits = cfg.get("limits", {})
    config = {
        "max_speed_steps_s": limits.get("max_velocity_steps_s", 1600.0),
        "max_accel_steps_s2": limits.get("max_acceleration_steps_s2", 800.0),
        "control_dt_s": cfg.get("control_dt_s", 0.02),
    }
    return MockStepperDriver(config)