/**
 * OpenJ5 Node 7 - MQTT command parser (ADR-015 wire format, ADR-006 logical
 * commands only: the robot SDK never sends joint angles as control inputs,
 * the node interprets them locally).
 *
 * Wire format (JSON on openj5/v1/balance/cmd):
 *   {"command": "level",  "target_pitch_deg": 0.0}     // optional arg
 *   {"command": "tilt",   "angle_deg": 5.0, "speed": 0.5}
 *   {"command": "stow"}
 *   {"command": "stop"}
 *
 * Runs in the MQTT event task: validation only reads atomics/config, motion
 * is queued to the control task (see balance_controller.hpp threading
 * contract). Unknown/malformed payloads get an ok=false ack on the evt topic.
 */
#pragma once

#include "balance_controller.hpp"

namespace openj5 {

class CommandHandler {
public:
    CommandHandler(BalanceController& controller, IBalanceSink& sink)
        : controller_(controller), sink_(sink) {}

    /// One MQTT payload from the balance cmd topic. Never throws, always acks.
    void handle(const char* json, int len);

private:
    void ack_unknown(const char* detail);

    BalanceController& controller_;
    IBalanceSink& sink_;
};

}  // namespace openj5
