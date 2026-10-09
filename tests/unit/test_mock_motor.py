"""Unit tests for the GPIO-free ``MockMotorDriver`` Digital Twin (T-025 Fase 1).

The mock implements the same ``IMotorDriver`` port as the L298N bench driver and
applies the ramp analytically (no sleeps), so it is the CI-safe counterpart. It
reads the same ``config/bench/tracks.json``: both adapters must stay in sync.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware.drivers.mock_motor import MockMotorDriver, load_driver
from hardware.hal.motor import IMotorDriver, MotorLevels

ROOT = Path(__file__).resolve().parents[2]
TRACKS = ROOT / "config" / "bench" / "tracks.json"


def _tracks() -> dict:
    return json.loads(TRACKS.read_text(encoding="utf-8"))


@pytest.fixture
def driver() -> MockMotorDriver:
    return load_driver()


def test_mock_is_an_imotor_driver(driver: MockMotorDriver):
    assert isinstance(driver, IMotorDriver)


def test_load_driver_reads_the_default_config():
    cfg = _tracks()
    instance = load_driver()
    assert instance.motor_names == list(cfg["motors"])
    assert instance.min_velocity == cfg["limits"]["min_velocity"]
    assert instance.max_velocity == cfg["limits"]["max_velocity"]
    assert instance.ramp_step == cfg["ramp_step"]
    assert instance.ramp_seconds == cfg["ramp_seconds"]


def test_initialize_starts_from_rest(driver: MockMotorDriver):
    for name in driver.motor_names:
        assert driver.get_velocity(name) == 0.0
        assert driver.motors[name].closed is False
        assert driver.motors[name].braked is False


def test_set_velocity_ramps_to_target_and_records_schedule(driver: MockMotorDriver):
    cfg = _tracks()
    target = 0.5
    driver.set_velocity("left", target)

    assert driver.get_velocity("left") == target
    assert driver.last_schedule["left"] == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5])
    assert driver.last_schedule["left"][-1] == target
    assert cfg["ramp_step"] == 0.1  # the schedule above comes from the config


def test_set_velocity_clamps_and_negative_target(driver: MockMotorDriver):
    cfg = _tracks()
    driver.set_velocity("right", 5.0)
    assert driver.get_velocity("right") == cfg["limits"]["max_velocity"]

    driver.set_velocity("left", -0.25)
    assert driver.get_velocity("left") == -0.25
    assert driver.last_schedule["left"][-1] == -0.25


def test_get_levels_forward_reverse_and_zero(driver: MockMotorDriver):
    driver.set_velocity("left", 0.5)
    assert driver.get_levels("left") == MotorLevels(True, False, 0.5)

    driver.set_velocity("left", -0.5)
    assert driver.get_levels("left") == MotorLevels(False, True, 0.5)

    driver.set_velocity("left", 0.0)
    assert driver.get_levels("left") == MotorLevels(False, False, 0.0)


def test_stop_all_coasts_every_channel(driver: MockMotorDriver):
    driver.set_velocity("left", 0.5)
    driver.set_velocity("right", -0.5)
    driver.stop_all()

    for name in driver.motor_names:
        assert driver.get_velocity(name) == 0.0


def test_brake_all_marks_every_channel_braked(driver: MockMotorDriver):
    driver.brake_all()

    for name in driver.motor_names:
        assert driver.motors[name].braked is True
        assert driver.get_velocity(name) == 0.0


def test_shutdown_closes_every_channel(driver: MockMotorDriver):
    driver.shutdown()

    for name in driver.motor_names:
        assert driver.motors[name].closed is True
        assert driver.get_velocity(name) == 0.0


def test_shutdown_is_idempotent(driver: MockMotorDriver):
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
