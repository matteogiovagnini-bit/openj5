/**
 * OpenJ5 pure motion math for STEP/DIR steppers (no I/O, host-testable).
 *
 * Corrected semantics versus the Python reference
 * src/hardware/hal/stepper.py::trapezoid_velocity: that one is stateless and
 * therefore only produces a braking curve - from standstill it jumps straight
 * to sqrt(2*a*d) (measured: 1410 steps/s on a full sweep instead of ramping
 * at +800 steps/s2) and its `+ accel * dt` term can never bind. On a real
 * motor that means missed steps.
 *
 * The C++ driver tracks velocity state and applies BOTH bounds each tick:
 *   v_tgt = sign * min(vmax, brake_bound(remaining))   // never too fast to stop
 *   v_now = slew(v_now, v_tgt, accel, dt)              // ramp up/down limited
 * Python must be aligned in T-029.
 */
#pragma once

#include <cmath>
#include <cstdint>

namespace openj5::motion {

/// Clamp helper.
inline double clamp(double v, double lo, double hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

/// Slew limit: move `v_now` toward `v_tgt` by at most `accel * dt`.
/// This is what ramps the axis up from rest (the piece the Python reference
/// is missing) and brakes it when reversing.
inline double slew(double v_now, double v_tgt, double accel, double dt) {
    const double dv = accel * dt;
    if (v_tgt > v_now + dv) {
        return v_now + dv;
    }
    if (v_tgt < v_now - dv) {
        return v_now - dv;
    }
    return v_tgt;
}

/// Maximum speed from which `accel` can still stop within `steps_remaining`.
/// 0 at the target.
inline double brake_bound(double steps_remaining, double accel) {
    const double d = std::fabs(steps_remaining);
    return std::sqrt(2.0 * accel * d);
}

/// Position-move velocity target at this control tick (then slew-limited):
/// 0 exactly on target, otherwise sign * min(vmax, brake_bound).
inline double position_velocity_target(double steps_remaining, double vmax,
                                       double accel) {
    if (steps_remaining == 0.0) {
        return 0.0;
    }
    const double sign = steps_remaining > 0.0 ? 1.0 : -1.0;
    const double v_cap = brake_bound(steps_remaining, accel);
    return sign * (vmax < v_cap ? vmax : v_cap);
}

/// Toggle period (microseconds) for the STEP pin given the step frequency:
/// the pin is toggled by a periodic timer, so rising edges (= steps) happen
/// at half the toggle rate. Returns 0 below `min_freq_hz` (hold, coils stay on).
inline uint32_t toggle_interval_us(double steps_per_s, double min_freq_hz) {
    const double f = steps_per_s < 0.0 ? -steps_per_s : steps_per_s;
    if (f < min_freq_hz) {
        return 0;
    }
    const double toggles_per_s = 2.0 * f;  // one rising edge every 2 toggles
    const double period = 1000000.0 / toggles_per_s;
    if (period < 1.0) {
        return 1;
    }
    return static_cast<uint32_t>(period + 0.5);
}

}  // namespace openj5::motion
