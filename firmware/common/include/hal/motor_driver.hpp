/**
 * OpenJ5 IMotorDriver - C++ port of the HAL port defined in
 * src/hardware/hal/motor.py (ADR-005 / ADR-018).
 *
 * Same contract on every backend: the ESP32-S3 L298N driver (this firmware,
 * Node 6), the retired Raspberry Pi bench driver (Python) and the
 * MockMotorDriver (Digital Twin, ADR-010). Pure interface: no ESP-IDF includes,
 * so it also compiles on the host for the shared unit tests.
 *
 * Velocity is normalized and signed in [-1.0, +1.0] (magnitude = PWM duty, sign
 * = direction). Out-of-range values are clamped by the implementation.
 * `brake_all()` (both direction pins high, PWM 0 = hold) is distinct from
 * `stop_all()` (direction pins low, PWM 0 = coast), and `shutdown()` is
 * idempotent ("safe to call twice", ADR-018).
 */
#pragma once

#include <string>
#include <vector>

namespace openj5 {

class IMotorDriver {
public:
    virtual ~IMotorDriver() = default;

    /// Identifiers of the configured motor channels, in config order.
    virtual std::vector<std::string> motor_names() const = 0;

    /// Bring the driver up: configure pins/board and create the channels.
    virtual void initialize() = 0;

    /// Set signed normalized velocity in [-1.0, +1.0]; sign selects direction.
    /// Violations of the configured limits are clamped, not executed raw.
    virtual void set_velocity(const std::string& motor_id, double velocity) = 0;

    /// Last commanded signed velocity for `motor_id`.
    virtual double get_velocity(const std::string& motor_id) const = 0;

    /// Coast every motor to 0 (direction pins low, PWM 0).
    virtual void stop_all() = 0;

    /// Brake every motor (both direction pins high, PWM 0) to hold it.
    virtual void brake_all() = 0;

    /// Release every resource; leaves the motors free. Safe to call twice.
    virtual void shutdown() = 0;
};

}  // namespace openj5
