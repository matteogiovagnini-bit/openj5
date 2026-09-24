/**
 * OpenJ5 per-node state machine (ADR-009): every node implements
 * BOOT -> INIT -> READY -> RUNNING <-> ERROR -> RECOVERY -> SHUTDOWN with the
 * same transition rules. Pure table-driven logic (host-testable); the node
 * applies side effects (brake, publish state topic...) on transitions.
 */
#pragma once

namespace openj5 {

enum class NodeState {
    Boot,
    Init,
    Ready,
    Running,
    Error,
    Recovery,
    Shutdown,
};

enum class NodeEvent {
    InitStarted,     ///< Boot -> Init
    PeripheralsOk,   ///< Init -> Ready
    InitFault,       ///< Init -> Error
    Start,           ///< Ready -> Running (leveling/motion enabled)
    Stop,            ///< Running -> Ready
    Fault,           ///< Running|Recovery|Ready -> Error
    Recovered,       ///< Error -> Recovery
    SelfCheckOk,     ///< Recovery -> Ready
    Shutdown,        ///< any -> Shutdown
};

struct TransitionResult {
    NodeState next;
    bool valid;  ///< false = event not allowed in `from` (state unchanged)
};

/// Apply `ev` to `from`; invalid events keep the current state.
TransitionResult transition(NodeState from, NodeEvent ev);

/// Stable lowercase name for logs and the MQTT state topic.
const char* to_string(NodeState state);

}  // namespace openj5
