#include "command_handler.hpp"

#include <cstdio>
#include <cstring>

#include "cJSON.h"

namespace openj5 {

void CommandHandler::ack_unknown(const char* detail) {
    char buf[160];
    std::snprintf(buf, sizeof(buf), R"({"command":"?","ok":false,"detail":"%s"})",
                  detail);
    sink_.publish_event(buf);
}

void CommandHandler::handle(const char* json, int len) {
    if (json == nullptr || len <= 0) {
        ack_unknown("empty payload");
        return;
    }
    cJSON* root = cJSON_ParseWithLength(json, static_cast<size_t>(len));
    if (root == nullptr) {
        ack_unknown("invalid JSON");
        return;
    }

    // "cmd" is the Node 6 wire field; "command" stays accepted for symmetry
    // with the other nodes (same parser shape).
    const cJSON* cmd = cJSON_GetObjectItem(root, "cmd");
    if (cmd == nullptr) {
        cmd = cJSON_GetObjectItem(root, "command");
    }
    const char* name = (cmd != nullptr && cJSON_IsString(cmd)) ? cmd->valuestring : nullptr;

    if (name == nullptr) {
        ack_unknown("missing 'cmd' field");
    } else if (std::strcmp(name, "stop") == 0) {
        controller_.cmd_stop("mqtt");
    } else {
        const cJSON* arg = cJSON_GetObjectItem(root, "velocity");
        const double velocity = (arg != nullptr && cJSON_IsNumber(arg))
                                    ? arg->valuedouble
                                    : default_velocity_;
        if (std::strcmp(name, "forward") == 0) {
            controller_.cmd_forward(velocity);
        } else if (std::strcmp(name, "backward") == 0) {
            controller_.cmd_backward(velocity);
        } else if (std::strcmp(name, "spin_left") == 0) {
            controller_.cmd_spin_left(velocity);
        } else if (std::strcmp(name, "spin_right") == 0) {
            controller_.cmd_spin_right(velocity);
        } else {
            ack_unknown("unknown command (forward|backward|spin_left|spin_right|stop)");
        }
    }

    cJSON_Delete(root);
}

}  // namespace openj5
