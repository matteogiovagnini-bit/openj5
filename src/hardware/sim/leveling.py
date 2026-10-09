"""
Body leveling loop simulation (ADR-017, Node 7 Balance Controller).

Simulates the ESP32 control loop in pure Python so the design and the PID gains
can be validated on the bench/HIL before the C++ firmware exists:

    body_pitch  = track_tilt + joint_angle          (gravity reference)
    error       = target_pitch - body_pitch
    joint_speed = PID(error)  ->  stepper  ->  joint_angle

The same kinematics/loop are ported 1:1 to firmware/node7_balance (ESP-IDF).
Sign conventions here match the C++ module so behaviour transfers directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..hal.stepper import IStepperDriver


@dataclass
class LevelingTelemetry:
    """Snapshot of one control-loop iteration (mirrors BodyTelemetryEvent)."""
    t: float
    track_pitch_deg: float
    joint_angle_deg: float
    body_pitch_deg: float
    error_deg: float
    command_steps_s: float
    leveling_enabled: bool


@dataclass
class LevelingLoop:
    """Deterministic PID leveling simulation built on an IStepperDriver mock.

    ``track_profile(t)`` returns the track pitch in degrees at each timestep;
    defaults to a constant 0 (flat bench) so loops converge to the target.
    """
    stepper: IStepperDriver
    steps_per_deg: float = 200 * 16 * 4 / 360.0
    control_hz: int = 100

    target_pitch_deg: float = 0.0
    max_tilt_deg: float = 35.0
    deadband_deg: float = 0.5

    kp: float = 15.0
    ki: float = 0.0
    kd: float = 0.0
    integral_min: float = -4000.0
    integral_max: float = 4000.0
    # Output clamp, mirror of BalancePidParams (firmware node7_balance
    # main/balance_pid.hpp:20-21): the drivers already assume +/-1600.
    output_min_steps_s: float = -1600.0
    output_max_steps_s: float = 1600.0

    track_profile: Callable[[float], float] = field(
        default=lambda t: 0.0, repr=False
    )

    def __post_init__(self):
        self._enabled = False
        self._residual_deg = 0.0
        self._integral = 0.0
        self._last_error = 0.0
        self._first = True
        self._t = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        self._enabled = True
        self._integral = 0.0
        self._last_error = 0.0
        self._first = True  # mirror BalancePid::reset() (balance_pid.hpp:30-34)

    def stop(self) -> None:
        self._enabled = False
        self.stepper.brake()

    def joint_angle_deg(self) -> float:
        return self.stepper.get_position_steps() / self.steps_per_deg

    def step(self) -> LevelingTelemetry:
        """Run one PID iteration (called at 1/control_hz)."""
        dt = 1.0 / self.control_hz
        self._t += dt

        track_pitch = self.track_profile(self._t)
        joint_deg = self.joint_angle_deg()
        body_pitch = track_pitch + joint_deg
        error = self.target_pitch_deg - body_pitch

        command = 0.0
        if self._enabled:
            # Clamp BEFORE incrementing, same order as balance_pid.hpp:45-47.
            self._integral = max(self.integral_min, min(self.integral_max, self._integral))
            self._integral += error * dt
            # No D on the first tick after (re)enable: mirror balance_pid.hpp:49-51
            # (derivative -> first_ = False -> last_error = error, in that order).
            derivative = 0.0 if self._first else (error - self._last_error) / dt
            self._first = False
            self._last_error = error
            command = (
                self.kp * error
                + self.ki * self._integral
                + self.kd * derivative
            )
            # Output clamp to the motor limits: mirror balance_pid.hpp:54-55.
            command = max(self.output_min_steps_s, min(self.output_max_steps_s, command))
            if abs(error) < self.deadband_deg:
                command = 0.0
        else:
            # Disabled keeps state but outputs 0: mirror balance_pid.hpp:39-43.
            self._last_error = error
            self._first = True

        self.stepper.set_velocity_steps_s(command)
        self.stepper.step(dt)  # forwards the simulation by one control tick
        self._residual_deg = body_pitch - self.target_pitch_deg

        return LevelingTelemetry(
            t=self._t,
            track_pitch_deg=track_pitch,
            joint_angle_deg=joint_deg,
            body_pitch_deg=body_pitch,
            error_deg=error,
            command_steps_s=command,
            leveling_enabled=self._enabled,
        )

    def run(self, seconds: float) -> list[LevelingTelemetry]:
        """Run for ``seconds`` of simulated time, return the telemetry trace."""
        telemetry = []
        steps = int(seconds * self.control_hz)
        for _ in range(steps):
            telemetry.append(self.step())
        return telemetry