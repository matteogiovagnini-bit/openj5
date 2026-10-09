#include "drivers/l298n_driver.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

#include "esp_err.h"
#include "esp_log.h"
#include "hal/motor_logic.hpp"

namespace openj5 {

namespace {
const char* TAG = "l298n";
constexpr const char* kLeftName = "left";
constexpr const char* kRightName = "right";
}  // namespace

L298NDriver::L298NDriver(const L298NConfig& cfg) : cfg_(cfg) {}

L298NDriver::~L298NDriver() { shutdown(); }

uint32_t L298NDriver::max_duty() const {
    return (1u << static_cast<unsigned>(cfg_.pwm_resolution_bits)) - 1u;
}

std::vector<std::string> L298NDriver::motor_names() const {
    return {kLeftName, kRightName};
}

void L298NDriver::initialize() {
    if (initialized_) {
        return;
    }
    // Pins are mandatory config (no magic defaults): fail loudly if unset.
    for (const Channel* channel : {&left_, &right_}) {
        if (channel->pins.enable_pin == GPIO_NUM_NC ||
            channel->pins.in_a_pin == GPIO_NUM_NC ||
            channel->pins.in_b_pin == GPIO_NUM_NC) {
            ESP_LOGE(TAG, "unconfigured motor pins (enable/in_a/in_b must be set)");
            return;
        }
    }

    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << left_.pins.in_a_pin) | (1ULL << left_.pins.in_b_pin) |
                      (1ULL << right_.pins.in_a_pin) | (1ULL << right_.pins.in_b_pin);
    io.mode = GPIO_MODE_OUTPUT;
    io.pull_up_en = GPIO_PULLUP_DISABLE;
    io.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&io));

    // Direction pins low -> coast at boot (motors free, safe default).
    for (const Channel* channel : {&left_, &right_}) {
        gpio_set_level(channel->pins.in_a_pin, 0);
        gpio_set_level(channel->pins.in_b_pin, 0);
    }

    ledc_timer_config_t timer = {};
    timer.speed_mode = cfg_.speed_mode;
    timer.duty_resolution = static_cast<ledc_timer_bit_t>(cfg_.pwm_resolution_bits);
    timer.timer_num = cfg_.timer;
    timer.freq_hz = static_cast<uint32_t>(cfg_.pwm_frequency_hz);
    timer.clk_cfg = LEDC_AUTO_CLK;
    ESP_ERROR_CHECK(ledc_timer_config(&timer));

    for (const Channel* channel : {&left_, &right_}) {
        ledc_channel_config_t ch = {};
        ch.gpio_num = channel->pins.enable_pin;
        ch.speed_mode = cfg_.speed_mode;
        ch.channel = channel->pins.channel;
        ch.intr_type = LEDC_INTR_DISABLE;
        ch.timer_sel = cfg_.timer;
        ch.duty = 0;
        ch.hpoint = 0;
        ESP_ERROR_CHECK(ledc_channel_config(&ch));
    }

    initialized_ = true;
    ESP_LOGI(TAG,
             "initialized: ENA=%d IN1=%d IN2=%d | ENB=%d IN3=%d IN4=%d | "
             "pwm=%u Hz %d bit, ramp step=%.2f %.0f ms",
             static_cast<int>(left_.pins.enable_pin),
             static_cast<int>(left_.pins.in_a_pin),
             static_cast<int>(left_.pins.in_b_pin),
             static_cast<int>(right_.pins.enable_pin),
             static_cast<int>(right_.pins.in_a_pin),
             static_cast<int>(right_.pins.in_b_pin),
             static_cast<unsigned>(cfg_.pwm_frequency_hz), cfg_.pwm_resolution_bits,
             cfg_.ramp_step, cfg_.ramp_seconds * 1000.0);
}

void L298NDriver::apply_velocity(Channel& channel, double velocity) {
    motor::MotorLevels levels = motor::motor_levels(velocity);
    bool forward = levels.forward;
    bool reverse = levels.reverse;
    if (channel.pins.inverted) {
        std::swap(forward, reverse);
    }
    gpio_set_level(channel.pins.in_a_pin, forward ? 1 : 0);
    gpio_set_level(channel.pins.in_b_pin, reverse ? 1 : 0);
    const uint32_t duty = static_cast<uint32_t>(
        std::lround(levels.duty * static_cast<double>(max_duty())));
    ledc_set_duty(cfg_.speed_mode, channel.pins.channel, duty);
    ledc_update_duty(cfg_.speed_mode, channel.pins.channel);
}

