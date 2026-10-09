/**
 * OpenJ5 pure motor math for DC drivers (no I/O, host-testable).
 *
 * 1:1 mirror of src/hardware/hal/motor.py (ADR-018): the real ESP32-S3 Node 6
 * driver and the host Python HAL (real bench + Digital-Twin mock) share the
 * exact same clamp/mapping/ramp semantics, so behaviour cannot drift between
 * the two sides. Header-only and free of ESP-IDF includes on purpose: the same
 * code compiles under g++/clang on the host (scripts/test/host_firmware.sh) and
 * under xtensa-esp32s3-elf-g++ in the firmware build.
 *
 * Contract (velocity is normalized and signed in [-1.0, +1.0]):
 *   clamp_velocity(v, min, max)  -> clamped v; config error if min > max
 *   motor_levels(v)              -> direction GPIO levels + PWM duty
 *   ramp_schedule(cur, tgt, step)-> per-step ramp values landing on tgt
 */
#pragma once

#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <stdexcept>
#include <vector>

namespace openj5::motor {

/// Immutable hardware level snapshot for one DC motor channel.
struct MotorLevels {
    bool forward = false;  ///< IN1/IN3 level: one direction
    bool reverse = false;  ///< IN2/IN4 level: the opposite direction
    double duty = 0.0;     ///< PWM duty in [0.0, 1.0]
};

namespace detail {

/// A misconfigured limit is a config error, never something to guess
/// deterministically (Python raises ValueError). On the host (exceptions on)
/// this throws; on ESP-IDF (-fno-exceptions) it asserts/aborts, the firmware
/// hard-fail equivalent.
[[noreturn]] inline void config_error(const char* message) {
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS)
    throw std::invalid_argument(message);
#else
    (void)message;
    assert(false && "OpenJ5 motor config error");
    std::abort();
#endif
}

}  // namespace detail

/// Clamp `velocity` into [min_velocity, max_velocity].
/// Raises a config error if the bounds are inverted (min > max).
inline double clamp_velocity(double velocity, double min_velocity,
                             double max_velocity) {
    if (min_velocity > max_velocity) {
        detail::config_error("inverted velocity limits: min > max");
    }
    if (velocity < min_velocity) {
        return min_velocity;
    }
    if (velocity > max_velocity) {
        return max_velocity;
    }
    return velocity;
}

/// Map a signed velocity to direction GPIO levels + PWM duty (pure).
/// duty = min(1, abs(v)); forward for v > 0, reverse for v < 0, both false at 0.
inline MotorLevels motor_levels(double velocity) {
    const double duty = std::fmin(1.0, std::fabs(velocity));
    if (velocity > 0.0) {
        return MotorLevels{true, false, duty};
    }
    if (velocity < 0.0) {
        return MotorLevels{false, true, duty};
    }
    return MotorLevels{false, false, 0.0};
}

/// Intermediate velocity values from the first ramp step up to `target`.
/// The last element is exactly `target` (the final increment may be shorter
/// than `step`). `current == target` returns an empty schedule; a non-positive
/// `step` is a config error.
inline std::vector<double> ramp_schedule(double current, double target, double step) {
    if (step <= 0.0) {
        detail::config_error("ramp step must be > 0");
    }
    const double delta = target - current;
    if (delta == 0.0) {
        return {};
    }
    const double direction = delta > 0.0 ? 1.0 : -1.0;
    const double distance = std::fabs(delta);
    const auto count = static_cast<long>(std::ceil(distance / step));
    std::vector<double> schedule;
    schedule.reserve(static_cast<std::size_t>(count));
    for (long k = 1; k <= count; ++k) {
        const double increment = std::fmin(static_cast<double>(k) * step, distance);
        schedule.push_back(current + direction * increment);
    }
    return schedule;
}

}  // namespace openj5::motor
