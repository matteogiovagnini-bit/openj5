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


def trapezoid_velocity(steps_remaining: float, vmax: float, accel: float, dt: float) -> float:
    """Acceleration-limited velocity (steps/s) toward a target (pure, no I/O).

    Returns the signed velocity that ramps up to ``vmax`` then down as
    ``steps_remaining`` shrinks. Shared by the A4988 bench driver and the mock
    so the simulated motion matches the real ramp. Unit-testable without GPIO.
    A vmax of 0 means 'hold' (velocity 0).
    """
    if steps_remaining == 0:
        return 0.0
    direction = 1.0 if steps_remaining > 0 else -1.0
    distance = abs(steps_remaining)
    v_cap = (2 * accel * distance) ** 0.5
    cruise_v = min(vmax, v_cap)
    v = min(cruise_v, v_cap + accel * dt)
    return direction * v