void L298NDriver::brake_channel(Channel& channel) {
    // L298N short-brake: both inputs high, PWM 0 -> motor terminals shorted.
    gpio_set_level(channel.pins.in_a_pin, 1);
    gpio_set_level(channel.pins.in_b_pin, 1);
    ledc_set_duty(cfg_.speed_mode, channel.pins.channel, 0);
    ledc_update_duty(cfg_.speed_mode, channel.pins.channel);
}

void L298NDriver::start_channel(Channel& channel, double target) {
    channel.target = target;
    channel.schedule = motor::ramp_schedule(channel.applied, target, cfg_.ramp_step);
    channel.next = 0;
    channel.elapsed = 0.0;
    if (channel.schedule.empty()) {
        return;  // already there
    }
    if (cfg_.ramp_seconds <= 0.0) {
        for (double value : channel.schedule) {
            apply_velocity(channel, value);
        }
        channel.applied = channel.target;
        channel.schedule.clear();
        return;
    }
    channel.step_dt =
        cfg_.ramp_seconds / static_cast<double>(channel.schedule.size());
}

void L298NDriver::set_velocity(const std::string& motor_id, double velocity) {
    if (!initialized_) {
        return;
    }
    const double clamped =
        motor::clamp_velocity(velocity, cfg_.min_velocity, cfg_.max_velocity);
    if (motor_id == kLeftName) {
        left_target_cmd_.store(clamped);
    } else if (motor_id == kRightName) {
        right_target_cmd_.store(clamped);
    } else {
        ESP_LOGW(TAG, "unknown motor id '%s'", motor_id.c_str());
    }
}

double L298NDriver::get_velocity(const std::string& motor_id) const {
    if (motor_id == kLeftName) {
        return left_velocity_.load();
    }
    if (motor_id == kRightName) {
        return right_velocity_.load();
    }
    return 0.0;
}

void L298NDriver::tick(double dt) {
    if (!initialized_) {
        return;
    }
    const double targets[2] = {left_target_cmd_.load(), right_target_cmd_.load()};
    Channel* channels[2] = {&left_, &right_};
    for (int i = 0; i < 2; ++i) {
        Channel& channel = *channels[i];
        if (targets[i] != channel.target) {
            start_channel(channel, targets[i]);
        }
        if (channel.next >= channel.schedule.size() || channel.step_dt <= 0.0) {
            continue;
        }
        channel.elapsed += dt;
        while (channel.next < channel.schedule.size() &&
               channel.elapsed >= channel.step_dt) {
            apply_velocity(channel, channel.schedule[channel.next]);
            channel.applied = channel.schedule[channel.next];
            ++channel.next;
            channel.elapsed -= channel.step_dt;
        }
    }
    left_velocity_.store(left_.applied);
    right_velocity_.store(right_.applied);
}

void L298NDriver::halt(bool brake) {
    left_target_cmd_.store(0.0);
    right_target_cmd_.store(0.0);
    for (Channel* channel : {&left_, &right_}) {
        channel->target = 0.0;
        channel->applied = 0.0;
        channel->schedule.clear();
        channel->next = 0;
        channel->elapsed = 0.0;
        if (brake) {
            brake_channel(*channel);
        } else {
            apply_velocity(*channel, 0.0);
        }
    }
    left_velocity_.store(0.0);
    right_velocity_.store(0.0);
}

void L298NDriver::stop_all() { halt(/*brake=*/false); }

void L298NDriver::brake_all() { halt(/*brake=*/true); }

void L298NDriver::shutdown() {
    if (!initialized_) {
        return;
    }
    halt(/*brake=*/false);  // release: motors free
    ledc_stop(cfg_.speed_mode, left_.pins.channel, 0);
    ledc_stop(cfg_.speed_mode, right_.pins.channel, 0);
    initialized_ = false;
    ESP_LOGI(TAG, "shutdown (motors released)");
}

}  // namespace openj5
