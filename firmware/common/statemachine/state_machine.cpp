#include "statemachine/state_machine.hpp"

namespace openj5 {

TransitionResult transition(NodeState from, NodeEvent ev) {
    const auto keep = from;

    if (ev == NodeEvent::Shutdown) {
        // Shutdown is accepted from every state except already Shutdown.
        return {NodeState::Shutdown, from != NodeState::Shutdown};
    }

    switch (from) {
        case NodeState::Boot:
            if (ev == NodeEvent::InitStarted) {
                return {NodeState::Init, true};
            }
            break;
        case NodeState::Init:
            if (ev == NodeEvent::PeripheralsOk) {
                return {NodeState::Ready, true};
            }
            if (ev == NodeEvent::InitFault) {
                return {NodeState::Error, true};
            }
            break;
        case NodeState::Ready:
            if (ev == NodeEvent::Start) {
                return {NodeState::Running, true};
            }
            if (ev == NodeEvent::Fault) {
                return {NodeState::Error, true};
            }
            break;
        case NodeState::Running:
            if (ev == NodeEvent::Stop) {
                return {NodeState::Ready, true};
            }
            if (ev == NodeEvent::Fault) {
                return {NodeState::Error, true};
            }
            break;
        case NodeState::Error:
            if (ev == NodeEvent::Recovered) {
                return {NodeState::Recovery, true};
            }
            break;
        case NodeState::Recovery:
            if (ev == NodeEvent::SelfCheckOk) {
                return {NodeState::Ready, true};
            }
            if (ev == NodeEvent::Fault) {
                return {NodeState::Error, true};
            }
            break;
        case NodeState::Shutdown:
            break;
    }
    return {keep, false};
}

const char* to_string(NodeState state) {
    switch (state) {
        case NodeState::Boot:
            return "boot";
        case NodeState::Init:
            return "init";
        case NodeState::Ready:
            return "ready";
        case NodeState::Running:
            return "running";
        case NodeState::Error:
            return "error";
        case NodeState::Recovery:
            return "recovery";
        case NodeState::Shutdown:
            return "shutdown";
    }
    return "unknown";
}

}  // namespace openj5
