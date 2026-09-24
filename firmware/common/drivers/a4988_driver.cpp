#include "drivers/a4988_driver.hpp"

#include "esp_log.h"
#include "hal/stepper_logic.hpp"

namespace openj5 {

namespace {
const char* TAG = "a4988";
}

A4988Driver::A4988Driver(const A4988Config& cfg) : cfg_(cfg), vmax_(cfg.max_velocity) {}

A4988Driver::~A4988Driver() { shutdown(); }

void A4988Driver::initialize() {
    if (initialized_) {
        return;
    }
    gpio_config_t out = {};
    out.pin_bit_mask = (1ULL << cfg_.step_pin) | (1ULL << cfg_.dir_pin) |
                       (1ULL << cfg_.enable_pin);
    out.mode = GPIO_MODE_OUTPUT;
    out.pull_up_en = GPIO_PULLUP_DISABLE;
    out.pull_down_en = GPIO_PULLDOWN_DISABLE;
    out.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&out));

    gpio_set_level(cfg_.step_pin, 0);
    step_level_.store(false);
    set_direction(1);
    gpio_set_level(cfg_.enable_pin, 1);  // ENABLE active LOW: 1 = released

    esp_timer_create_args_t targs = {};
    targs.callback = &A4988Driver::pulse_timer_cb;
    targs.arg = this;
    targs.dispatch_method = ESP_TIMER_TASK;
    targs.name = "a4988_step";
    ESP_ERROR_CHECK(esp_timer_create(&targs, &timer_));

    initialized_ = true;
    ESP_LOGI(TAG, "initialized: STEP=%d DIR=%d EN=%d vmax=%.0f amax=%.0f",
             static_cast<int>(cfg_.step_pin), static_cast<int>(cfg_.dir_pin),
             static_cast<int>(cfg_.enable_pin), vmax_, cfg_.max_accel);
}

void A4988Driver::pulse_timer_cb(void* arg) {
    auto* self = static_cast<A4988Driver*>(arg);
    const bool level = !self->step_level_.load();
    self->step_level_.store(level);
    gpio_set_level(self->cfg_.step_pin, level ? 1 : 0);
    if (level) {  // rising edge = one microstep
        self->position_ += self->dir_sign_.load();
    }
}

void A4988Driver::set_direction(int sign) {
    dir_sign_.store(sign);
    int level = (sign > 0) ? 1 : 0;
    if (cfg_.dir_inverted) {
        level = 1 - level;
    }
    gpio_set_level(cfg_.dir_pin, level);
}

void A4988Driver::update_timer() {
    const uint32_t period = motion::toggle_interval_us(v_now_, cfg_.min_pulse_hz);
    const bool want_pulsing = period > 0;

    // Direction changes only while pulses are stopped (slew always crosses
    // zero below min_pulse_hz first, but guard anyway: never flip DIR under
    // an in-flight pulse train).
    const int want_dir = v_now_ >= 0.0 ? 1 : -1;
    const bool dir_changed = want_dir != dir_sign_.load();
    if (dir_changed && v_now_ != 0.0) {
        if (timer_running_) {
            esp_timer_stop(timer_);
            timer_running_ = false;
            step_level_.store(false);
            gpio_set_level(cfg_.step_pin, 0);
        }
        set_direction(want_dir);
    }

    if (!want_pulsing) {
        if (timer_running_) {
            esp_timer_stop(timer_);
            timer_running_ = false;
        }
        step_level_.store(false);
        gpio_set_level(cfg_.step_pin, 0);
        last_period_us_ = 0;
        return;
    }

    if (!timer_running_) {
        last_period_us_ = period;
        esp_timer_start_periodic(timer_, period);
        timer_running_ = true;
    } else if (period != last_period_us_) {
        last_period_us_ = period;
        esp_timer_restart(timer_, period);
    }
}

void A4988Driver::tick(double dt) {
    if (!initialized_) {
        return;
    }
    if (pos_mode_) {
        const double remaining = static_cast<double>(target_ - position_.load());
        if (std::fabs(remaining) <= cfg_.position_snap_steps) {
            pos_mode_ = false;  // at target (<= 2 steps, 0.06 deg)
            v_tgt_ = 0.0;
        } else {
            v_tgt_ = motion::position_velocity_target(remaining, vmax_, cfg_.max_accel);
        }
    }
    v_now_ = motion::slew(v_now_, v_tgt_, cfg_.max_accel, dt);
    velocity_.store(v_now_);
    update_timer();
}

void A4988Driver::set_max_velocity(double steps_s) {
    vmax_ = motion::clamp(steps_s, 1.0, cfg_.max_velocity);
}

void A4988Driver::enable() {
    if (!initialized_) {
        return;
    }
    gpio_set_level(cfg_.enable_pin, 0);
    enabled_ = true;
}

void A4988Driver::disable() {
    if (!initialized_) {
        return;
    }
    v_now_ = v_tgt_ = 0.0;
    velocity_.store(0.0);
    pos_mode_ = false;
    update_timer();
    gpio_set_level(cfg_.enable_pin, 1);
    enabled_ = false;
}

bool A4988Driver::set_position_steps(int64_t steps) {
    // HAL contract: out-of-limits violations are REJECTED, never executed.
    if (steps < cfg_.min_position || steps > cfg_.max_position) {
        ESP_LOGW(TAG, "position %lld outside limits [%lld, %lld] - rejected",
                 static_cast<long long>(steps), static_cast<long long>(cfg_.min_position),
                 static_cast<long long>(cfg_.max_position));
        return false;
    }
    if (!enabled_) {
        enable();
    }
    target_ = steps;
    pos_mode_ = true;
    return true;
}

void A4988Driver::set_velocity_steps_s(double steps_s) {
    const double clamped = motion::clamp(steps_s, -cfg_.max_velocity, cfg_.max_velocity);
    if (clamped != 0.0 && !enabled_) {
        enable();
    }
    pos_mode_ = false;
    v_tgt_ = clamped;
}

int64_t A4988Driver::get_position_steps() const { return position_.load(); }

double A4988Driver::get_velocity_steps_s() const { return velocity_.load(); }

void A4988Driver::home() {
    // No endstop yet (HAL contract: implementation-defined). Absolute zero is
    // the stow reference; the body-pitch IMU closes the absolute error.
    set_position_steps(0);
}

void A4988Driver::brake() {
    v_now_ = v_tgt_ = 0.0;
    velocity_.store(0.0);
    pos_mode_ = false;
    update_timer();  // stops pulsing
    enable();        // energized coils = holding torque
}

void A4988Driver::shutdown() {
    if (!initialized_) {
        return;
    }
    v_now_ = v_tgt_ = 0.0;
    velocity_.store(0.0);
    pos_mode_ = false;
    if (timer_running_) {
        esp_timer_stop(timer_);
        timer_running_ = false;
    }
    esp_timer_delete(timer_);
    timer_ = nullptr;
    gpio_set_level(cfg_.enable_pin, 1);
    gpio_set_level(cfg_.step_pin, 0);
    step_level_.store(false);
    enabled_ = false;
    initialized_ = false;
    ESP_LOGI(TAG, "shutdown (position=%lld)",
             static_cast<long long>(position_.load()));
}

}  // namespace openj5
