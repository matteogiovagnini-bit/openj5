"""Unit tests for the body leveling feature (ADR-017, Node 7 Balance Controller)."""
import math

from core.domain import StepperConfig, BalanceConfig


def build_stepper_config(gear: float = 4.0) -> StepperConfig:
    return StepperConfig(
        name="balance_joint",
        steps_per_rev=200,
        microsteps=16,
        gear_ratio=gear,
        max_speed_steps_s=1600.0,
        max_accel_steps_s2=800.0,
    )


def test_steps_per_deg_math():
    cfg = build_stepper_config()
    assert cfg.steps_per_joint_rev == 200 * 16 * 4
    assert math.isclose(cfg.steps_per_deg, 12800 / 360.0)
    assert cfg.deg_to_steps(45.0) == 1600
    assert math.isclose(cfg.steps_to_deg(800), 360.0 * 800 / 12800)


def test_balance_config_defaults_are_safe():
    cfg = BalanceConfig()
    assert cfg.max_tilt_deg == 35.0
    assert cfg.reference == "gravity"
    assert not cfg.enabled_on_boot


def test_steps_inverted_handling():
    cfg = build_stepper_config()
    s = StepperConfig(
        name=cfg.name, steps_per_rev=cfg.steps_per_rev,
        microsteps=cfg.microsteps, gear_ratio=cfg.gear_ratio,
        max_speed_steps_s=cfg.max_speed_steps_s,
        max_accel_steps_s2=cfg.max_accel_steps_s2,
        inverted=True,
    )
    assert s.inverted and not cfg.inverted


def test_mock_stepper_reaches_target():
    from hardware.drivers.mock_stepper import MockStepperDriver

    mock = MockStepperDriver(
        {"max_speed_steps_s": 1600.0, "max_accel_steps_s2": 800.0,
         "control_dt_s": 0.02}
    )
    mock.initialize()
    mock.set_position_steps(1600)
    assert math.isclose(mock.get_position_steps(), 1600.0, abs_tol=1.0)


def test_trapezoid_velocity_is_bounded():
    from hardware.hal import trapezoid_velocity

    v = trapezoid_velocity(800.0, 1600.0, 800.0, 0.02)
    assert 0.0 < v <= 1600.0
    vneg = trapezoid_velocity(-800.0, 1600.0, 800.0, 0.02)
    assert -1600.0 <= vneg < 0.0
    assert trapezoid_velocity(0.0, 1600.0, 800.0, 0.02) == 0.0


def test_leveling_loop_converges_on_flat_bench():
    from hardware.drivers.mock_stepper import MockStepperDriver
    from hardware.sim.leveling import LevelingLoop

    mock = MockStepperDriver(
        {"max_speed_steps_s": 1600.0, "max_accel_steps_s2": 800.0,
         "control_dt_s": 0.01}
    )
    mock.initialize()
    loop = LevelingLoop(
        stepper=mock,
        steps_per_deg=200 * 16 * 4 / 360.0,
        control_hz=100,
        kp=12.0, ki=1.5, kd=0.5,
        deadband_deg=0.5,
        track_profile=lambda t: 10.0,  # constant 10 deg track ramp
    )
    loop.start()
    # Off-bench start: joint at 0, body tilted by 10 deg -> must recover.
    mock.set_position_steps(0)
    trace = loop.run(seconds=5.0)
    loop.stop()
    final = trace[-1]
    assert abs(final.body_pitch_deg - loop.target_pitch_deg) <= loop.deadband_deg
    assert abs(final.joint_angle_deg) > 5.0  # joint counter-rotated the tilt


def test_leveling_loop_follows_slow_track_ramp():
    from hardware.drivers.mock_stepper import MockStepperDriver
    from hardware.sim.leveling import LevelingLoop

    mock = MockStepperDriver(
        {"max_speed_steps_s": 1600.0, "max_accel_steps_s2": 800.0,
         "control_dt_s": 0.01}
    )
    mock.initialize()
    loop = LevelingLoop(
        stepper=mock,
        steps_per_deg=200 * 16 * 4 / 360.0,
        control_hz=100,
        kp=120.0, ki=8.0, kd=0.5,
        deadband_deg=0.5,
        track_profile=lambda t: 2.0 * t,  # 0 -> 10 deg over 5 s
    )
    loop.start()
    trace = loop.run(seconds=5.0)
    loop.stop()
    final = trace[-1]
    # Steady-state tracking lag must stay near the deadband (not hours behind).
    assert abs(final.error_deg) <= 2.0
    assert math.isclose(final.track_pitch_deg, 10.0, abs_tol=1e-6)


def test_body_command_validation():
    import pytest
    from core.domain import BodyCommand

    BodyCommand(action="level")
    BodyCommand(action="tilt", angle_deg=20.0)
    with pytest.raises(ValueError):
        BodyCommand(action="wobble")
    with pytest.raises(ValueError):
        BodyCommand(action="tilt", angle_deg=95.0)