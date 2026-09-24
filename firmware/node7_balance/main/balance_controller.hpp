/**
 * OpenJ5 Node 7 - Balance controller (ADR-017): turns logical commands and
 * the fused body pitch into stepper motion, with the fail-safes required by
 * the ADR (deadman on IMU freshness, joint travel limit, watchdog on loop
 * stall, disabled on boot).
 *
 * Threading contract (SOLID, race-free without locks):
 *   - cmd_*()      : MQTT context  -> atomics only (single-slot mailbox,
 *                    latest command wins; stop has a dedicated priority flag).
 *   - set_pitch()  : IMU task      -> atomics only.
 *   - tick()       : control task  -> SOLE OWNER of the stepper, the PID, the
 *                    mode and the ADR-009 state machine; publishes via sink.
 *
 * Semantics are 1:1 with src/hardware/sim/leveling.py (kp/ki/kd, deadband,
 * integral clamp order); gains arrive via Kconfig == config/node7_balance/node.json
 * (enforced by tests/unit/test_node7_config_sync.py).
 */
#pragma once

#include <atomic>
#include <cstdint>

#include "balance_pid.hpp"
#include "drivers/a4988_driver.hpp"
#include "statemachine/state_machine.hpp"

namespace openj5 {

enum class BalanceMode : int { Disabled = 0, Leveling = 1, Position = 2 };

const char* to_string(BalanceMode mode);

struct BalanceConfig {
    float target_pitch_deg = 0.0f;   ///< default level target (0 = gravity)
    float max_tilt_deg = 35.0f;      ///< mechanical joint travel
    float deadband_deg = 0.5f;       ///< no command inside deadband
    float jsteps_per_deg = 35.5556f; ///< steps*microsteps*gear / 360 (derived)
    float control_dt = 0.01f;        ///< 1 / control_hz (fixed-rate cadence)
    double max_velocity = 1600.0;
    double max_accel = 800.0;
    uint32_t deadman_ms = 250;           ///< pitch staleness -> brake + fault
    uint32_t watchdog_ms = 1000;         ///< loop stall -> brake + fault
    uint32_t telemetry_period_ms = 1000;
    BalancePidParams pid{};
};

/// Publication sink, implemented in app_main over MQTT: keeps this class free
/// of networking (unit-testable, single responsibility).
class IBalanceSink {
public:
    virtual ~IBalanceSink() = default;
    virtual void publish_state(const char* state_json) = 0;
    virtual void publish_event(const char* json) = 0;
    virtual void publish_telemetry(const char* json) = 0;
};

class BalanceController {
public:
    BalanceController(A4988Driver& stepper, const BalanceConfig& cfg, IBalanceSink& sink);

    // --- MQTT context: validate + queue, ack through the sink ---
    void cmd_level();  ///< default target from config (target_pitch_deg)
    void cmd_level(float target_pitch_deg);
    void cmd_tilt(float angle_deg, float speed);
    void cmd_stow();
    void cmd_stop(const char* reason);

    // --- IMU task ---
    void set_pitch(float pitch_deg, uint32_t now_ms);

    // --- control task ---
    void tick(uint32_t now_ms);

    // --- lifecycle (app_main, before the control task starts) ---
    void notify(NodeEvent ev);

    NodeState node_state() const { return state_; }
    BalanceMode mode() const { return static_cast<BalanceMode>(mode_.load()); }
    bool faulted() const { return faulted_; }
    const char* fault_reason() const { return fault_reason_; }
    uint32_t last_tick_ms() const { return last_tick_ms_; }
    float last_error_deg() const { return last_error_deg_; }
    float pitch() const { return pitch_.load(); }
    bool pitch_fresh(uint32_t now_ms) const;

private:
    // Mailbox types (single slot, latest wins). Stop uses its own flag.
    static constexpr int kNone = 0;
    static constexpr int kLevel = 1;
    static constexpr int kTilt = 2;
    static constexpr int kStow = 3;

    void apply_pending();
    void enter_mode(BalanceMode m);
    void clear_fault_and_advance();  ///< Error -> Recovery -> Ready (ADR-009)
    void start_motion();             ///< Ready -> Running
    void fault(const char* reason, uint32_t now_ms);
    void transition(NodeEvent ev);
    void publish_state();
    void publish_telemetry(uint32_t now_ms);
    void ack(const char* command, bool ok, const char* detail);

    A4988Driver& stepper_;
    BalanceConfig cfg_;
    IBalanceSink& sink_;
    BalancePid pid_;

    // control-task owned (written before tasks start / only from tick)
    NodeState state_ = NodeState::Boot;
    bool faulted_ = false;
    const char* fault_reason_ = "none";  ///< static string literals only
    float level_target_deg_ = 0.0f;
    int64_t position_target_steps_ = 0;
    float last_error_deg_ = 0.0f;
    uint32_t last_tick_ms_ = 0;
    uint32_t last_telemetry_ms_ = 0;
    bool first_tick_ = true;

    // MQTT -> control mailbox
    std::atomic<int> pending_{kNone};
    std::atomic<float> pending_a_{0.0f};
    std::atomic<float> pending_b_{0.0f};
    std::atomic<int> stop_pending_{0};

    // IMU -> control
    std::atomic<float> pitch_{0.0f};
    std::atomic<uint32_t> pitch_ms_{0};

    // telemetry mirror (written in tick, read only for logging)
    std::atomic<int> mode_{static_cast<int>(BalanceMode::Disabled)};
};

}  // namespace openj5
