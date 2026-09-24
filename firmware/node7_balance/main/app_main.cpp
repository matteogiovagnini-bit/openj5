/**
 * OpenJ5 Node 7 - Balance Controller (ESP32-S3) - application entry (ADR-017).
 *
 * Wiring diagram and bench procedure: docs/hardware/BENCH_BALANCE.md
 * Config parity: config/node7_balance/node.json <-> main/Kconfig.projbuild,
 * enforced by tests/unit/test_node7_config_sync.py.
 *
 * Boot sequence (ADR-009 state machine, coils NEVER energized on boot):
 *   Boot -> Init -> [peripherals ok] Ready, then on the first motion command
 *   -> Running. Every fault -> Error (joint braked and held).
 *
 * Tasks:
 *   - "imu"     @ imu_sample_hz (200 Hz): MPU6050 read + Madgwick -> set_pitch
 *   - "balance" @ control_hz   (100 Hz): mailbox, PID/position, fail-safes,
 *                stepper.tick (STEP pulse timer runs in esp_timer context)
 *   - app_main  : 5 s monitor (heap, state, control liveness -> reboot)
 *
 * Threading: MQTT callbacks only queue into the controller's atomics; the
 * control task owns the stepper/PID/state machine; the IMU task only writes
 * pitch atomics. See balance_controller.hpp.
 */
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "balance_controller.hpp"
#include "command_handler.hpp"
#include "comms/mqtt_client.hpp"
#include "comms/wifi_station.hpp"
#include "drivers/a4988_driver.hpp"
#include "drivers/mpu6050_driver.hpp"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

using namespace openj5;

static const char* TAG = "node7";

// A Kconfig bool is #define'd only when 'y' (it is absent from sdkconfig.h
// when 'n'), so reading CONFIG_OPENJ5_* as a value would not compile for the
// default-'n' options: expose the three bools as real constants via #ifdef.
#ifdef CONFIG_OPENJ5_DIR_INVERTED
constexpr bool kDirInverted = true;
#else
constexpr bool kDirInverted = false;
#endif
#ifdef CONFIG_OPENJ5_ENABLED_ON_BOOT
constexpr bool kEnabledOnBoot = true;
#else
constexpr bool kEnabledOnBoot = false;
#endif
#ifdef CONFIG_OPENJ5_MQTT_TLS
constexpr bool kMqttTls = true;
#else
constexpr bool kMqttTls = false;
#endif

// ------------------------------------------------------------------ globals --
// Wired once in app_main (single-threaded phase), read-only afterwards:
// esp-mqtt callbacks are plain functions without a context parameter beyond
// the one passed to register_event, so the topics/handlers live here.
static MqttClient* g_mqtt = nullptr;
static BalanceController* g_controller = nullptr;
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
class MqttBalanceSink : public IBalanceSink {
public:
    explicit MqttBalanceSink(MqttClient& mqtt) : mqtt_(mqtt) {}

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
    Mpu6050* imu;
    BalanceController* ctrl;
    float imu_dt;
};

static void imu_task_fn(void* arg) {
    auto* args = static_cast<TaskArgs*>(arg);
    // 1000 Hz tick / sample rate -> e.g. 200 Hz = 5 ms; never 0.
    TickType_t period = pdMS_TO_TICKS(1000 / CONFIG_OPENJ5_IMU_SAMPLE_HZ);
    if (period == 0) {
        period = 1;
    }
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        const uint32_t t = now_ms();
        if (args->imu->update(args->imu_dt)) {
            args->ctrl->set_pitch(args->imu->pitch_deg(), t);
        }
        vTaskDelayUntil(&wake, period);
    }
}

static void control_task_fn(void* arg) {
    auto* args = static_cast<TaskArgs*>(arg);
    // 1000 Hz tick / control rate -> e.g. 100 Hz = 10 ms; never 0.
    TickType_t period = pdMS_TO_TICKS(1000 / CONFIG_OPENJ5_CONTROL_HZ);
    if (period == 0) {
        period = 1;
    }
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        args->ctrl->tick(now_ms());
        vTaskDelayUntil(&wake, period);
    }
}

