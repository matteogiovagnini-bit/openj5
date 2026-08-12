"""
OpenJ5 Firmware - ESP-IDF Project Structure

This directory contains ESP-IDF C++20 firmware for all 6 nodes.
Each node has its own project with shared common library.

Structure:
firmware/
├── common/                 # Shared library (HAL, drivers, comms, state machine)
│   ├── CMakeLists.txt
│   ├── hal/               # Hardware Abstraction Layer interfaces
│   ├── drivers/           # Driver implementations
│   ├── comms/             # MQTT client, protocol handlers
│   ├── statemachine/      # State machine implementation
│   ├── config/            # Configuration parser
│   ├── ota/               # OTA update client
│   └── utils/             # Logging, CRC, math utilities
├── node1_robot_core/      # Not used (RPi runs Linux)
├── node2_head/            # ESP32-S3 Head Controller
├── node3_right_arm/       # ESP32-S3 Right Arm Controller
├── node4_left_arm/        # ESP32-S3 Left Arm Controller
├── node5_torso/           # ESP32 Torso Controller
└── node6_tracks/          # ESP32 Track Controller

Build:
    cd firmware/common && idf.py build
    cd firmware/node2_head && idf.py build flash monitor

Common Configuration (sdkconfig.defaults):
    - CONFIG_FREERTOS_HZ=1000
    - CONFIG_ESP32_DEFAULT_CPU_FREQ_MHZ=240
    - CONFIG_LOG_DEFAULT_LEVEL=3 (Info)
    - CONFIG_MBEDTLS_TLS_MODE=y
    - CONFIG_MQTT_PROTOCOL_311=y
    - CONFIG_SPI_FLASH_SIZE=4MB (or 8MB/16MB)

Node-Specific Configuration:
    - node2_head: PCA9685 @ 0x40, 6 servos, I2S mics, SSD1306 display, WS2812
    - node3_right_arm: PCA9685 @ 0x41, 6 servos
    - node4_left_arm: PCA9685 @ 0x42, 6 servos (mirrored)
    - node5_torso: PCA9685 @ 0x43, 4 servos, INA219, DS18B20
    - node6_tracks: L298N/TB6612, 2 DC motors + encoders, MPU6050, 2x VL53L0X
"""

# Example: node2_head/CMakeLists.txt
cmake_content = """
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(openj5_node2_head)

# Component requirements
set(COMPONENT_REQUIRES
    common
    esp_mqtt
    driver
    i2c
    spi_flash
    nvs_flash
    esp_timer
    freertos
)

# Include directories
target_include_directories(${COMPONENT_LIB} PRIVATE
    include
    ../common/include
)

# Source files
target_sources(${COMPONENT_LIB} PRIVATE
    src/main.cpp
    src/head_controller.cpp
    src/servo_manager.cpp
    src/motion_primitives.cpp
    src/display_manager.cpp
    src/audio_manager.cpp
    src/sensor_manager.cpp
)

# Compile options
target_compile_options(${COMPONENT_LIB} PRIVATE
    -std=c++20
    -Wall
    -Wextra
    -Wpedantic
    -Werror
)

# Link libraries
target_link_libraries(${COMPONENT_LIB} PRIVATE
    common
    ${IDF_MQTT_LIB}
)
"""

# Example: node2_head/src/main.cpp
main_cpp = """
#include "head_controller.hpp"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "protocol_examples_common.h"

static const char* TAG = "node2_head";

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "Starting OpenJ5 Node 2 - Head Controller");
    ESP_LOGI(TAG, "Firmware version: %s", CONFIG_APP_PROJECT_VER);

    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize network
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(example_connect());  // WiFi connection

    // Create and start head controller
    openj5::HeadController head;
    esp_err_t err = head.initialize();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Head controller init failed: %s", esp_err_to_name(err));
        return;
    }

    err = head.start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Head controller start failed: %s", esp_err_to_name(err));
        return;
    }

    ESP_LOGI(TAG, "Head controller running");

    // Main loop - FreeRTOS tasks handle everything
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        ESP_LOGI(TAG, "Head controller alive, state: %s", head.get_state_name());
    }
}
"""

