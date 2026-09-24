/**
 * OpenJ5 MPU6050 IMU driver (I2C) + Madgwick fusion for Node 7.
 *
 * Mounted on the BODY (ADR-017): measures absolute pitch vs gravity at
 * imu_sample_hz (default 200 Hz). Uses the legacy ESP-IDF i2c master driver
 * (`driver/i2c.h`), present in IDF v5.2. Address 0x68 = AD0 low
 * (config: "address": 104 decimal).
 */
#pragma once

#include <cstdint>

#include "driver/i2c.h"
#include "esp_err.h"
#include "imu/madgwick.hpp"

namespace openj5 {

struct ImuSample {
    float ax_g = 0.0f, ay_g = 0.0f, az_g = 1.0f;  ///< accel in g
    float gx_dps = 0.0f, gy_dps = 0.0f, gz_dps = 0.0f;  ///< gyro in deg/s
    float temp_c = 0.0f;
};

class Mpu6050 {
public:
    struct Config {
        gpio_num_t sda_pin = GPIO_NUM_8;
        gpio_num_t scl_pin = GPIO_NUM_9;
        uint8_t address = 104;             ///< 0x68, AD0 to GND
        uint32_t sample_rate_hz = 200;
        float madgwick_beta = 0.1f;
    };

    /// Bring up the bus and the sensor; ESP_OK only when WHO_AM_I matches.
    esp_err_t init(const Config& cfg);
    void deinit();

    /// Read one sample (true on bus success).
    bool read_sample(ImuSample& out);

    /// read_sample + fused Madgwick update; false on repeated bus errors.
    bool update(float dt);

    /// Fused pitch vs gravity, degrees (+ = nose up per mount in
    /// docs/hardware/BENCH_BALANCE.md: Z up, Y left-to-right).
    float pitch_deg() const { return filter_.pitch_deg(); }
    float roll_deg() const { return filter_.roll_deg(); }

    /// False after consecutive bus errors (fail-safe input for the controller).
    bool healthy() const { return healthy_; }
    uint32_t error_count() const { return errors_; }

private:
    esp_err_t write_reg(uint8_t reg, uint8_t value);
    esp_err_t read_regs(uint8_t reg, uint8_t* buf, size_t len);

    Config cfg_{};
    Madgwick filter_;
    bool installed_ = false;
    bool healthy_ = false;
    uint32_t errors_ = 0;
};

}  // namespace openj5
