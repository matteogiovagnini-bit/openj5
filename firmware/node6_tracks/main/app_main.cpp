/**
 * OpenJ5 Node 6 - Tracks Controller (ESP32-S3 + L298N) - application entry
 * (ADR-002 / ADR-018 / ADR-019).
 *
 * Wiring diagram and bench procedure: docs/hardware/BENCH_*.md (T-022).
 * Config parity: config/node6_tracks/node.json <-> main/Kconfig.projbuild
 * (enforced by the Node 6 parity test, T-032).
 *
 * Boot sequence (ADR-009 state machine, motors RELEASED on boot):
 *   Boot -> Init -> [peripherals ok] Ready, then on the first motion command
 *   -> Running. Every fault -> Error (motors braked).
 *
 * Tasks:
 *   - "tracks" @ control_hz (default 50 Hz): mailbox, ramp, fail-safes and the
 *               ADR-009 state machine; publishes via the MQTT sink.
 *   - app_main : 5 s monitor (heap, state, control liveness -> reboot).
 *
 * Threading: MQTT callbacks only queue into the controller's atomics; the
 * control task owns the L298N driver and the state machine. See
 * track_controller.hpp.
 */
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "command_handler.hpp"
#include "comms/mqtt_client.hpp"
#include "comms/wifi_station.hpp"
#include "drivers/l298n_driver.hpp"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "track_controller.hpp"

using namespace openj5;

static const char* TAG = "node6";

// A Kconfig bool is #define'd only when 'y' (absent from sdkconfig.h when 'n'),
// so expose it as a real constant via #ifdef.
#ifdef CONFIG_OPENJ5_MQTT_TLS
constexpr bool kMqttTls = true;
#else
constexpr bool kMqttTls = false;
#endif

// ------------------------------------------------------------------ globals --
// Wired once in app_main (single-threaded phase), read-only afterwards.
static MqttClient* g_mqtt = nullptr;
static TrackController* g_controller = nullptr;
static CommandHandler* g_command_handler = nullptr;
static char g_cmd_topic[96];
static char g_estop_topic[96];
static char g_state_topic[96];
static char g_evt_topic[96];
static char g_telemetry_topic[96];

static inline uint32_t now_ms() {
    return static_cast<uint32_t>(esp_timer_get_time() / 1000);
}

// -------------------------------------------------------------------- sink --
class MqttTrackSink : public ITrackSink {
public:
    explicit MqttTrackSink(MqttClient& mqtt) : mqtt_(mqtt) {}

    void init_topics(const char* prefix) {
        std::snprintf(g_cmd_topic, sizeof(g_cmd_topic), "%s/cmd", prefix);
        std::snprintf(g_state_topic, sizeof(g_state_topic), "%s/state", prefix);
        std::snprintf(g_evt_topic, sizeof(g_evt_topic), "%s/evt", prefix);
        std::snprintf(g_telemetry_topic, sizeof(g_telemetry_topic), "%s/telemetry",
                      prefix);
        // System-wide emergency stop (config/common/topics.json -> system).
        std::snprintf(g_estop_topic, sizeof(g_estop_topic),
                      "openj5/v1/system/emergency_stop");
    }

    void publish_state(const char* state_json) override {
        mqtt_.publish(g_state_topic, state_json, /*retain=*/true, /*qos=*/1);
    }
    void publish_event(const char* json) override {
        mqtt_.publish(g_evt_topic, json, /*retain=*/false, /*qos=*/1);
    }
    void publish_telemetry(const char* json) override {
        mqtt_.publish(g_telemetry_topic, json, /*retain=*/false, /*qos=*/0);
    }

private:
    MqttClient& mqtt_;
};

static void on_mqtt_data(void* /*ctx*/, const char* topic, const uint8_t* payload,
                         int len) {
    if (std::strcmp(topic, g_cmd_topic) == 0) {
        g_command_handler->handle(reinterpret_cast<const char*>(payload), len);
    } else if (std::strcmp(topic, g_estop_topic) == 0) {
        // Payload ignored: ANY publish on the system E-stop stops the node.
        g_controller->cmd_stop("emergency");
    }
}

