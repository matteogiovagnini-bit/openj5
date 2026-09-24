/**
 * Node 7 balance PID - PURE logic (no ESP-IDF), 1:1 parity with the validated
 * simulation in src/hardware/sim/leveling.py (ADR-017):
 *
 *     error = target_pitch - body_pitch
 *     command = kp*error + ki*integral + kd*(error-last_error)/dt   [steps/s]
 *
 * Integral is clamped BEFORE the increment (same order as the Python sim),
 * output is clamped to the motor limits, and the caller zeroes the command
 * inside the deadband to avoid micro-oscillation. Gains come from
 * config/node7_balance/node.json via Kconfig (kept in sync by
 * tests/unit/test_node7_config_sync.py).
 */
#pragma once

struct BalancePidParams {
    float kp = 15.0f;
    float ki = 1.0f;
    float kd = 0.3f;
    float output_min = -1600.0f;
    float output_max = 1600.0f;
    float integral_min = -4000.0f;
    float integral_max = 4000.0f;
};

class BalancePid {
public:
    explicit BalancePid(const BalancePidParams& params) : p_(params) { reset(); }

    void reset() {
        integral_ = 0.0f;
        last_error_ = 0.0f;
        first_ = true;
    }

    /// One PID iteration; `error` in degrees, `dt` in seconds.
    /// `enabled=false` keeps state but outputs 0 (mirrors the sim).
    float update(float error, float dt, bool enabled) {
        if (!enabled) {
            last_error_ = error;
            first_ = true;
            return 0.0f;
        }
        // Clamp BEFORE incrementing, exactly like the Python reference.
        integral_ = integral_ < p_.integral_min ? p_.integral_min : integral_;
        integral_ = integral_ > p_.integral_max ? p_.integral_max : integral_;
        integral_ += error * dt;

        const float derivative = first_ ? 0.0f : (error - last_error_) / dt;
        first_ = false;
        last_error_ = error;

        float command = p_.kp * error + p_.ki * integral_ + p_.kd * derivative;
        command = command < p_.output_min ? p_.output_min : command;
        command = command > p_.output_max ? p_.output_max : command;
        return command;
    }

    float integral() const { return integral_; }

private:
    BalancePidParams p_;
    float integral_ = 0.0f;
    float last_error_ = 0.0f;
    bool first_ = true;
};
