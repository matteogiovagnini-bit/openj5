#include "drivers/mpu6050_driver.hpp"

#include <cmath>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace openj5 {

namespace {
const char* TAG = "mpu6050";

constexpr uint8_t kRegSmplrtDiv = 0x19;
constexpr uint8_t kRegConfig = 0x1A;
constexpr uint8_t kRegGyroConfig = 0x1B;
constexpr uint8_t kRegAccelConfig = 0x1C;
constexpr uint8_t kRegAccelXOutH = 0x3B;
constexpr uint8_t kRegPwrMgmt1 = 0x6B;
constexpr uint8_t kRegWhoAmI = 0x75;
constexpr uint8_t kWhoAmIValue = 0x68;

constexpr float kAccelLsbPerG = 16384.0f;   // +/- 2 g full scale
constexpr float kGyroLsbPerDps = 65.5f;      // +/- 500 deg/s full scale
constexpr float kRadToDeg = 57.29577951308232f;

int16_t be16(const uint8_t* p) {
    return static_cast<int16_t>((static_cast<uint16_t>(p[0]) << 8) | p[1]);
}
}  // namespace

esp_err_t Mpu6050::write_reg(uint8_t reg, uint8_t value) {
    return i2c_master_write_to_device(I2C_NUM_0, cfg_.address, &reg, 1,
                                      pdMS_TO_TICKS(50)) == ESP_OK &&
                   i2c_master_write_to_device(I2C_NUM_0, cfg_.address, &value, 1,
                                              pdMS_TO_TICKS(50)) == ESP_OK
               ? ESP_OK
               : ESP_FAIL;
}

esp_err_t Mpu6050::read_regs(uint8_t reg, uint8_t* buf, size_t len) {
    return i2c_master_write_read_device(I2C_NUM_0, cfg_.address, &reg, 1, buf, len,
                                        pdMS_TO_TICKS(50)) == ESP_OK
               ? ESP_OK
               : ESP_FAIL;
}

esp_err_t Mpu6050::init(const Config& cfg) {
    cfg_ = cfg;
    filter_ = Madgwick(cfg.madgwick_beta);

    i2c_config_t conf = {};
    conf.mode = I2C_MODE_MASTER;
    conf.sda_io_num = cfg.sda_pin;
    conf.scl_io_num = cfg.scl_pin;
    conf.sda_pullup_en = GPIO_PULLUP_ENABLE;
    conf.scl_pullup_en = GPIO_PULLUP_ENABLE;
    conf.master.clk_speed = 400000;
    conf.clk_flags = I2C_SCLK_SRC_FLAG_FOR_NOMAL;  // any available clock source
    ESP_ERROR_CHECK(i2c_param_config(I2C_NUM_0, &conf));
    esp_err_t err = i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    installed_ = true;

    uint8_t who = 0;
    err = read_regs(kRegWhoAmI, &who, 1);
    if (err != ESP_OK || who != kWhoAmIValue) {
        ESP_LOGE(TAG, "WHO_AM_I=0x%02x (expected 0x%02x): %s", who, kWhoAmIValue,
                 esp_err_to_name(err));
        healthy_ = false;
        return ESP_ERR_NOT_FOUND;
    }

    write_reg(kRegPwrMgmt1, 0x80);  // device reset
    vTaskDelay(pdMS_TO_TICKS(100));
    write_reg(kRegPwrMgmt1, 0x01);  // clock source: PLL X gyro
    // Sample rate: gyro output 1 kHz (DLPF on) / (1 + div) = sample_rate_hz
    const uint8_t div =
        static_cast<uint8_t>(1000 / (cfg.sample_rate_hz > 0 ? cfg.sample_rate_hz : 200) -
                             1);
    write_reg(kRegSmplrtDiv, div);
    write_reg(kRegConfig, 0x03);      // DLPF 44 Hz accel / 42 Hz gyro
    write_reg(kRegGyroConfig, 0x08);  // +/- 500 dps
    write_reg(kRegAccelConfig, 0x00); // +/- 2 g

    healthy_ = true;
    errors_ = 0;
    ESP_LOGI(TAG, "ready: addr=0x%02x rate=%lu Hz beta=%.2f",
             cfg.address, static_cast<unsigned long>(cfg.sample_rate_hz),
             static_cast<double>(cfg.madgwick_beta));
    return ESP_OK;
}

void Mpu6050::deinit() {
    if (installed_) {
        i2c_driver_delete(I2C_NUM_0);
        installed_ = false;
    }
    healthy_ = false;
}

bool Mpu6050::read_sample(ImuSample& out) {
    uint8_t raw[14];
    if (read_regs(kRegAccelXOutH, raw, sizeof(raw)) != ESP_OK) {
        if (++errors_ > 10) {
            healthy_ = false;
        }
        return false;
    }
    out.ax_g = static_cast<float>(be16(&raw[0])) / kAccelLsbPerG;
    out.ay_g = static_cast<float>(be16(&raw[2])) / kAccelLsbPerG;
    out.az_g = static_cast<float>(be16(&raw[4])) / kAccelLsbPerG;
    out.temp_c = static_cast<float>(be16(&raw[6])) / 340.0f + 36.53f;
    out.gx_dps = static_cast<float>(be16(&raw[8])) / kGyroLsbPerDps;
    out.gy_dps = static_cast<float>(be16(&raw[10])) / kGyroLsbPerDps;
    out.gz_dps = static_cast<float>(be16(&raw[12])) / kGyroLsbPerDps;
    errors_ = 0;
    healthy_ = true;
    return true;
}

bool Mpu6050::update(float dt) {
    ImuSample s;
    if (!read_sample(s)) {
        return false;
    }
    filter_.update(dt, s.gx_dps / kRadToDeg, s.gy_dps / kRadToDeg,
                   s.gz_dps / kRadToDeg, s.ax_g, s.ay_g, s.az_g);
    return true;
}

}  // namespace openj5
