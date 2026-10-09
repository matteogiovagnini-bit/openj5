"""Unit tests for the GPIO-free ``MockMotorDriver`` Digital Twin (T-025).

The mock implements the ``IMotorDriver`` HAL port and applies the ramp
analytically (no sleeps), so it is the CI-safe counterpart of the Node 6
ESP32-S3 firmware driver (ADR-019). ``load_driver()`` works standalone from
documented defaults and also parses an explicit JSON path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware.drivers.mock_motor import MockMotorDriver, load_driver
from hardware.hal.motor import IMotorDriver, MotorLevels


@pytest.fixture
def driver() -> MockMotorDriver:
    return load_driver()


def test_mock_is_an_imotor_driver(driver: MockMotorDriver):
    assert isinstance(driver, IMotorDriver)


class TestDefaults:
    """``load_driver()`` with no path must not read any external file."""

    def test_documented_defaults(self, driver: MockMotorDriver):
        assert driver.motor_names == ["left", "right"]
        assert driver.min_velocity == -1.0
        assert driver.max_velocity == 1.0
        assert driver.ramp_step == 0.1
        assert driver.ramp_seconds == 0.05

    def test_initialize_starts_from_rest(self, driver: MockMotorDriver):
        for name in driver.motor_names:
            assert driver.get_velocity(name) == 0.0
            assert driver.motors[name].closed is False
            assert driver.motors[name].braked is False


class TestExplicitPath:
    def test_reads_limits_ramp_and_motors_from_json(self, tmp_path: Path):
        path = tmp_path / "motor.json"
        path.write_text(
            json.dumps(
                {
                    "limits": {"min_velocity": -0.8, "max_velocity": 0.6},
                    "ramp_step": 0.2,
                    "ramp_seconds": 0.3,
                    "motors": {"front_left": {}, "front_right": {}, "rear": {}},
                }
            ),
            encoding="utf-8",
        )
        instance = load_driver(path)
        assert instance.motor_names == ["front_left", "front_right", "rear"]
        assert instance.min_velocity == -0.8
        assert instance.max_velocity == 0.6
        assert instance.ramp_step == 0.2
        assert instance.ramp_seconds == 0.3


class TestRampAndClamp:
    def test_set_velocity_ramps_to_target_and_records_schedule(
        self, driver: MockMotorDriver
    ):
        target = 0.5
        driver.set_velocity("left", target)

        assert driver.get_velocity("left") == target
        assert driver.last_schedule["left"] == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5])
        assert driver.last_schedule["left"][-1] == target

    def test_set_velocity_clamps_and_negative_target(self, driver: MockMotorDriver):
        driver.set_velocity("right", 5.0)
        assert driver.get_velocity("right") == driver.max_velocity

        driver.set_velocity("left", -0.25)
        assert driver.get_velocity("left") == -0.25
        assert driver.last_schedule["left"][-1] == -0.25


class TestLevels:
    def test_get_levels_forward_reverse_and_zero(self, driver: MockMotorDriver):
        driver.set_velocity("left", 0.5)
        assert driver.get_levels("left") == MotorLevels(True, False, 0.5)

        driver.set_velocity("left", -0.5)
        assert driver.get_levels("left") == MotorLevels(False, True, 0.5)

        driver.set_velocity("left", 0.0)
        assert driver.get_levels("left") == MotorLevels(False, False, 0.0)


class TestStopBrakeShutdown:
    def test_stop_all_coasts_every_channel(self, driver: MockMotorDriver):
        driver.set_velocity("left", 0.5)
        driver.set_velocity("right", -0.5)
        driver.stop_all()

        for name in driver.motor_names:
            assert driver.get_velocity(name) == 0.0

    def test_brake_all_marks_every_channel_braked(self, driver: MockMotorDriver):
        driver.brake_all()

        for name in driver.motor_names:
            assert driver.motors[name].braked is True
            assert driver.get_velocity(name) == 0.0

    def test_shutdown_closes_every_channel(self, driver: MockMotorDriver):
        driver.shutdown()

        for name in driver.motor_names:
            assert driver.motors[name].closed is True
            assert driver.get_velocity(name) == 0.0

    def test_shutdown_is_idempotent(self, driver: MockMotorDriver):
        """Blind the ``safe to call twice`` contract also on the mock/Digital Twin."""
        driver.shutdown()
        driver.shutdown()  # must not raise

        for name in driver.motor_names:
            assert driver.motors[name].closed is True
            assert driver.get_velocity(name) == 0.0


def test_inverted_limits_surface_as_value_error_on_set_velocity(tmp_path: Path):
    bad = tmp_path / "tracks_bad.json"
    bad.write_text(
        json.dumps(
            {
                "limits": {"min_velocity": 1.0, "max_velocity": -1.0},
                "ramp_step": 0.1,
                "ramp_seconds": 0.05,
                "motors": {"left": {}, "right": {}},
            }
        ),
        encoding="utf-8",
    )
    instance = load_driver(bad)
    with pytest.raises(ValueError, match="inverted velocity limits"):
        instance.set_velocity("left", 0.5)
