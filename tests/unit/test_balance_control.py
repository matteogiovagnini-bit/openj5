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

    # From rest the profile RAMPS: slew moves by at most accel*dt per tick
    # (firmware/common/include/hal/stepper_logic.hpp:31-40) instead of jumping
    # straight to sqrt(2*a*d) like the old stateless version (~1410 steps/s,
    # stepper_logic.hpp:4-9).
    v = trapezoid_velocity(0.0, 800.0, 1600.0, 800.0, 0.02)
    assert v == 800.0 * 0.02  # 16.0 steps/s on the first tick
    vneg = trapezoid_velocity(0.0, -800.0, 1600.0, 800.0, 0.02)
    assert vneg == -(800.0 * 0.02)  # same accel*dt ramp in the negative direction
    # At cruise toward a nearer target the slew brakes one accel*dt per tick
    # (stepper_logic.hpp:31-40), staying bounded by vmax:
    assert 0.0 < trapezoid_velocity(1600.0, 800.0, 1600.0, 800.0, 0.02) <= 1600.0
    # Hot axis at the target: one tick decelerates by accel*dt only, so v_now=1600
    # does NOT drop to 0.0 in a single tick (slew needs many ticks to brake).
    vbrake = trapezoid_velocity(1600.0, 0.0, 1600.0, 800.0, 0.02)
    assert vbrake == 1600.0 - 800.0 * 0.02  # 1584.0, not 0.0
    # At rest exactly on the target the velocity is 0 (stepper_logic.hpp:53-54).
    assert trapezoid_velocity(0.0, 0.0, 1600.0, 800.0, 0.02) == 0.0


def test_pid_first_tick_has_no_derivative_kick():
    from hardware.drivers.mock_stepper import MockStepperDriver
    from hardware.sim.leveling import LevelingLoop

    mock = MockStepperDriver({"control_dt_s": 0.01})
    mock.initialize()
    loop = LevelingLoop(
        stepper=mock,
        control_hz=100,
        kp=15.0,  # balance_pid.hpp:17 default kp
        ki=0.0,
        kd=1.0,  # kd=1 makes a D kick obvious: error/dt = -10/0.01 = -1000
        track_profile=lambda t: 10.0,  # body pitched +10 deg at joint 0
    )
    loop.start()
    tel = loop.step()
    # error = target(0) - body(10) = -10 deg, dt = 1/100 = 0.01 s.
    # balance_pid.hpp:49-51: derivative = first_ ? 0.0 : (error-last_error)/dt
    # -> command = kp*error = -150.0. WITHOUT the guard it would be
    # -150 + kd*(error - 0)/dt = -150 - 1000 = -1150.0 (derivative kick).
    assert tel.command_steps_s == -150.0
    assert tel.leveling_enabled


def test_pid_reenable_has_no_derivative_kick():
    from hardware.drivers.mock_stepper import MockStepperDriver
    from hardware.sim.leveling import LevelingLoop

    mock = MockStepperDriver({"control_dt_s": 0.01})
    mock.initialize()
    track = {"pitch": 0.0}
    loop = LevelingLoop(
        stepper=mock,
        control_hz=100,
        kp=15.0,
        ki=0.0,
        kd=1.0,
        track_profile=lambda t: track["pitch"],
    )
    loop.start()
    assert loop.step().command_steps_s == 0.0  # flat track: zero error
    loop.stop()
    # Parked: the track tilts while disabled. Disabled ticks keep state but
    # output 0 and re-arm the first_ guard (balance_pid.hpp:39-43).
    track["pitch"] = 10.0
    disabled = loop.step()
    assert disabled.command_steps_s == 0.0
    assert not disabled.leveling_enabled
    # Tilt further right before re-enabling (no disabled tick in between).
    track["pitch"] = 20.0
    loop.start()
    reenabled = loop.step()
    # error = 0 - 20 = -20 deg: command = kp*error = -300.0, derivative = 0
    # because start()/reset re-armed first_ (balance_pid.hpp:30-34, :41).
    # Without it: start() left last_error=0 -> D = kd*(-20)/0.01 = -2000
    # -> command = -2300.0.
    assert reenabled.command_steps_s == -300.0


def test_pid_output_clamped_to_motor_limits():
    from hardware.drivers.mock_stepper import MockStepperDriver
    from hardware.sim.leveling import LevelingLoop

    # balance_pid.hpp:20-21: output_min/max = +/-1600 (host_test.cpp:182-183
    # "output clamped to motor limit" with a huge error).
    for track_pitch, expected in ((200.0, -1600.0), (-200.0, 1600.0)):
        mock = MockStepperDriver({"control_dt_s": 0.01})
        mock.initialize()
        loop = LevelingLoop(
            stepper=mock,
            control_hz=100,
            kp=15.0,
            ki=0.0,
            kd=1.0,
            track_profile=lambda t, p=track_pitch: p,
        )
        loop.start()
        tel = loop.step()
        # Raw kp*error = 15 * -/+200 = -/+3000 steps/s, clamped to the limits.
        assert tel.command_steps_s == expected
        assert loop.output_min_steps_s == -1600.0
        assert loop.output_max_steps_s == 1600.0


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