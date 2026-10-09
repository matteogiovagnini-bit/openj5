"""Motion-math parity tests: Python HAL vs firmware/common (T-029).

Every constant is taken from the C++ reference that defines the behaviour:
  - firmware/common/include/hal/stepper_logic.hpp (openj5::motion::*)
  - firmware/common/test/host_test.cpp (host vectors, line noted per test)
"""
import math

from hardware.hal.stepper import (
    brake_bound,
    position_velocity_target,
    slew,
    trapezoid_velocity,
)


def test_slew_ramps_from_rest_at_accel_per_tick():
    # host_test.cpp:39-43: 10 ticks slew(0 -> 1600.0, accel 800, dt 0.01)
    # must equal 800 * 0.01 * 10 = 80 steps/s, never a jump to sqrt(2ad).
    v = 0.0
    for _ in range(10):
        v = slew(v, 1600.0, 800.0, 0.01)
    assert math.isclose(v, 80.0, rel_tol=0.0, abs_tol=1e-9)


def test_slew_decel_is_limited_to_one_tick():
    # host_test.cpp:44: slew(1600.0 -> -1600.0, accel 800, dt 0.01) == 1592.0
    # (= 1600 - 800 * 0.01: the direction flip takes many ticks, no teleport).
    assert slew(1600.0, -1600.0, 800.0, 0.01) == 1592.0


def test_slew_passes_small_gaps_through():
    # host_test.cpp:45-46: within accel*dt of the target, slew returns it.
    assert math.isclose(slew(10.0, 15.0, 800.0, 0.01), 15.0, rel_tol=0.0, abs_tol=1e-9)


def test_brake_bound_is_sqrt_2ad():
    # host_test.cpp:49-50: brake_bound(1244.0, 800.0) == sqrt(2 * 800 * 1244).
    assert math.isclose(
        brake_bound(1244.0, 800.0),
        math.sqrt(2.0 * 800.0 * 1244.0),
        rel_tol=0.0,
        abs_tol=1e-6,
    )


def test_brake_bound_at_target_is_zero():
    # host_test.cpp:51: brake_bound(0.0, 800.0) == 0.0.
    assert brake_bound(0.0, 800.0) == 0.0


def test_position_velocity_target_is_zero_on_target_and_signed():
    # stepper_logic.hpp:51-59: 0 exactly on target, else sign * min(vmax, bound).
    assert position_velocity_target(0.0, 1600.0, 800.0) == 0.0
    # 1600 steps away: sqrt(2 * 800 * 1600) = 1600 = vmax -> capped at vmax.
    assert position_velocity_target(1600.0, 1600.0, 800.0) == 1600.0
    assert position_velocity_target(-1600.0, 1600.0, 800.0) == -1600.0
    # Close to target the brake bound binds: sqrt(2 * 800 * 8) < vmax.
    assert math.isclose(
        position_velocity_target(8.0, 1600.0, 800.0),
        math.sqrt(2.0 * 800.0 * 8.0),
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_trapezoid_velocity_is_the_cpp_composition():
    # trapezoid_velocity == slew(v_now, position_velocity_target(...), accel, dt),
    # the mirror of stepper_logic.hpp:31-59 assembled the way the C++ driver does
    # (a4988_driver.cpp:116-119).
    assert trapezoid_velocity(0.0, 1244.0, 1600.0, 800.0, 0.01) == slew(
        0.0, position_velocity_target(1244.0, 1600.0, 800.0), 800.0, 0.01
    )


def test_trapezoid_velocity_ramps_from_rest_not_to_brake_bound():
    # The T-029 defect: the old stateless profile jumped straight to
    # sqrt(2*a*d) ~ 1410 steps/s on a full sweep (stepper_logic.hpp:4-9).
    # Now the first tick from rest is exactly accel * dt (host_test.cpp:64).
    first = trapezoid_velocity(0.0, 1244.0, 1600.0, 800.0, 0.01)
    assert first == 800.0 * 0.01  # 8.0 steps/s, NOT sqrt(2 * 800 * 1244) ~ 1410
    assert first < math.sqrt(2.0 * 800.0 * 1244.0)


def test_full_position_move_parity_with_host_test():
    # host_test.cpp:53-76: full sweep 0 -> 1244 steps, vmax 1600, accel 800,
    # dt 0.01: starts at rest, reaches the target, respects the accel bound.
    vmax, accel, dt = 1600.0, 800.0, 0.01
    target = 1244.0
    pos, vel, ticks = 0.0, 0.0, 0
    while pos != target and ticks < 100000:
        remaining = target - pos
        vel = trapezoid_velocity(vel, remaining, vmax, accel, dt)
        if ticks == 0:
            # host_test.cpp:64: first tick ramps, does not jump.
            assert vel <= accel * dt + 1e-9
        pos += vel * dt
        if remaining > 0 and pos > target:
            pos = target  # integer step snap (<= 2 steps), host_test.cpp:67-69
        ticks += 1
    assert pos == target  # host_test.cpp:72
    assert ticks < 100000  # host_test.cpp:73: move terminates
    # host_test.cpp:74-76: cannot be faster than the triangular accel bound.
    min_ticks = math.sqrt(2.0 * 1244.0 / accel) / dt
    assert ticks >= min_ticks * 0.9
