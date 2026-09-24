/**
 * OpenJ5 A4988 STEP/DIR driver - production firmware implementation of
 * IStepperDriver (ADR-005 / ADR-017). ESP32-S3, Node 7 balance joint.
 *
 * Pulse generation: a periodic esp_timer toggles the STEP pin; rising edges
 * are the microsteps and are counted into `position_` (open loop, exactly one
 * count per pulse). The timer period derives from the current velocity, which
 * the control task updates each tick via `tick(dt)`:
 *
 *   v_tgt = position mode ? sign*min(vmax, sqrt(2*a*remaining)) : PID command
 *   v_now = slew(v_now, v_tgt, accel, dt)        // ramp up/down bounded
 *   period = toggle_interval_us(v_now)           // 0 below min pulse rate
 *
 * All motion state is owned by the control task; other tasks read the atomic
 * position/velocity only. ENABLE is active LOW; coils stay de-energized until
 * enable() (enabled_on_boot = false per config/node7_balance/node.json).
 */
#pragma once

#include <atomic>
#include <cstdint>

#include "driver/gpio.h"
#include "esp_timer.h"
#include "hal/stepper_driver.hpp"

namespace openj5 {

struct A4988Config {
    gpio_num_t step_pin = GPIO_NUM_4;
    gpio_num_t dir_pin = GPIO_NUM_5;
    gpio_num_t enable_pin = GPIO_NUM_6;
    bool dir_inverted = false;        ///< swap CW/CCW without touching wiring
    double max_velocity = 1600.0;     ///< steps/s (config: max_speed_steps_s)
    double max_accel = 800.0;         ///< steps/s^2 (config: max_acceleration)
    int64_t min_position = -1244;     ///< -35 deg at 35.556 steps/deg
    int64_t max_position = 1244;      ///< +35 deg
    double min_pulse_hz = 5.0;        ///< below this: hold instead of pulsing
    int position_snap_steps = 2;      ///< declare target reached within N steps
};

class A4988Driver : public IStepperDriver {
public:
    explicit A4988Driver(const A4988Config& cfg);
    ~A4988Driver() override;

    void initialize() override;
    void enable() override;
    void disable() override;
    bool set_position_steps(int64_t steps) override;
    void set_velocity_steps_s(double steps_s) override;
    int64_t get_position_steps() const override;
    double get_velocity_steps_s() const override;
    void home() override;
    void brake() override;
    void shutdown() override;

    /// Control-task tick: slews velocity, advances the position profile and
    /// (re)starts the pulse timer. Call at a fixed rate (control_hz).
    void tick(double dt);

    /// Velocity ceiling for position moves (tilt speed scaling); clamped.
    void set_max_velocity(double steps_s);

    /// True while executing a position move (tilt/stow).
    bool positioning() const { return pos_mode_; }
    bool enabled() const { return enabled_; }

private:
    static void pulse_timer_cb(void* arg);
    void set_direction(int sign);
    void update_timer();

    A4988Config cfg_;
    esp_timer_handle_t timer_ = nullptr;
    bool timer_running_ = false;
    bool initialized_ = false;
    bool enabled_ = false;

    std::atomic<int64_t> position_{0};
    std::atomic<int> dir_sign_{1};
    std::atomic<bool> step_level_{false};
    std::atomic<double> velocity_{0.0};

    bool pos_mode_ = false;
    int64_t target_ = 0;
    double v_now_ = 0.0;
    double v_tgt_ = 0.0;
    double vmax_ = 0.0;
    uint32_t last_period_us_ = 0;
};

}  // namespace openj5
