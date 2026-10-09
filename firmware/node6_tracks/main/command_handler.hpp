/**
 * OpenJ5 Node 6 - MQTT command parser (ADR-006 logical commands, ADR-015 wire
 * format). The robot SDK sends motion intent, the node interprets it locally.
 *
 * Wire format (JSON on openj5/v1/tracks/cmd):
 *   {"cmd": "forward",   "velocity": 0.3}   // velocity optional, default cfg
 *   {"cmd": "backward",  "velocity": 0.3}
 *   {"cmd": "spin_left", "velocity": 0.3}   // left wheel back, right forward
 *   {"cmd": "spin_right","velocity": 0.3}
 *   {"cmd": "stop"}
 *
 * `"command"` is accepted as an alias of `"cmd"` (same shape as Node 7).
 *
 * Runs in the MQTT event task: validation only reads the link atomic/default,
 * motion is queued to the control task (see track_controller.hpp threading
 * contract). Unknown/malformed payloads get an ok=false ack on the evt topic.
 */
#pragma once

#include "track_controller.hpp"

namespace openj5 {

class CommandHandler {
public:
    CommandHandler(TrackController& controller, ITrackSink& sink,
                   double default_velocity)
        : controller_(controller), sink_(sink), default_velocity_(default_velocity) {}

    /// One MQTT payload from the tracks cmd topic. Never throws, always acks.
    void handle(const char* json, int len);

private:
    void ack_unknown(const char* detail);

    TrackController& controller_;
    ITrackSink& sink_;
    double default_velocity_;
};

}  // namespace openj5