# Example: common/include/openj5/hal/servo_driver.hpp
servo_driver_hpp = """
#ifndef OPENJ5_HAL_SERVO_DRIVER_HPP
#define OPENJ5_HAL_SERVO_DRIVER_HPP

#include <cstdint>
#include <vector>
#include <string>
#include "openj5/core/result.hpp"

namespace openj5::hal {

struct ServoConfig {
    std::string name;
    uint8_t channel;
    uint16_t min_pulse_us;    // e.g., 500
    uint16_t max_pulse_us;    // e.g., 2500
    uint16_t home_pulse_us;   // e.g., 1500
    float min_angle_deg;      // e.g., -90
    float max_angle_deg;      // e.g., 90
    float home_angle_deg;     // e.g., 0
    float max_speed_dps;      // deg/s
    float max_accel_dps2;     // deg/s^2
    float offset_deg;         // calibration offset
    bool reversed;            // direction
};

struct ServoState {
    float position_deg;
    float target_deg;
    float velocity_dps;
    bool moving;
    bool enabled;
    uint32_t error_count;
};

class IServoDriver {
public:
    virtual ~IServoDriver() = default;

    // Initialize driver with servo configurations
    virtual Result<void> initialize(const std::vector<ServoConfig>& configs) = 0;

    // Set servo position (degrees)
    virtual Result<void> set_position(uint8_t channel, float angle_deg, float speed_dps = 0) = 0;

    // Get current position
    virtual Result<float> get_position(uint8_t channel) const = 0;

    // Set speed limit
    virtual Result<void> set_speed(uint8_t channel, float speed_dps) = 0;

    // Move to home position
    virtual Result<void> home(uint8_t channel) = 0;

    // Enable/disable servo
    virtual Result<void> enable(uint8_t channel) = 0;
    virtual Result<void> disable(uint8_t channel) = 0;

    // Get servo state
    virtual Result<ServoState> get_state(uint8_t channel) const = 0;

    // Calibrate servo (set min/max/home)
    virtual Result<void> calibrate(uint8_t channel, 
                                   uint16_t min_pulse, 
                                   uint16_t max_pulse, 
                                   uint16_t home_pulse) = 0;

    // Emergency stop - all servos to safe position
    virtual Result<void> emergency_stop() = 0;

    // Shutdown
    virtual void shutdown() = 0;

    // Get number of channels
    virtual uint8_t channel_count() const = 0;
};

} // namespace openj5::hal

#endif // OPENJ5_HAL_SERVO_DRIVER_HPP
"""

