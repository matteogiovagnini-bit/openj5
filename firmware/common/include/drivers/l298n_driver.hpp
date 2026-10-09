/**
 * OpenJ5 L298N driver - production firmware implementation of IMotorDriver
 * (ADR-005 / ADR-018). ESP32-S3, Node 6 tracks: 2 DC gear motors.
 *
 * PWM: LEDC on ENA/ENB (config: pwm_frequency_hz / pwm_resolution_bits, e.g.
 * 1000 Hz / 10 bit). Direction: plain GPIO on IN1..IN4 mapped through the pure
 * motor::motor_levels(). Velocity ramps come from motor::ramp_schedule() and
 * are advanced by tick(dt) from the control task, so a command never blocks the
 * real-time loop with per-step sleeps (unlike the host Python bench driver).
 *
 * Threading: the control task owns the LEDC/GPIO writes; other tasks only
 * publish a clamped target via set_velocity() (atomic mailbox). get_velocity()
 * reads an atomic mirror.
 *
 * All pins/limits come from Kconfig == config/node6_tracks/node.json (ADR-008).
 */
#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "hal/motor_driver.hpp"

namespace openj5 {

struct L298NMotorConfig {
    gpio_num_t enable_pin = GPIO_NUM_NC;  ///< ENA/ENB (LEDC PWM)
    gpio_num_t in_a_pin = GPIO_NUM_NC;    ///< IN1/IN3 (forward)
    gpio_num_t in_b_pin = GPIO_NUM_NC;    ///< IN2/IN4 (reverse)
    ledc_channel_t channel = LEDC_CHANNEL_0;
    bool inverted = false;  ///< swap forward/reverse without touching wiring
};

struct L298NConfig {
    L298NMotorConfig left{};
    L298NMotorConfig right{};
    double min_velocity = -1.0;
    double max_velocity = 1.0;
    double pwm_frequency_hz = 1000.0;
    int pwm_resolution_bits = 10;
    double ramp_step = 0.1;     ///< velocity increment per ramp step
    double ramp_seconds = 0.05; ///< total ramp duration (0 = apply at once)
    ledc_timer_t timer = LEDC_TIMER_0;
    ledc_mode_t speed_mode = LEDC_LOW_SPEED_MODE;
};

class L298NDriver : public IMotorDriver {
public:
    explicit L298NDriver(const L298NConfig& cfg);
    ~L298NDriver() override;

    void initialize() override;
    std::vector<std::string> motor_names() const override;
    void set_velocity(const std::string& motor_id, double velocity) override;
    double get_velocity(const std::string& motor_id) const override;
    void stop_all() override;
    void brake_all() override;
    void shutdown() override;

    /// Advance the pending velocity ramps by dt and (re)apply the levels.
    /// Call from the control task at a fixed cadence (control_hz).
    void tick(double dt);

    bool initialized() const { return initialized_; }

private:
    struct Channel {
        L298NMotorConfig pins{};
        double target = 0.0;             ///< control-task owned
        double applied = 0.0;            ///< control-task owned
        std::vector<double> schedule;    ///< control-task owned
        std::size_t next = 0;
        double elapsed = 0.0;
        double step_dt = 0.0;
    };

    void halt(bool brake);
    void start_channel(Channel& channel, double target);
    void apply_velocity(Channel& channel, double velocity);
    void brake_channel(Channel& channel);
    uint32_t max_duty() const;

    L298NConfig cfg_;
    Channel left_{};
    Channel right_{};
    std::atomic<double> left_target_cmd_{0.0};   ///< set_velocity -> tick
    std::atomic<double> right_target_cmd_{0.0};
    std::atomic<double> left_velocity_{0.0};      ///< tick -> get_velocity
    std::atomic<double> right_velocity_{0.0};
    bool initialized_ = false;
};

}  // namespace openj5