// ------------------------------------------------------------------ app_main --
extern "C" void app_main(void) {
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "OpenJ5 Node 7 - Balance Controller");
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

    // ---- Configuration: Kconfig == config/node7_balance/node.json ----
    BalanceConfig balance_cfg;
    balance_cfg.target_pitch_deg = static_cast<float>(CONFIG_OPENJ5_TARGET_PITCH_DEG);
    balance_cfg.max_tilt_deg = static_cast<float>(CONFIG_OPENJ5_MAX_TILT_DEG);
    balance_cfg.deadband_deg = std::strtof(CONFIG_OPENJ5_DEADBAND_DEG, nullptr);
    balance_cfg.jsteps_per_deg =
        static_cast<float>(CONFIG_OPENJ5_STEPS_PER_REV * CONFIG_OPENJ5_MICROSTEPS *
                           CONFIG_OPENJ5_GEAR_RATIO) /
        360.0f;
    balance_cfg.control_dt = 1.0f / static_cast<float>(CONFIG_OPENJ5_CONTROL_HZ);
    balance_cfg.max_velocity = static_cast<double>(CONFIG_OPENJ5_MAX_VELOCITY);
    balance_cfg.max_accel = static_cast<double>(CONFIG_OPENJ5_MAX_ACCEL);
    balance_cfg.deadman_ms = CONFIG_OPENJ5_DEADMAN_TIMEOUT_MS;
    balance_cfg.watchdog_ms = CONFIG_OPENJ5_WATCHDOG_TIMEOUT_MS;
    balance_cfg.telemetry_period_ms = CONFIG_OPENJ5_TELEMETRY_PERIOD_MS;
    balance_cfg.pid.kp = std::strtof(CONFIG_OPENJ5_PID_KP, nullptr);
    balance_cfg.pid.ki = std::strtof(CONFIG_OPENJ5_PID_KI, nullptr);
    balance_cfg.pid.kd = std::strtof(CONFIG_OPENJ5_PID_KD, nullptr);
    // node.json carries symmetric clamps; Kconfig stores the magnitude only
    // (Kconfig has no negative int defaults) - same values.
    balance_cfg.pid.output_max = static_cast<float>(CONFIG_OPENJ5_PID_OUTPUT_MAX);
    balance_cfg.pid.output_min = -balance_cfg.pid.output_max;
    balance_cfg.pid.integral_max = static_cast<float>(CONFIG_OPENJ5_PID_INTEGRAL_LIMIT);
    balance_cfg.pid.integral_min = -balance_cfg.pid.integral_max;

    A4988Config stepper_cfg;
    stepper_cfg.step_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_STEP);
    stepper_cfg.dir_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_DIR);
    stepper_cfg.enable_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_PIN_ENABLE);
    stepper_cfg.dir_inverted = kDirInverted;
    stepper_cfg.max_velocity = static_cast<double>(CONFIG_OPENJ5_MAX_VELOCITY);
    stepper_cfg.max_accel = static_cast<double>(CONFIG_OPENJ5_MAX_ACCEL);
    stepper_cfg.max_position = CONFIG_OPENJ5_POS_LIMIT_STEPS;
    stepper_cfg.min_position = -CONFIG_OPENJ5_POS_LIMIT_STEPS;
    stepper_cfg.min_pulse_hz = static_cast<double>(CONFIG_OPENJ5_MIN_PULSE_HZ);

    ESP_LOGI(TAG,
             "jsteps/deg=%.3f | limits +/- %d jsteps (+/- %.1f deg) | "
             "pid kp=%.2f ki=%.2f kd=%.2f | deadband=%.2f deg",
             static_cast<double>(balance_cfg.jsteps_per_deg),
             CONFIG_OPENJ5_POS_LIMIT_STEPS,
             static_cast<double>(CONFIG_OPENJ5_POS_LIMIT_STEPS) /
                 static_cast<double>(balance_cfg.jsteps_per_deg),
             static_cast<double>(balance_cfg.pid.kp),
             static_cast<double>(balance_cfg.pid.ki),
             static_cast<double>(balance_cfg.pid.kd),
             static_cast<double>(balance_cfg.deadband_deg));

    // ---- Objects (constructed single-threaded, before tasks/MQTT start) ----
    MqttClient mqtt;
    MqttBalanceSink sink(mqtt);
    sink.init_topics(CONFIG_OPENJ5_TOPIC_PREFIX);

    A4988Driver stepper(stepper_cfg);
    stepper.initialize();  // coils released (enabled_on_boot = false)
    if (kEnabledOnBoot) {
        stepper.enable();
    }

    BalanceController ctrl(stepper, balance_cfg, sink);
    CommandHandler command_handler(ctrl, sink);
    g_mqtt = &mqtt;
    g_controller = &ctrl;
    g_command_handler = &command_handler;

    ctrl.notify(NodeEvent::InitStarted);  // Boot -> Init

    // ---- IMU (mounted on the body, ADR-017) ----
    Mpu6050 imu;
    Mpu6050::Config imu_cfg;
    imu_cfg.sda_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_I2C_SDA);
    imu_cfg.scl_pin = static_cast<gpio_num_t>(CONFIG_OPENJ5_I2C_SCL);
    imu_cfg.address = static_cast<uint8_t>(CONFIG_OPENJ5_IMU_ADDR);
    imu_cfg.sample_rate_hz = CONFIG_OPENJ5_IMU_SAMPLE_HZ;
    imu_cfg.madgwick_beta = std::strtof(CONFIG_OPENJ5_MADGWICK_BETA, nullptr);
    if (imu.init(imu_cfg) == ESP_OK) {
        ctrl.notify(NodeEvent::PeripheralsOk);  // Init -> Ready
    } else {
        ESP_LOGE(TAG,
                 "MPU6050 init failed: node boots in Error, 'level' stays "
                 "rejected until the IMU answers (deadman fail-safe)");
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
    std::snprintf(uri, sizeof(uri), "%s://%s:%d",
                  kMqttTls ? "mqtts" : "mqtt", CONFIG_OPENJ5_MQTT_HOST,
                  CONFIG_OPENJ5_MQTT_PORT);
    MqttClient::Config mqtt_cfg;
    mqtt_cfg.uri = uri;
    mqtt_cfg.client_id = CONFIG_OPENJ5_MQTT_CLIENT_ID;
    mqtt_cfg.keepalive_s = CONFIG_OPENJ5_MQTT_KEEPALIVE;
    mqtt.set_handlers(&on_mqtt_data, nullptr, &on_mqtt_connect);
    ESP_ERROR_CHECK(mqtt.start(mqtt_cfg));

    // ---- Tasks ----
    static TaskArgs s_args{&imu, &ctrl,
                           1.0f / static_cast<float>(CONFIG_OPENJ5_IMU_SAMPLE_HZ)};
    xTaskCreate(&imu_task_fn, "imu", 4096, &s_args, 6, nullptr);
    xTaskCreate(&control_task_fn, "balance", 6144, &s_args, 5, nullptr);

    // ---- Monitor (app_main loop): soft watchdog on the control task ----
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        const uint32_t last = ctrl.last_tick_ms();
        const uint32_t t = now_ms();
        if (last != 0 && (t - last) > balance_cfg.watchdog_ms * 5U) {
            ESP_LOGE(TAG, "control task stalled for %lu ms - rebooting",
                     static_cast<unsigned long>(t - last));
            esp_restart();
        }
        ESP_LOGI(TAG, "state=%s mode=%s pitch=%.2f deg pos=%lld jsteps heap=%lu",
                 to_string(ctrl.node_state()), to_string(ctrl.mode()),
                 static_cast<double>(ctrl.pitch()),
                 static_cast<long long>(stepper.get_position_steps()),
                 static_cast<unsigned long>(esp_get_free_heap_size()));
    }
}
