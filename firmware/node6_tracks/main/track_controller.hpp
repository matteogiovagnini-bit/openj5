/**
 * OpenJ5 Node 6 - Tracks controller (ADR-002 / ADR-019): turns logical MQTT
 * commands into differential-drive motor velocities on the L298N driver, with
 * the fail-safes required for a motor node.
 *
 * Threading contract (race-free without locks, mirrors Node 7):
 *   - cmd_*()      : MQTT context  -> atomics only (single-slot mailbox, latest
 *                    command wins; stop has a dedicated priority flag).
 *   - set_link_ok(): app_main/control-task glue -> atomic.
 *   - tick()       : control task  -> SOLE OWNER of the driver, the mode and the
 *                    ADR-009 state machine; publishes via sink.
 *
 * Fail-safes:
 *   - command deadman (watchdog_ms): no fresh command while driving -> brake;
 *   - MQTT link lost               : brake immediately;
 *   - control loop stall           : brake (and app_main reboots on 5x);
 *   - disabled on boot             : motors released until the first command.
 *
 * Velocity is normalized [-1, +1] == src/hardware/hal/motor.py; limits/ramp
 * arrive via Kconfig == config/node6_tracks/node.json (ADR-008).
 */
#pragma once

#include <atomic>
#include <cstdint>

#include "drivers/l298n_driver.hpp"
#include "statemachine/state_machine.hpp"

namespace openj5 {

enum class TrackMode : int {
    Disabled = 0,
    Forward = 1,
    Backward = 2,
    SpinLeft = 3,
    SpinRight = 4,
};

const char* to_string(TrackMode mode);

struct TrackConfig {
    double default_velocity = 0.3;
    double min_velocity = -1.0;
    double max_velocity = 1.0;
    uint32_t watchdog_ms = 1000;         ///< command freshness (deadman)
    uint32_t telemetry_period_ms = 1000;
    uint32_t control_dt_ms = 20;         ///< ramp cadence = 1/control_hz
};

/// Publication sink, implemented in app_main over MQTT: keeps this class free
/// of networking (unit-testable, single responsibility).
class ITrackSink {
public:
    virtual ~ITrackSink() = default;
    virtual void publish_state(const char* state_json) = 0;
    virtual void publish_event(const char* json) = 0;
    virtual void publish_telemetry(const char* json) = 0;
};

class TrackController {
public:
    TrackController(L298NDriver& driver, const TrackConfig& cfg, ITrackSink& sink);

    // --- MQTT context: validate + queue, ack through the sink ---
    void cmd_forward(double velocity);
    void cmd_backward(double velocity);
    void cmd_spin_left(double velocity);
    void cmd_spin_right(double velocity);
    void cmd_stop(const char* reason);

    // --- link liveness (control-task glue) ---
    void set_link_ok(bool ok);
    bool link_ok() const { return link_ok_.load(); }

    // --- control task ---
    void tick(uint32_t now_ms);

    // --- lifecycle (app_main, before the control task starts) ---
    void notify(NodeEvent ev);

    NodeState node_state() const { return state_; }
    TrackMode mode() const { return static_cast<TrackMode>(mode_.load()); }
    bool faulted() const { return faulted_; }
    const char* fault_reason() const { return fault_reason_; }
    uint32_t last_tick_ms() const { return last_tick_ms_; }
    double command_velocity() const { return velocity_.load(); }

private:
    // Mailbox types (single slot, latest wins). Stop uses its own flag.
    static constexpr int kNone = 0;
    static constexpr int kForward = 1;
    static constexpr int kBackward = 2;
    static constexpr int kSpinLeft = 3;
    static constexpr int kSpinRight = 4;

    double clamp_command(double velocity) const;
    void queue(int kind, double velocity, const char* command);
    void apply_pending(uint32_t now_ms);
    void enter_mode(TrackMode mode, double velocity);
    void clear_fault_and_advance();  ///< Error -> Recovery -> Ready (ADR-009)
    void start_motion();             ///< Ready -> Running
    void fault(const char* reason, uint32_t now_ms);
    void transition(NodeEvent ev);
    void publish_state();
    void publish_telemetry(uint32_t now_ms);
    void ack(const char* command, bool ok, const char* detail);

    L298NDriver& driver_;
    TrackConfig cfg_;
    ITrackSink& sink_;

    // control-task owned
    NodeState state_ = NodeState::Boot;
    bool faulted_ = false;
    const char* fault_reason_ = "none";  ///< static string literals only
    uint32_t last_tick_ms_ = 0;
    uint32_t last_command_ms_ = 0;
    uint32_t last_telemetry_ms_ = 0;
    bool first_tick_ = true;

    // MQTT -> control mailbox
    std::atomic<int> pending_{kNone};
    std::atomic<double> pending_velocity_{0.0};
    std::atomic<int> stop_pending_{0};
    std::atomic<double> velocity_{0.0};

    // link -> control (written by app_main glue, read by tick)
    std::atomic<bool> link_ok_{false};

    // telemetry mirror (written in tick, read only for logging)
    std::atomic<int> mode_{static_cast<int>(TrackMode::Disabled)};
};

}  // namespace openj5
