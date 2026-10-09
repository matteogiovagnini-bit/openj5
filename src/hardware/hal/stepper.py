"""
OpenJ5 Core HAL - IStepperDriver (Port)

Pure interface for stepper motor drivers, per ADR-005 / ADR-017.

A stepper is neither a servo (PCA9685) nor a DC motor (L298N):
it is driven by a STEP/DIR driver (A4988, DRV8825, TMC2209, ...) and its
position is the number of microsteps counted from home. Applications and
domain code depend on this interface only; a concrete driver (A4988 over
RPi GPIO for the bench, ESP-IDF C++ or a Gazebo joint for the simulator)
implements it.

Interface shape (Python):
    initialize(), enable(), disable(), set_position_steps(),
    set_velocity_steps_s(), get_position_steps(), get_velocity_steps_s(),
    home(), brake(), shutdown()

The same contract is defined in C++ at
firmware/common/include/hal/ for the ESP-IDF firmware (ADR-014).
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class StepperMove(Enum):
    """Direction descriptor produced by the acceleration-limited motion logic."""
    NONE = "none"
    FORWARD = "forward"
    BACKWARD = "backward"


@dataclass(frozen=True, slots=True)
class StepperState:
    """Immutable stepper state snapshot (telemetry)."""
    position_steps: int = 0
    velocity_steps_s: float = 0.0
    enabled: bool = False
    moving: bool = False
    home_reached: bool = False


class IStepperDriver(ABC):
    """Hardware Abstraction Layer port for STEP/DIR stepper drivers."""

    @abstractmethod
    def initialize(self) -> None:
        """Bring the driver up: configure pins/board, reset position if homing."""

    @abstractmethod
    def enable(self) -> None:
        """Energize the coils (hold torque). Called before any motion."""

    @abstractmethod
    def disable(self) -> None:
        """Release the coils (free shaft, no holding torque)."""

    @abstractmethod
    def set_position_steps(self, steps: int) -> None:
        """Move to an absolute position (steps from home). Acceleration-limited.

        Violations of the configured motion limits must be rejected instead of
        silently executed: raise ValueError / return an error Result.
        """

    @abstractmethod
    def set_velocity_steps_s(self, steps_s: float) -> None:
        """Set continuous velocity (signed). 0 stops and holds unless disabled."""

    @abstractmethod
    def get_position_steps(self) -> int:
        """Current position in steps from home."""

    @abstractmethod
    def get_velocity_steps_s(self) -> float:
        """Current signed velocity in steps per second."""

    @abstractmethod
    def home(self) -> None:
        """Return to home (absolute zero). Implementation-defined (no endstop yet)."""

    @abstractmethod
    def brake(self) -> None:
        """Stop motion immediately and energize the coils to hold position."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release every resource; leaves the shaft free. Safe to call twice."""


def slew(v_now: float, v_tgt: float, accel: float, dt: float) -> float:
    """Slew limit: move ``v_now`` toward ``v_tgt`` by at most ``accel * dt``.

    Mirror of ``openj5::motion::slew`` in
    ``firmware/common/include/hal/stepper_logic.hpp`` (same body): this is what
    ramps the axis up from rest and brakes it when reversing.
    """
    dv = accel * dt
    if v_tgt > v_now + dv:
        return v_now + dv
    if v_tgt < v_now - dv:
        return v_now - dv
    return v_tgt


def brake_bound(steps_remaining: float, accel: float) -> float:
    """Maximum speed from which ``accel`` can still stop within the distance.

    ``sqrt(2 * accel * |steps_remaining|)``, 0 at the target. Mirror of
    ``openj5::motion::brake_bound`` in
    ``firmware/common/include/hal/stepper_logic.hpp``.
    """
    d = abs(steps_remaining)
    return math.sqrt(2.0 * accel * d)


def position_velocity_target(steps_remaining: float, vmax: float, accel: float) -> float:
    """Position-move velocity target for this control tick (then slew-limited).

    0 exactly on target, otherwise ``sign * min(vmax, brake_bound(...))``.
    Mirror of ``openj5::motion::position_velocity_target`` in
    ``firmware/common/include/hal/stepper_logic.hpp``.
    """
    if steps_remaining == 0.0:
        return 0.0
    sign = 1.0 if steps_remaining > 0.0 else -1.0
    v_cap = brake_bound(steps_remaining, accel)
    return sign * (vmax if vmax < v_cap else v_cap)


def trapezoid_velocity(
    v_now: float, steps_remaining: float, vmax: float, accel: float, dt: float
) -> float:
    """Acceleration-limited velocity (steps/s) for one control tick (pure, no I/O).

    Mirror of ``openj5::motion::*`` in
    ``firmware/common/include/hal/stepper_logic.hpp``: the returned velocity is

        slew(v_now, position_velocity_target(steps_remaining, vmax, accel), accel, dt)

    so the caller feeds back the previous tick's value as ``v_now``: the axis
    ramps up from rest at ``accel * dt`` per tick, cruises at ``vmax`` and
    brakes within the remaining steps (never jumps straight to
    ``sqrt(2 * accel * distance)``). Shared by the A4988 bench driver and the
    mock so the simulated motion matches the real ramp. Unit-testable without
    GPIO. A ``vmax`` of 0 means 'hold' (target velocity 0, slew-braked).

    Documented, deliberate divergences from the C++ reference:

    - ``toggle_interval_us`` and ``clamp`` of ``stepper_logic.hpp`` are NOT
      ported: ``toggle_interval_us`` is an implementation detail (C++ periodic
      timer vs gpiozero PWM pulse train) and ``clamp`` is not needed here.
    - Mid-move re-targeting is not expressible through the Python blocking
      ``set_position_steps`` API: pre-existing divergence, not new debt.
    """
    return slew(v_now, position_velocity_target(steps_remaining, vmax, accel), accel, dt)