#include "comms/wifi_station.hpp"

#include <cstdio>
#include <cstring>

#include "esp_log.h"

namespace openj5 {

namespace {
const char* TAG = "wifi";
constexpr EventBits_t kGotIpBit = BIT0;
}

esp_err_t WifiStation::start(const Config& cfg) {
    if (started_) {
        return ESP_OK;
    }
    if (cfg.ssid == nullptr || cfg.ssid[0] == '\0') {
        ESP_LOGE(TAG, "WiFi SSID not configured (idf.py menuconfig -> "
                      "OpenJ5 Node 7 Balance -> WiFi SSID)");
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t err = esp_netif_init();
    if (err != ESP_OK) {
        return err;
    }
    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

    group_ = xEventGroupCreate();
    if (group_ == nullptr) {
        return ESP_ERR_NO_MEM;
    }
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &WifiStation::event_handler, this, &wifi_inst_));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &WifiStation::event_handler, this, &ip_inst_));

    wifi_config_t wifi_cfg = {};
    // strlcpy is BSD/newlib-only and invisible under -std=c++20: snprintf gives
    // the same bounded, NUL-terminated copy using standard C++.
    std::snprintf(reinterpret_cast<char*>(wifi_cfg.sta.ssid),
                  sizeof(wifi_cfg.sta.ssid), "%s", cfg.ssid);
    std::snprintf(reinterpret_cast<char*>(wifi_cfg.sta.password),
                  sizeof(wifi_cfg.sta.password), "%s", cfg.password);
    wifi_cfg.sta.threshold.authmode =
        cfg.password[0] == '\0' ? WIFI_AUTH_OPEN : WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());
    started_ = true;

    const EventBits_t bits =
        xEventGroupWaitBits(group_, kGotIpBit, pdFALSE, pdFALSE,
                            pdMS_TO_TICKS(cfg.connect_timeout_ms));
    if ((bits & kGotIpBit) == 0) {
        ESP_LOGW(TAG, "no IP after %lu ms (auto-reconnect keeps retrying)",
                 static_cast<unsigned long>(cfg.connect_timeout_ms));
        return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

void WifiStation::stop() {
    if (!started_) {
        return;
    }
    esp_wifi_disconnect();
    esp_wifi_stop();
    esp_wifi_deinit();
    if (group_ != nullptr) {
        vEventGroupDelete(group_);
        group_ = nullptr;
    }
    started_ = false;
}

bool WifiStation::connected() const {
    if (group_ == nullptr) {
        return false;
    }
    return (xEventGroupGetBits(group_) & kGotIpBit) != 0;
}

void WifiStation::event_handler(void* arg, esp_event_base_t base, int32_t event_id,
                                void* event_data) {
    auto* self = static_cast<WifiStation*>(arg);
    if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        const auto* disconnected =
            static_cast<const wifi_event_sta_disconnected_t*>(event_data);
        const int attempt = ++self->reconnects_;
        xEventGroupClearBits(self->group_, kGotIpBit);
        if (attempt % 10 == 1) {
            ESP_LOGW(TAG, "disconnected (reason %d, attempt %d) - reconnecting",
                     disconnected->reason, attempt);
        }
        esp_wifi_connect();
    } else if (base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        const auto* got_ip = static_cast<const ip_event_got_ip_t*>(event_data);
        ESP_LOGI(TAG, "got IP: " IPSTR " (rssi attempt %d)", IP2STR(&got_ip->ip_info.ip),
                 self->reconnects_.load());
        xEventGroupSetBits(self->group_, kGotIpBit);
    }
}

}  // namespace openj5