static void on_mqtt_connect() {
    g_mqtt->subscribe(g_cmd_topic, /*qos=*/1);
    g_mqtt->subscribe(g_estop_topic, /*qos=*/1);
    // State is retained, but republish the live value on every (re)connect so
    // transitions published while the node was offline are never lost.
    char buf[64];
    std::snprintf(buf, sizeof(buf), R"({"state":"%s"})",
                  to_string(g_controller->node_state()));
    g_mqtt->publish(g_state_topic, buf, /*retain=*/true, /*qos=*/1);
    ESP_LOGI(TAG, "MQTT connected: subscribed to %s and %s", g_cmd_topic,
             g_estop_topic);
}

// -------------------------------------------------------------------- tasks --
struct TaskArgs {
    MqttClient* mqtt;
    TrackController* ctrl;
};

static void control_task_fn(void* arg) {
    auto* args = static_cast<TaskArgs*>(arg);
    // 1000 Hz tick / control rate -> e.g. 50 Hz = 20 ms; never 0.
    TickType_t period = pdMS_TO_TICKS(1000 / CONFIG_OPENJ5_CONTROL_HZ);
    if (period == 0) {
        period = 1;
    }
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        // Liveness: a dropped broker becomes a fail-safe stop on the next tick.
        args->ctrl->set_link_ok(args->mqtt->connected());
        args->ctrl->tick(now_ms());
        vTaskDelayUntil(&wake, period);
    }
}

