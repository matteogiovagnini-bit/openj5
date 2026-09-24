/**
 * OpenJ5 IStepperDriver - C++ port of the HAL port defined in
 * src/hardware/hal/stepper.py (ADR-005 / ADR-017).
 *
 * Same contract on every backend: an ESP32 A4988 driver (this firmware),
 * the Raspberry Pi bench driver (Python) or the Gazebo/mock adapters.
 * Pure interface: no ESP-IDF includes, so it also compiles on the host for
 * the shared unit tests (scripts/test/host_firmware.sh).
 */
#pragma once

#include <cstdint>

namespace openj5 {

struct StepperState {
    int64_t position_steps = 0;
    double velocity_steps_s = 0.0;
    bool enabled = false;
    bool moving = false;
    bool home_reached = false;
};

class IStepperDriver {
public:
    virtual ~IStepperDriver() = default;

    virtual void initialize() = 0;
    virtual void enable() = 0;                   ///< energize coils (hold torque)
    virtual void disable() = 0;                  ///< release coils (free shaft)
    virtual bool set_position_steps(int64_t steps) = 0;  ///< false if out of limits
    virtual void set_velocity_steps_s(double steps_s) = 0;
    virtual int64_t get_position_steps() const = 0;
    virtual double get_velocity_steps_s() const = 0;
    virtual void home() = 0;                     ///< move to absolute zero (no endstop)
    virtual void brake() = 0;                    ///< stop and hold
    virtual void shutdown() = 0;                 ///< release everything, safe twice
};

}  // namespace openj5
