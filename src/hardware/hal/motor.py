"""
OpenJ5 Core HAL - IMotorDriver (Port)

Pure interface for DC motor drivers, per ADR-005. It is the motor counterpart
of ``hal/stepper.py``: velocity is normalized in [-1.0, +1.0] (magnitude = PWM
duty, sign = direction) instead of steps/s.

Interface shape (Python):
    initialize(), set_velocity(motor_id, velocity), get_velocity(motor_id),
    stop_all(), brake_all(), shutdown(), motor_names

Applications and domain code depend on this interface only. The concrete
drivers live in ``hardware.drivers``: ``l298n`` (real RPi GPIO, bench Node 6)
and ``mock_motor`` (CI/demo, Digital Twin).

This Python port is the reference contract for now: the C++ counterpart at
``firmware/common/include/hal/`` (and its parity helpers) will be added with the
Node 6 firmware, following the pattern of ``hal/stepper.py`` -- whose C++
``stepper_driver.hpp`` / ``stepper_logic.hpp`` already exist -- but is **not
present yet**.

This module is pure: no GPIO, no I/O, importable on any machine.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MotorLevels:
    """Immutable hardware level snapshot for one DC motor channel.

    ``forward``/``reverse`` are the two direction GPIO levels (exactly one True
    for a nonzero velocity, both False at rest) and ``duty`` is the PWM duty in
    [0.0, 1.0].
    """

    forward: bool
    reverse: bool
    duty: float


class IMotorDriver(ABC):
    """Hardware Abstraction Layer port for DC motor drivers (ADR-005)."""

    @property
    @abstractmethod
    def motor_names(self) -> list[str]:
        """Identifiers of the configured motor channels, in config order."""

    @abstractmethod
    def initialize(self) -> None:
        """Bring the driver up: configure pins/board and create the channels."""

    @abstractmethod
    def set_velocity(self, motor_id: str, velocity: float) -> None:
        """Set signed normalized velocity in [-1.0, +1.0]; sign selects direction.

        Violations of the configured limits must be clamped instead of silently
        executed (the bench drivers ramp toward the clamped target).
        """

    @abstractmethod
    def get_velocity(self, motor_id: str) -> float:
        """Last commanded signed velocity for ``motor_id``."""

    @abstractmethod
    def stop_all(self) -> None:
        """Coast every motor to 0 (direction pins low, PWM 0)."""

    @abstractmethod
    def brake_all(self) -> None:
        """Brake every motor (both direction pins high, PWM 0) to hold it."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release every resource; leaves the motors free. Safe to call twice."""


def clamp_velocity(velocity: float, min_velocity: float, max_velocity: float) -> float:
    """Clamp ``velocity`` into [``min_velocity``, ``max_velocity``].

    Raises ``ValueError`` if the bounds are inverted (``min_velocity >
    max_velocity``): a misconfigured limit is a config error, not something to
    guess deterministically.
    """
    if min_velocity > max_velocity:
        raise ValueError(
            f"inverted velocity limits: {min_velocity} > {max_velocity}"
        )
    return max(min_velocity, min(max_velocity, float(velocity)))


def motor_levels(velocity: float) -> MotorLevels:
    """Map a signed velocity to direction GPIO levels + PWM duty (pure).

    ``duty`` is ``abs(velocity)`` clamped to [0.0, 1.0]; ``forward`` is set for a
    positive velocity, ``reverse`` for a negative one, and both stay False at
    exactly 0.0.
    """
    duty = min(1.0, abs(float(velocity)))
    if velocity > 0.0:
        return MotorLevels(forward=True, reverse=False, duty=duty)
    if velocity < 0.0:
        return MotorLevels(forward=False, reverse=True, duty=duty)
    return MotorLevels(forward=False, reverse=False, duty=0.0)


def ramp_schedule(current: float, target: float, step: float) -> list[float]:
    """Intermediate velocity values from the first ramp step up to ``target``.

    Returns one value per ramp step: the ramp starts at ``current + step`` (in
    the sign of ``target - current``) and the last element is exactly ``target``
    (the final increment may be shorter than ``step`` so the ramp lands on the
    target instead of overshooting). A driver plays this list with a per-step
    sleep so PWM ramps instead of jumping, which is easier on the gearboxes.

    Documented edge cases (never divide by zero):

    - ``step <= 0``: raise ``ValueError`` (a non-positive ramp step is a config
      error; the caller must not divide by it).
    - ``current == target``: return ``[]`` (already there, nothing to ramp).
    """
    if step <= 0.0:
        raise ValueError(f"ramp step must be > 0, got: {step}")
    delta = float(target) - float(current)
    if delta == 0.0:
        return []
    direction = 1.0 if delta > 0.0 else -1.0
    distance = abs(delta)
    count = math.ceil(distance / step)
    return [current + direction * min(k * step, distance) for k in range(1, count + 1)]
