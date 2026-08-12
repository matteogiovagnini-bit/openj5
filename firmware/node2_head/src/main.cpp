/**
 * OpenJ5 Node 2 - Head Controller
 * 
 * ESP32-S3 Firmware for head control:
 * - 6 Servos: Neck Yaw/Pitch/Roll, Eyes H/V, Eyelids
 * - WS2812 LED Strip (12 LEDs)
 * - SSD1306 OLED Display (128x64)
 * - 2x I2S MEMS Microphones
 * - MPU6050 IMU
 * - VL53L0X ToF Sensor
 * - MQTT Communication
 * - OTA Updates
 */

#include "head_controller.hpp"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "protocol_examples_common.h"
#include "esp_ota_ops.h"
#include "esp_app_format.h"

static const char* TAG = "node2_head";

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "OpenJ5 Node 2 - Head Controller Starting");
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "Firmware version: %s", CONFIG_APP_PROJECT_VER);
    ESP_LOGI(TAG, "Compile time: %s %s", __DATE__, __TIME__);

    // Print chip info
    esp_chip_info_t chip_info;
    esp_chip_info(&chip_info);
    ESP_LOGI(TAG, "Chip: %s rev %d (%d cores)", 
             CONFIG_IDF_TARGET, chip_info.revision, chip_info.cores);

    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition truncated, erasing...");
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize network stack
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Connect to WiFi
    ESP_ERROR_CHECK(example_connect());

    // Get MAC address for node identification
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    ESP_LOGI(TAG, "MAC Address: %02x:%02x:%02x:%02x:%02x:%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    // Create and initialize head controller
    openj5::node2::HeadController head;

    ret = head.initialize();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Head controller initialization failed: %s", esp_err_to_name(ret));
        esp_restart();
    }

    ESP_LOGI(TAG, "Head controller initialized successfully");

    // Start head controller (starts all tasks)
    ret = head.start();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Head controller start failed: %s", esp_err_to_name(ret));
        esp_restart();
    }

    ESP_LOGI(TAG, "Head controller running");
    ESP_LOGI(TAG, "State: %s", head.get_state_name());

    // Main loop - monitor and report status
    uint32_t loop_count = 0;
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(10000));  // 10 second status report

        loop_count++;
        if (loop_count % 6 == 0) {  // Every minute
            ESP_LOGI(TAG, "=== Status Report ===");
            ESP_LOGI(TAG, "State: %s", head.get_state_name());
            ESP_LOGI(TAG, "Uptime: %lu seconds", loop_count * 10);
            ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());
            ESP_LOGI(TAG, "Min free heap: %lu bytes", esp_get_minimum_free_heap_size());
            
            // Print servo positions
            for (int i = 0; i < 6; i++) {
                auto state = head.get_servo_state(i);
                if (state.has_value()) {
                    ESP_LOGI(TAG, "Servo %d (%s): pos=%.1f target=%.1f moving=%s",
                             i, head.get_servo_name(i).c_str(),
                             state->position_deg, state->target_deg,
                             state->moving ? "yes" : "no");
                }
            }
        }

        // Check WiFi connection
        if (!example_is_connected()) {
            ESP_LOGW(TAG, "WiFi disconnected, reconnecting...");
            ESP_ERROR_CHECK(example_connect());
        }
    }
}