// ------------------------------------------------------------------ app_main --
extern "C" void app_main(void) {
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "OpenJ5 Node 6 - Tracks Controller");
    ESP_LOGI(TAG, "Firmware %s, built %s %s",
             esp_app_get_description()->version, __DATE__, __TIME__);
    ESP_LOGI(TAG, "========================================");

    // ---- NVS (WiFi storage) ----
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    // ---- Configuration: Kconfig == config/node6_tracks/node.json ----
    L298NConfig motor_cfg;
    motor_cfg.left.enable_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_ENA);
    motor_cfg.left.in_a_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_IN1);
    motor_cfg.left.in_b_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_IN2);
    motor_cfg.left.channel = LEDC_CHANNEL_0;
    motor_cfg.left.inverted = false;
    motor_cfg.right.enable_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_ENB);
    motor_cfg.right.in_a_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_IN3);
    motor_cfg.right.in_b_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_IN4);
    motor_cfg.right.channel = LEDC_CHANNEL_1;
    motor_cfg.right.inverted = false;
    motor_cfg.timer = LEDC_TIMER_0;
    motor_cfg.speed_mode = LEDC_LOW_SPEED_MODE;
    motor_cfg.pwm_frequency_hz = static_cast<double>(CONFIG_OPENJ5_PWM_FREQ_HZ);
    motor_cfg.pwm_resolution_bits = CONFIG_OPENJ5_PWM_RESOLUTION_BITS;
    motor_cfg.ramp_step = std::strtof(CONFIG_OPENJ5_RAMP_STEP, nullptr);
    motor_cfg.ramp_seconds = std::strtof(CONFIG_OPENJ5_RAMP_SECONDS, nullptr);
    motor_cfg.min_velocity = std::strtof(CONFIG_OPENJ5_MIN_VELOCITY, nullptr);
    motor_cfg.max_velocity = std::strtof(CONFIG_OPENJ5_MAX_VELOCITY, nullptr);

    TrackConfig track_cfg;
    track_cfg.default_velocity = std::strtof(CONFIG_OPENJ5_DEFAULT_VELOCITY, nullptr);
    track_cfg.min_velocity = motor_cfg.min_velocity;
    track_cfg.max_velocity = motor_cfg.max_velocity;
    track_cfg.watchdog_ms = CONFIG_OPENJ5_WATCHDOG_TIMEOUT_MS;
    track_cfg.telemetry_period_ms = CONFIG_OPENJ5_TELEMETRY_PERIOD_MS;
    track_cfg.control_dt_ms = 1000U / CONFIG_OPENJ5_CONTROL_HZ;

    ESP_LOGI(TAG,
             "pwm=%d Hz %d bit | ramp step=%.2f %.0f ms | limits [%.2f, %.2f] | "
             "watchdog=%u ms | control=%d Hz",
             CONFIG_OPENJ5_PWM_FREQ_HZ, CONFIG_OPENJ5_PWM_RESOLUTION_BITS,
             static_cast<double>(motor_cfg.ramp_step),
             static_cast<double>(motor_cfg.ramp_seconds) * 1000.0,
             motor_cfg.min_velocity, motor_cfg.max_velocity,
             static_cast<unsigned>(track_cfg.watchdog_ms), CONFIG_OPENJ5_CONTROL_HZ);

    // ---- Objects (constructed single-threaded, before tasks/MQTT start) ----
    MqttClient mqtt;
    MqttTrackSink sink(mqtt);
    sink.init_topics(CONFIG_OPENJ5_TOPIC_PREFIX);

    L298NDriver driver(motor_cfg);
    driver.initialize();  // direction pins low, PWM 0 -> motors released at boot

    TrackController ctrl(driver, track_cfg, sink);
    CommandHandler command_handler(ctrl, sink, track_cfg.default_velocity);
    g_mqtt = &mqtt;
    g_controller = &ctrl;
    g_command_handler = &command_handler;

    ctrl.notify(NodeEvent::InitStarted);  // Boot -> Init
    if (driver.initialized()) {
        ctrl.notify(NodeEvent::PeripheralsOk);  // Init -> Ready
    } else {
        ESP_LOGE(TAG, "L298N init failed: node boots in Error");
        ctrl.notify(NodeEvent::InitFault);  // Init -> Error
    }

    // ---- WiFi + MQTT ----
    WifiStation wifi;
    WifiStation::Config wifi_cfg;
    wifi_cfg.ssid = CONFIG_OPENJ5_WIFI_SSID;
    wifi_cfg.password = CONFIG_OPENJ5_WIFI_PASSWORD;
    if (wifi.start(wifi_cfg) != ESP_OK) {
        ESP_LOGW(TAG, "WiFi not up yet - MQTT connects as soon as it is");
    }

    char uri[128];
    std::snprintf(uri, sizeof(uri), "%s://%s:%d", kMqttTls ? "mqtts" : "mqtt",
                  CONFIG_OPENJ5_MQTT_HOST, CONFIG_OPENJ5_MQTT_PORT);
    MqttClient::Config mqtt_cfg;
    mqtt_cfg.uri = uri;
    mqtt_cfg.client_id = CONFIG_OPENJ5_MQTT_CLIENT_ID;
    mqtt_cfg.keepalive_s = CONFIG_OPENJ5_MQTT_KEEPALIVE;
    mqtt.set_handlers(&on_mqtt_data, nullptr, &on_mqtt_connect);
    ESP_ERROR_CHECK(mqtt.start(mqtt_cfg));

    // ---- Control task ----
    static TaskArgs s_args{&mqtt, &ctrl};
    xTaskCreate(&control_task_fn, "tracks", 4096, &s_args, 5, nullptr);

    // ---- Monitor (app_main loop): soft watchdog on the control task ----
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        const uint32_t last = ctrl.last_tick_ms();
        const uint32_t t = now_ms();
        if (last != 0 && (t - last) > track_cfg.watchdog_ms * 5U) {
            ESP_LOGE(TAG, "control task stalled for %lu ms - rebooting",
                     static_cast<unsigned long>(t - last));
            esp_restart();
        }
        ESP_LOGI(TAG, "state=%s mode=%s left=%.2f right=%.2f faulted=%s heap=%lu",
                 to_string(ctrl.node_state()), to_string(ctrl.mode()),
                 driver.get_velocity("left"), driver.get_velocity("right"),
                 ctrl.faulted() ? "yes" : "no",
                 static_cast<unsigned long>(esp_get_free_heap_size()));
    }
}
