/**
 * OpenJ5 WiFi station bring-up with auto-reconnect (ADR-013 local-first, no
 * cloud). Every node uses this to reach the broker; credentials come from
 * Kconfig (never committed - set via menuconfig or sdkconfig.local).
 */
#pragma once

#include <atomic>
#include <cstdint>

#include "esp_err.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

namespace openj5 {

class WifiStation {
public:
    struct Config {
        const char* ssid = "";
        const char* password = "";
        uint32_t connect_timeout_ms = 30000;
    };

    /// Full bring-up (netif/event loop/wifi). Blocks until an IP is obtained
    /// or the timeout expires; reconnects forever on later drops.
    /// ESP_ERR_TIMEOUT = not connected yet (keeps retrying in background).
    esp_err_t start(const Config& cfg);
    void stop();

    bool connected() const;
    int reconnect_count() const { return reconnects_.load(); }

private:
    static void event_handler(void* arg, esp_event_base_t base, int32_t event_id,
                              void* event_data);

    EventGroupHandle_t group_ = nullptr;
    esp_event_handler_instance_t wifi_inst_ = nullptr;
    esp_event_handler_instance_t ip_inst_ = nullptr;
    std::atomic<int> reconnects_{0};
    bool started_ = false;
};

}  // namespace openj5
