#include "comms/mqtt_client.hpp"

#include "esp_log.h"

#if OPENJ5_MQTT_TLS
// Embedded by the node's main component (EMBED_FILES): PEM documents must end
// with a NUL byte, which IDF appends to embedded binary data.
extern "C" {
extern const uint8_t _binary_certs_ca_crt_start[] asm("_binary_certs_ca_crt_start");
extern const uint8_t _binary_certs_ca_crt_end[] asm("_binary_certs_ca_crt_end");
extern const uint8_t _binary_certs_node7_crt_start[] asm("_binary_certs_node7_crt_start");
extern const uint8_t _binary_certs_node7_crt_end[] asm("_binary_certs_node7_crt_end");
extern const uint8_t _binary_certs_node7_key_start[] asm("_binary_certs_node7_key_start");
extern const uint8_t _binary_certs_node7_key_end[] asm("_binary_certs_node7_key_end");
}
#endif  // OPENJ5_MQTT_TLS

namespace openj5 {

namespace {
const char* TAG = "mqtt";
}

esp_err_t MqttClient::start(const Config& cfg) {
    if (client_ != nullptr) {
        return ESP_ERR_INVALID_STATE;
    }

    esp_mqtt_client_config_t mqtt_cfg = {};
    mqtt_cfg.broker.address.uri = cfg.uri;
    mqtt_cfg.credentials.client_id = cfg.client_id;
    mqtt_cfg.session.keepalive = cfg.keepalive_s;

#if OPENJ5_MQTT_TLS
    // CA used to verify the broker. IDF 5.5's esp-mqtt names it
    // verification.certificate (older releases used cacert); CI never
    // compiles this block (TLS off), only the bench build does.
    mqtt_cfg.broker.verification.certificate =
        reinterpret_cast<const char*>(_binary_certs_ca_crt_start);
    mqtt_cfg.broker.verification.certificate_len =
        static_cast<size_t>(_binary_certs_ca_crt_end - _binary_certs_ca_crt_start);
    mqtt_cfg.credentials.authentication.certificate =
        reinterpret_cast<const char*>(_binary_certs_node7_crt_start);
    mqtt_cfg.credentials.authentication.certificate_len = static_cast<size_t>(
        _binary_certs_node7_crt_end - _binary_certs_node7_crt_start);
    mqtt_cfg.credentials.authentication.key =
        reinterpret_cast<const char*>(_binary_certs_node7_key_start);
    mqtt_cfg.credentials.authentication.key_len = static_cast<size_t>(
        _binary_certs_node7_key_end - _binary_certs_node7_key_start);
    ESP_LOGI(TAG, "starting with mTLS (broker certs validated, node7 cert embedded)");
#else
    ESP_LOGW(TAG,
             "starting WITHOUT TLS (bench/dev build): production broker listens on "
             "8883 mTLS only - build with OPENJ5_MQTT_TLS=y + main/certs/ (ADR-013)");
#endif

    client_ = esp_mqtt_client_init(&mqtt_cfg);
    if (client_ == nullptr) {
        return ESP_FAIL;
    }
    // MQTT_EVENT_ANY (-1, esp_mqtt_event_id_t) is esp-mqtt's own "any event"
    // id: register_event takes the esp-mqtt enum (not esp-event's id type).
    esp_mqtt_client_register_event(client_, MQTT_EVENT_ANY, &MqttClient::event_handler,
                                   this);
    return esp_mqtt_client_start(client_);
}

void MqttClient::stop() {
    if (client_ == nullptr) {
        return;
    }
    esp_mqtt_client_stop(client_);
    esp_mqtt_client_destroy(client_);
    client_ = nullptr;
    connected_.store(false);
}

esp_err_t MqttClient::publish(const char* topic, const char* payload, bool retain,
                              int qos) {
    if (client_ == nullptr || !connected_.load()) {
        return ESP_ERR_INVALID_STATE;
    }
    const int msg_id = esp_mqtt_client_publish(client_, topic, payload, 0, qos,
                                               retain ? 1 : 0);
    return msg_id < 0 ? ESP_FAIL : ESP_OK;
}

esp_err_t MqttClient::subscribe(const char* topic, int qos) {
    if (client_ == nullptr || !connected_.load()) {
        return ESP_ERR_INVALID_STATE;
    }
    const int msg_id = esp_mqtt_client_subscribe(client_, topic, qos);
    return msg_id < 0 ? ESP_FAIL : ESP_OK;
}

void MqttClient::set_handlers(DataHandler data, void* data_ctx,
                              ConnectHandler on_connect) {
    data_handler_ = data;
    data_ctx_ = data_ctx;
    on_connect_ = on_connect;
}

void MqttClient::event_handler(void* arg, esp_event_base_t /*base*/, int32_t event_id,
                               void* event_data) {
    auto* self = static_cast<MqttClient*>(arg);
    auto* event = static_cast<esp_mqtt_event_handle_t>(event_data);

    switch (event->event_id) {
        case MQTT_EVENT_CONNECTED:
            self->connected_.store(true);
            ESP_LOGI(TAG, "connected (client_id=%s)",
                     event->client != nullptr ? "ok" : "?");
            if (self->on_connect_ != nullptr) {
                self->on_connect_();  // resubscribe + republish retained state
            }
            break;
        case MQTT_EVENT_DISCONNECTED:
            self->connected_.store(false);
            ESP_LOGW(TAG, "disconnected - esp-mqtt reconnects automatically");
            break;
        case MQTT_EVENT_DATA:
            if (self->data_handler_ != nullptr && event->topic != nullptr) {
                self->data_handler_(self->data_ctx_, event->topic,
                                    reinterpret_cast<const uint8_t*>(event->data),
                                    event->data_len);
            }
            break;
        default:
            break;
    }
}

}  // namespace openj5
