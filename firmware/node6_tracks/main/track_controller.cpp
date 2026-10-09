#include "track_controller.hpp"

#include <cstdio>

namespace openj5 {

const char* to_string(TrackMode mode) {
    switch (mode) {
        case TrackMode::Disabled:
            return "disabled";
        case TrackMode::Forward:
            return "forward";
        case TrackMode::Backward:
            return "backward";
        case TrackMode::SpinLeft:
            return "spin_left";
        case TrackMode::SpinRight:
            return "spin_right";
    }
    return "unknown";
}

TrackController::TrackController(L298NDriver& driver, const TrackConfig& cfg,
                                 ITrackSink& sink)
    : driver_(driver), cfg_(cfg), sink_(sink) {}

double TrackController::clamp_command(double velocity) const {
    if (velocity < cfg_.min_velocity) {
        return cfg_.min_velocity;
    }
    if (velocity > cfg_.max_velocity) {
        return cfg_.max_velocity;
    }
    return velocity;
}

void TrackController::ack(const char* command, bool ok, const char* detail) {
    char buf[192];
    std::snprintf(buf, sizeof(buf), R"({"command":"%s","ok":%s,"detail":"%s"})",
                  command, ok ? "true" : "false", detail);
    sink_.publish_event(buf);
}

void TrackController::queue(int kind, double velocity, const char* command) {
    if (!link_ok_.load()) {
        ack(command, false, "mqtt link down");
        return;
    }
    pending_velocity_.store(clamp_command(velocity));
    pending_.store(kind);  // latest wins
    ack(command, true, "accepted");
}

// ---------------------------------------------------------------- commands --

void TrackController::cmd_forward(double velocity) {
    queue(kForward, velocity, "forward");
}

void TrackController::cmd_backward(double velocity) {
    queue(kBackward, velocity, "backward");
}

void TrackController::cmd_spin_left(double velocity) {
    queue(kSpinLeft, velocity, "spin_left");
}

void TrackController::cmd_spin_right(double velocity) {
    queue(kSpinRight, velocity, "spin_right");
}

void TrackController::cmd_stop(const char* reason) {
    // Priority path: applied first by the next tick regardless of the mailbox.
    stop_pending_.store(1);
    ack("stop", true, reason != nullptr ? reason : "stop");
}

// ------------------------------------------------------------------- link --

void TrackController::set_link_ok(bool ok) { link_ok_.store(ok); }

// ------------------------------------------------------------ control tick --

void TrackController::notify(NodeEvent ev) { transition(ev); }

void TrackController::transition(NodeEvent ev) {
    // Qualified call: the member name would otherwise hide the free function.
    const TransitionResult r = openj5::transition(state_, ev);
    if (r.valid) {
        state_ = r.next;
        publish_state();
    }
}

void TrackController::publish_state() {
    char buf[64];
    std::snprintf(buf, sizeof(buf), R"({"state":"%s"})", to_string(state_));
    sink_.publish_state(buf);
}

void TrackController::enter_mode(TrackMode mode, double velocity) {
    mode_.store(static_cast<int>(mode));
    velocity_.store(velocity);
}

void TrackController::clear_fault_and_advance() {
    faulted_ = false;
    fault_reason_ = "none";
    if (state_ == NodeState::Error) {
        transition(NodeEvent::Recovered);    // Error   -> Recovery
        transition(NodeEvent::SelfCheckOk);  // Recovery -> Ready
    }
}

void TrackController::start_motion() {
    if (state_ == NodeState::Ready) {
        transition(NodeEvent::Start);  // Ready -> Running
    }
}

void TrackController::fault(const char* reason, uint32_t now_ms) {
    if (faulted_) {
        return;
    }
    faulted_ = true;
    fault_reason_ = reason;
    enter_mode(TrackMode::Disabled, 0.0);
    driver_.brake_all();           // short-brake: hold the tracks
    transition(NodeEvent::Fault);  // ignored when already in Error
    char buf[192];
    std::snprintf(buf, sizeof(buf), R"({"event":"fault","reason":"%s","t":%lu})",
                  reason, static_cast<unsigned long>(now_ms));
    sink_.publish_event(buf);
}

void TrackController::apply_pending(uint32_t now_ms) {
    if (stop_pending_.exchange(0) != 0) {
        enter_mode(TrackMode::Disabled, 0.0);
        driver_.brake_all();  // stop motion and hold
        last_command_ms_ = now_ms;
        if (state_ == NodeState::Running) {
            transition(NodeEvent::Stop);  // Running -> Ready
        }
    }

    const int kind = pending_.exchange(kNone);
    if (kind == kNone) {
        return;
    }
    const double velocity = pending_velocity_.load();

    // Any accepted motion command is an explicit operator intent: it clears a
    // latched fault (the link check happened at cmd_*).
    clear_fault_and_advance();

    switch (kind) {
        case kForward:
            enter_mode(TrackMode::Forward, velocity);
            break;
        case kBackward:
            enter_mode(TrackMode::Backward, velocity);
            break;
        case kSpinLeft:
            enter_mode(TrackMode::SpinLeft, velocity);
            break;
        case kSpinRight:
            enter_mode(TrackMode::SpinRight, velocity);
            break;
        default:
            return;
    }
    last_command_ms_ = now_ms;
    start_motion();
}

void TrackController::tick(uint32_t now_ms) {
    if (first_tick_) {
        first_tick_ = false;
        last_tick_ms_ = now_ms;
        last_telemetry_ms_ = now_ms;
    } else {
        const uint32_t gap_ms = now_ms - last_tick_ms_;
        last_tick_ms_ = now_ms;
        if (gap_ms > cfg_.watchdog_ms) {
            fault("control loop stalled", now_ms);
        }
    }

    apply_pending(now_ms);

    // Fail-safe #1: the link dropped while driving.
    if (!link_ok_.load() && mode() != TrackMode::Disabled) {
        fault("mqtt link lost", now_ms);
    }

    // Fail-safe #2: command deadman - commands stopped arriving.
    if (mode() != TrackMode::Disabled &&
        (now_ms - last_command_ms_) > cfg_.watchdog_ms) {
        fault("command watchdog expired", now_ms);
    }

    if (!faulted_) {
        const double v = velocity_.load();
        switch (mode()) {
            case TrackMode::Forward:
                driver_.set_velocity("left", v);
                driver_.set_velocity("right", v);
                break;
            case TrackMode::Backward:
                driver_.set_velocity("left", -v);
                driver_.set_velocity("right", -v);
                break;
            case TrackMode::SpinLeft:
                driver_.set_velocity("left", -v);
                driver_.set_velocity("right", v);
                break;
            case TrackMode::SpinRight:
                driver_.set_velocity("left", v);
                driver_.set_velocity("right", -v);
                break;
            case TrackMode::Disabled:
            default:
                break;
        }
    }

    driver_.tick(static_cast<double>(cfg_.control_dt_ms) / 1000.0);

    if (now_ms - last_telemetry_ms_ >= cfg_.telemetry_period_ms) {
        last_telemetry_ms_ = now_ms;
        publish_telemetry(now_ms);
    }
}

void TrackController::publish_telemetry(uint32_t now_ms) {
    char buf[320];
    std::snprintf(buf, sizeof(buf),
                  R"({"t":%lu,"state":"%s","mode":"%s","left":%.2f,"right":%.2f,)"
                  R"("velocity":%.2f,"faulted":%s,"fault_reason":"%s","link":%s})",
                  static_cast<unsigned long>(now_ms), to_string(state_), to_string(mode()),
                  driver_.get_velocity("left"), driver_.get_velocity("right"),
                  velocity_.load(), faulted_ ? "true" : "false", fault_reason_,
                  link_ok_.load() ? "true" : "false");
    sink_.publish_telemetry(buf);
}

}  // namespace openj5
