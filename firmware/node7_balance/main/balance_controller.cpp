#include "balance_controller.hpp"

#include <cmath>
#include <cstdio>

#include <esp_timer.h>

namespace openj5 {

namespace {
/// Headroom between the commanded travel and the fault threshold: position
/// snap is <= 2 jsteps (0.06 deg), so 0.5 deg detects a real mechanical
/// overrun without tripping on normal convergence.
constexpr float kLimitMarginDeg = 0.5f;
}  // namespace

const char* to_string(BalanceMode mode) {
    switch (mode) {
        case BalanceMode::Disabled:
            return "disabled";
        case BalanceMode::Leveling:
            return "leveling";
        case BalanceMode::Position:
            return "position";
    }
    return "unknown";
}

BalanceController::BalanceController(A4988Driver& stepper, const BalanceConfig& cfg,
                                     IBalanceSink& sink)
    : stepper_(stepper), cfg_(cfg), sink_(sink), pid_(cfg.pid) {}

bool BalanceController::pitch_fresh(uint32_t now_ms) const {
    const uint32_t age = now_ms - pitch_ms_.load();  // wrap-safe unsigned
    return pitch_ms_.load() != 0 && age <= cfg_.deadman_ms;
}

void BalanceController::ack(const char* command, bool ok, const char* detail) {
    char buf[192];
    std::snprintf(buf, sizeof(buf), R"({"command":"%s","ok":%s,"detail":"%s"})",
                  command, ok ? "true" : "false", detail);
    sink_.publish_event(buf);
}

// ---------------------------------------------------------------- commands --

void BalanceController::cmd_level() { cmd_level(cfg_.target_pitch_deg); }

void BalanceController::cmd_level(float target_pitch_deg) {
    if (target_pitch_deg > cfg_.max_tilt_deg || target_pitch_deg < -cfg_.max_tilt_deg) {
        ack("level", false, "target_pitch_deg outside +/-max_tilt_deg");
        return;
    }
    // Leveling needs a trustworthy pitch: reject when the deadman already lost
    // it (a faulting tick may still be a few ms away).
    const uint32_t now = static_cast<uint32_t>(esp_timer_get_time() / 1000);
    if (!pitch_fresh(now)) {
        ack("level", false, "imu pitch stale (deadman)");
        return;
    }
    pending_a_.store(target_pitch_deg);
    pending_.store(kLevel);  // latest wins
    ack("level", true, "accepted");
}

void BalanceController::cmd_tilt(float angle_deg, float speed) {
    float angle = angle_deg;
    const char* detail = "accepted";
    if (angle > cfg_.max_tilt_deg) {
        angle = cfg_.max_tilt_deg;
        detail = "angle_deg clamped to +max_tilt_deg";
    } else if (angle < -cfg_.max_tilt_deg) {
        angle = -cfg_.max_tilt_deg;
        detail = "angle_deg clamped to -max_tilt_deg";
    }
    float sp = speed;
    if (sp < 0.05f) {
        sp = 0.05f;
        detail = "speed clamped to [0.05, 1.0]";
    } else if (sp > 1.0f) {
        sp = 1.0f;
        detail = "speed clamped to [0.05, 1.0]";
    }
    pending_a_.store(angle);
    pending_b_.store(sp);
    pending_.store(kTilt);
    ack("tilt", true, detail);
}

void BalanceController::cmd_stow() {
    pending_.store(kStow);
    ack("stow", true, "accepted");
}

void BalanceController::cmd_stop(const char* reason) {
    // Priority path: applied first by the next tick regardless of the mailbox.
    stop_pending_.store(1);
    ack("stop", true, reason != nullptr ? reason : "stop");
}

// -------------------------------------------------------------------- IMU ---

void BalanceController::set_pitch(float pitch_deg, uint32_t now_ms) {
    pitch_.store(pitch_deg);
    pitch_ms_.store(now_ms);
}

// ------------------------------------------------------------ control tick --

void BalanceController::notify(NodeEvent ev) { transition(ev); }

void BalanceController::transition(NodeEvent ev) {
    // Qualified call: the member name would otherwise hide the free function.
    const TransitionResult r = openj5::transition(state_, ev);
    if (r.valid) {
        state_ = r.next;
        publish_state();
    }
}

void BalanceController::publish_state() {
    char buf[64];
    std::snprintf(buf, sizeof(buf), R"({"state":"%s"})", to_string(state_));
    sink_.publish_state(buf);
}

void BalanceController::enter_mode(BalanceMode m) {
    mode_.store(static_cast<int>(m));
    if (m == BalanceMode::Leveling) {
        pid_.reset();
    }
}

void BalanceController::clear_fault_and_advance() {
    faulted_ = false;
    fault_reason_ = "none";
    if (state_ == NodeState::Error) {
        transition(NodeEvent::Recovered);   // Error   -> Recovery
        transition(NodeEvent::SelfCheckOk); // Recovery -> Ready
    }
}

void BalanceController::start_motion() {
    if (state_ == NodeState::Ready) {
        transition(NodeEvent::Start);  // Ready -> Running
    }
}

void BalanceController::fault(const char* reason, uint32_t now_ms) {
    if (faulted_) {
        return;
    }
    faulted_ = true;
    fault_reason_ = reason;
    enter_mode(BalanceMode::Disabled);
    stepper_.brake();  // hold the joint, stop commanding motion
    transition(NodeEvent::Fault);  // ignored when already in Error
    char buf[192];
    std::snprintf(buf, sizeof(buf), R"({"event":"fault","reason":"%s","t":%lu})",
                  reason, static_cast<unsigned long>(now_ms));
    sink_.publish_event(buf);
}

void BalanceController::apply_pending() {
    if (stop_pending_.exchange(0) != 0) {
        enter_mode(BalanceMode::Disabled);
        stepper_.brake();  // stop motion, energize coils (hold position)
        pid_.reset();
        if (state_ == NodeState::Running) {
            transition(NodeEvent::Stop);  // Running -> Ready
        }
        last_error_deg_ = 0.0f;
    }

    const int kind = pending_.exchange(kNone);
    if (kind == kNone) {
        return;
    }
    const float a = pending_a_.load();
    const float b = pending_b_.load();

    // Any accepted motion command is an explicit operator intent: it clears a
    // latched fault (the validation that needed the IMU happened at cmd_*).
    clear_fault_and_advance();

    switch (kind) {
        case kLevel:
            level_target_deg_ = a;
            enter_mode(BalanceMode::Leveling);
            start_motion();
            break;
        case kTilt: {
            position_target_steps_ =
                static_cast<int64_t>(std::lround(a * cfg_.jsteps_per_deg));
            stepper_.set_max_velocity(cfg_.max_velocity * static_cast<double>(b));
            enter_mode(BalanceMode::Position);
            start_motion();
            break;
        }
        case kStow:
            position_target_steps_ = 0;
            stepper_.set_max_velocity(cfg_.max_velocity);
            enter_mode(BalanceMode::Position);
            start_motion();
            break;
        default:
            break;
    }
}

void BalanceController::tick(uint32_t now_ms) {
    uint32_t gap_ms = 0;
    if (first_tick_) {
        first_tick_ = false;
        last_tick_ms_ = now_ms;
        last_telemetry_ms_ = now_ms;
    } else {
        gap_ms = now_ms - last_tick_ms_;
        last_tick_ms_ = now_ms;
        if (gap_ms > cfg_.watchdog_ms) {
            fault("control loop stalled", now_ms);
        }
    }

    apply_pending();

    // ADR-017 fail-safe #1: stale pitch (IMU dead / task dead) -> brake.
    const uint32_t pitch_age = now_ms - pitch_ms_.load();
    if (pitch_ms_.load() == 0 || pitch_age > cfg_.deadman_ms) {
        fault("imu pitch stale (deadman)", now_ms);
    }

    const auto current = mode();
    const float pitch = pitch_.load();

    switch (current) {
        case BalanceMode::Leveling: {
            const float error = level_target_deg_ - pitch;
            last_error_deg_ = error;
            // Sim parity: PID always integrates; command zeroed in deadband.
            float command = pid_.update(error, cfg_.control_dt, true);
            if (std::fabs(error) < cfg_.deadband_deg) {
                command = 0.0f;
            }
            if (!faulted_) {
                stepper_.set_velocity_steps_s(static_cast<double>(command));
            }
            break;
        }
        case BalanceMode::Position: {
            last_error_deg_ = 0.0f;
            if (!faulted_) {
                // Idempotent each tick: re-issuing the same target also heals
                // a rejected out-of-limit call without extra state.
                (void)stepper_.set_position_steps(position_target_steps_);
            }
            break;
        }
        case BalanceMode::Disabled:
        default:
            break;
    }

    if (!faulted_) {
        stepper_.tick(cfg_.control_dt);  // fixed-rate cadence = control task period

        // ADR-017 fail-safe #2: joint beyond mechanical travel -> brake.
        const float joint_deg =
            static_cast<float>(stepper_.get_position_steps()) / cfg_.jsteps_per_deg;
        if (joint_deg > cfg_.max_tilt_deg + kLimitMarginDeg ||
            joint_deg < -(cfg_.max_tilt_deg + kLimitMarginDeg)) {
            fault("joint beyond mechanical travel limit", now_ms);
        }
    }

    if (now_ms - last_telemetry_ms_ >= cfg_.telemetry_period_ms) {
        last_telemetry_ms_ = now_ms;
        publish_telemetry(now_ms);
    }
}

void BalanceController::publish_telemetry(uint32_t now_ms) {
    const float body = pitch_.load();
    const float joint =
        static_cast<float>(stepper_.get_position_steps()) / cfg_.jsteps_per_deg;
    // Kinematics of the sim: body_pitch = track_pitch + joint_angle.
    const float track = body - joint;
    char buf[320];
    std::snprintf(buf, sizeof(buf),
                  R"({"t":%lu,"state":"%s","mode":"%s","body_pitch_deg":%.2f,)"
                  R"("track_pitch_deg":%.2f,"joint_deg":%.2f,"error_deg":%.2f,)"
                  R"("velocity_steps_s":%.0f,"enabled":%s,"faulted":%s,)"
                  R"("fault_reason":"%s"})",
                  static_cast<unsigned long>(now_ms), to_string(state_),
                  to_string(mode()), static_cast<double>(body),
                  static_cast<double>(track), static_cast<double>(joint),
                  static_cast<double>(last_error_deg_),
                  stepper_.get_velocity_steps_s(), stepper_.enabled() ? "true" : "false",
                  faulted_ ? "true" : "false", fault_reason_);
    sink_.publish_telemetry(buf);
}

}  // namespace openj5