# Example: common/src/drivers/pca9685_driver.cpp
pca9685_driver = """
#include "openj5/hal/servo_driver.hpp"
#include "driver/i2c.h"
#include "esp_log.h"
#include <cmath>

namespace openj5::drivers {

class PCA9685Driver : public hal::IServoDriver {
public:
    PCA9685Driver(i2c_port_t i2c_port, uint8_t address = 0x40, uint32_t freq_hz = 50)
        : i2c_port_(i2c_port), address_(address), freq_hz_(freq_hz) {}

    ~PCA9685Driver() override {
        shutdown();
    }

    Result<void> initialize(const std::vector<hal::ServoConfig>& configs) override {
        configs_ = configs;
        
        // Initialize I2C
        i2c_config_t conf = {
            .mode = I2C_MODE_MASTER,
            .sda_io_num = CONFIG_I2C_SDA_GPIO,
            .scl_io_num = CONFIG_I2C_SCL_GPIO,
            .sda_pullup_en = GPIO_PULLUP_ENABLE,
            .scl_pullup_en = GPIO_PULLUP_ENABLE,
            .master = { .clk_speed = 400000 }
        };
        ESP_ERROR_CHECK(i2c_param_config(i2c_port_, &conf));
        ESP_ERROR_CHECK(i2c_driver_install(i2c_port_, conf.mode, 0, 0, 0));

        // Reset PCA9685
        write_reg(0x00, 0x00);  // Mode 1: restart
        vTaskDelay(pdMS_TO_TICKS(10));
        
        // Set frequency
        set_pwm_freq(freq_hz_);
        
        // Enable auto-increment
        write_reg(0x00, 0x20);  // Mode 1: auto-increment
        
        // Initialize all channels to home
        for (const auto& config : configs_) {
            set_pwm(config.channel, 0, pulse_from_angle(config.home_angle_deg, config));
            states_[config.channel] = {
                .position_deg = config.home_angle_deg,
                .target_deg = config.home_angle_deg,
                .velocity_dps = 0,
                .moving = false,
                .enabled = true,
                .error_count = 0
            };
        }
        
        return Result<void>::ok();
    }

    Result<void> set_position(uint8_t channel, float angle_deg, float speed_dps) override {
        auto it = std::find_if(configs_.begin(), configs_.end(),
            [channel](const auto& c) { return c.channel == channel; });
        if (it == configs_.end()) {
            return Result<void>::fail("INVALID_CHANNEL", "Channel not configured");
        }

        const auto& config = *it;
        
        // Clamp to limits
        angle_deg = std::clamp(angle_deg, config.min_angle_deg, config.max_angle_deg);
        
        // Apply offset and reversal
        float raw_angle = config.reversed ? -angle_deg : angle_deg;
        raw_angle += config.offset_deg;
        
        // Convert to pulse
        uint16_t pulse = pulse_from_angle(raw_angle, config);
        
        // Set PWM
        set_pwm(channel, 0, pulse);
        
        // Update state
        auto& state = states_[channel];
        state.target_deg = angle_deg;
        state.moving = std::abs(state.position_deg - angle_deg) > 0.5f;
        
        return Result<void>::ok();
    }

    Result<float> get_position(uint8_t channel) const override {
        auto it = states_.find(channel);
        if (it != states_.end()) {
            return Result<float>::ok(it->second.position_deg);
        }
        return Result<float>::fail("NOT_FOUND", "Channel not found");
    }

    Result<void> set_speed(uint8_t channel, float speed_dps) override {
        // PCA9685 doesn't support speed control directly
        // Would need to implement in software (trajectory generation)
        return Result<void>::ok();
    }

    Result<void> home(uint8_t channel) override {
        auto it = std::find_if(configs_.begin(), configs_.end(),
            [channel](const auto& c) { return c.channel == channel; });
        if (it != configs_.end()) {
            return set_position(channel, it->home_angle_deg);
        }
        return Result<void>::fail("INVALID_CHANNEL", "Channel not configured");
    }

    Result<void> enable(uint8_t channel) override {
        auto it = states_.find(channel);
        if (it != states_.end()) {
            it->second.enabled = true;
            return Result<void>::ok();
        }
        return Result<void>::fail("NOT_FOUND", "Channel not found");
    }

    Result<void> disable(uint8_t channel) override {
        auto it = states_.find(channel);
        if (it != states_.end()) {
            it->second.enabled = false;
            // Set PWM to 0 (high impedance)
            set_pwm(channel, 0, 0);
            return Result<void>::ok();
        }
        return Result<void>::fail("NOT_FOUND", "Channel not found");
    }

    Result<hal::ServoState> get_state(uint8_t channel) const override {
        auto it = states_.find(channel);
        if (it != states_.end()) {
            return Result<hal::ServoState>::ok(it->second);
        }
        return Result<hal::ServoState>::fail("NOT_FOUND", "Channel not found");
    }

    Result<void> calibrate(uint8_t channel, uint16_t min_pulse, uint16_t max_pulse, uint16_t home_pulse) override {
        auto it = std::find_if(configs_.begin(), configs_.end(),
            [channel](const auto& c) { return c.channel == channel; });
        if (it != configs_.end()) {
            it->min_pulse_us = min_pulse;
            it->max_pulse_us = max_pulse;
            it->home_pulse_us = home_pulse;
            return Result<void>::ok();
        }
        return Result<void>::fail("INVALID_CHANNEL", "Channel not configured");
    }

    Result<void> emergency_stop() override {
        // Move all servos to home position at max speed
        for (const auto& config : configs_) {
            set_pwm(config.channel, 0, config.home_pulse_us);
            states_[config.channel].position_deg = config.home_angle_deg;
            states_[config.channel].target_deg = config.home_angle_deg;
            states_[config.channel].moving = false;
        }
        return Result<void>::ok();
    }

    void shutdown() override {
        emergency_stop();
        i2c_driver_delete(i2c_port_);
    }

    uint8_t channel_count() const override {
        return 16;
    }

private:
    i2c_port_t i2c_port_;
    uint8_t address_;
    uint32_t freq_hz_;
    std::vector<hal::ServoConfig> configs_;
    std::unordered_map<uint8_t, hal::ServoState> states_;

    void write_reg(uint8_t reg, uint8_t value) {
        uint8_t data[2] = {reg, value};
        i2c_master_write_to_device(i2c_port_, address_, data, 2, pdMS_TO_TICKS(100));
    }

    uint8_t read_reg(uint8_t reg) {
        uint8_t value;
        i2c_master_write_read_device(i2c_port_, address_, &reg, 1, &value, 1, pdMS_TO_TICKS(100));
        return value;
    }

    void set_pwm_freq(uint32_t freq_hz) {
        float prescale_val = 25000000.0f / (4096.0f * freq_hz) - 1.0f;
        uint8_t prescale = static_cast<uint8_t>(std::round(prescale_val));
        
        uint8_t old_mode = read_reg(0x00);
        write_reg(0x00, (old_mode & 0x7F) | 0x10);  // Sleep
        write_reg(0xFE, prescale);                   // Prescale
        write_reg(0x00, old_mode);                   // Wake
        vTaskDelay(pdMS_TO_TICKS(5));
        write_reg(0x00, old_mode | 0xA1);            // Auto-increment + restart
    }

    void set_pwm(uint8_t channel, uint16_t on, uint16_t off) {
        uint8_t base = 0x06 + 4 * channel;
        uint8_t data[5] = {
            base,
            static_cast<uint8_t>(on & 0xFF),
            static_cast<uint8_t>(on >> 8),
            static_cast<uint8_t>(off & 0xFF),
            static_cast<uint8_t>(off >> 8)
        };
        i2c_master_write_to_device(i2c_port_, address_, data, 5, pdMS_TO_TICKS(100));
    }

    uint16_t pulse_from_angle(float angle_deg, const hal::ServoConfig& config) {
        // Map angle to pulse
        float angle_range = config.max_angle_deg - config.min_angle_deg;
        float pulse_range = config.max_pulse_us - config.min_pulse_us;
        float ratio = (angle_deg - config.min_angle_deg) / angle_range;
        return static_cast<uint16_t>(config.min_pulse_us + ratio * pulse_range);
    }
};

} // namespace openj5::drivers
"""

print("Firmware structure created!")
print("Common HAL interfaces, PCA9685 driver, and node2_head example provided.")