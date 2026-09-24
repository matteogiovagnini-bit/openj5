/**
 * OpenJ5 MQTT client wrapper (esp-mqtt): connect/reconnect, subscribe and
 * thread-safe publish for the node's logical commands and telemetry
 * (ADR-006 logical commands, ADR-015 topics, ADR-013 mTLS when built with
 * OPENJ5_MQTT_TLS + certs embedded by the node's main component).
 */
#pragma once

#include <atomic>
#include <cstdint>

#include "esp_err.h"
#include "mqtt_client.h"

namespace openj5 {

class MqttClient {
public:
    struct Config {
        const char* uri = "mqtt://openj5-core:1883";  ///< mqtt:// or mqtts://
        const char* client_id = "openj5-node";
        uint16_t keepalive_s = 60;
    };

    /// topic + payload of one PUBLISH received on a subscribed topic.
    using DataHandler =
        void (*)(void* ctx, const char* topic, const uint8_t* payload, int len);
    /// Called on every (re)connect: resubscribe + republish retained state.
    using ConnectHandler = void (*)();

    esp_err_t start(const Config& cfg);
    void stop();

    bool connected() const { return connected_.load(); }
    esp_err_t publish(const char* topic, const char* payload, bool retain = false,
                      int qos = 0);
    esp_err_t subscribe(const char* topic, int qos = 1);

    void set_handlers(DataHandler data, void* data_ctx, ConnectHandler on_connect);

private:
    static void event_handler(void* arg, esp_event_base_t base, int32_t event_id,
                              void* event_data);

    esp_mqtt_client_handle_t client_ = nullptr;
    std::atomic<bool> connected_{false};
    DataHandler data_handler_ = nullptr;
    void* data_ctx_ = nullptr;
    ConnectHandler on_connect_ = nullptr;
};

}  // namespace openj5
