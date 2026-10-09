"""Pure unit tests for the ``hardware.hal.motor`` port helpers (T-025 Fase 1).

No GPIO, no I/O: these are the pure math functions shared by the Node 6
ESP32-S3 firmware driver and its Digital Twin mock (ADR-019), so they must be
exercised independently of any channel factory.
"""
from __future__ import annotations

import pytest

from hardware.hal.motor import (
    MotorLevels,
    clamp_velocity,
    motor_levels,
    ramp_schedule,
)


class TestClampVelocity:
    def test_passes_through_when_within_limits(self):
        assert clamp_velocity(0.5, -1.0, 1.0) == 0.5

    def test_clamps_above_max(self):
        assert clamp_velocity(5.0, -1.0, 1.0) == 1.0

    def test_clamps_below_min(self):
        assert clamp_velocity(-5.0, -1.0, 1.0) == -1.0

    def test_keeps_the_boundaries_exactly(self):
        assert clamp_velocity(1.0, -1.0, 1.0) == 1.0
        assert clamp_velocity(-1.0, -1.0, 1.0) == -1.0

    def test_inverted_limits_raise_value_error(self):
        with pytest.raises(ValueError, match="inverted velocity limits"):
            clamp_velocity(0.0, 1.0, -1.0)


class TestMotorLevels:
    def test_positive_velocity_drives_forward(self):
        levels = motor_levels(0.5)
        assert levels == MotorLevels(forward=True, reverse=False, duty=0.5)

    def test_negative_velocity_drives_reverse(self):
        levels = motor_levels(-0.25)
        assert levels == MotorLevels(forward=False, reverse=True, duty=0.25)

    def test_zero_velocity_leaves_both_directions_low(self):
        assert motor_levels(0.0) == MotorLevels(
            forward=False, reverse=False, duty=0.0
        )

    def test_duty_is_clamped_to_one(self):
        assert motor_levels(3.0).duty == 1.0
        assert motor_levels(-3.0).duty == 1.0


class TestRampSchedule:
    def test_ascent_is_stepped_up_to_the_target(self):
        assert ramp_schedule(0.0, 0.5, 0.1) == pytest.approx(
            [0.1, 0.2, 0.3, 0.4, 0.5]
        )

    def test_descent_to_negative_target(self):
        # 0.5 -> -0.2, step 0.3: 0.2, -0.1, -0.2 (last step is shorter).
        assert ramp_schedule(0.5, -0.2, 0.3) == pytest.approx([0.2, -0.1, -0.2])

    def test_last_element_is_exactly_target_with_non_divisor_step(self):
        schedule = ramp_schedule(0.0, 0.55, 0.1)
        assert schedule[-1] == 0.55
        assert schedule == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5, 0.55])

    def test_single_step_when_target_within_one_step(self):
        assert ramp_schedule(0.4, 0.5, 0.3) == pytest.approx([0.5])

    def test_already_at_target_returns_empty(self):
        assert ramp_schedule(0.5, 0.5, 0.1) == []

    def test_non_positive_step_raises_value_error(self):
        with pytest.raises(ValueError, match="ramp step must be > 0"):
            ramp_schedule(0.0, 0.5, 0.0)
        with pytest.raises(ValueError, match="ramp step must be > 0"):
            ramp_schedule(0.0, 0.5, -0.1)
