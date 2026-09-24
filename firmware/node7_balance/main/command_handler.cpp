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

    const cJSON* cmd = cJSON_GetObjectItem(root, "command");
    const char* name = (cmd != nullptr && cJSON_IsString(cmd)) ? cmd->valuestring : nullptr;

    if (name == nullptr) {
        ack_unknown("missing 'command' field");
    } else if (std::strcmp(name, "level") == 0) {
        // Optional target; default = config target_pitch_deg (0 = gravity).
        const cJSON* arg = cJSON_GetObjectItem(root, "target_pitch_deg");
        if (arg != nullptr && cJSON_IsNumber(arg)) {
            controller_.cmd_level(static_cast<float>(arg->valuedouble));
        } else {
            controller_.cmd_level();
        }
    } else if (std::strcmp(name, "tilt") == 0) {
        const cJSON* angle = cJSON_GetObjectItem(root, "angle_deg");
        const cJSON* speed = cJSON_GetObjectItem(root, "speed");
        const float a = (angle != nullptr && cJSON_IsNumber(angle))
                            ? static_cast<float>(angle->valuedouble)
                            : 0.0f;
        const float s = (speed != nullptr && cJSON_IsNumber(speed))
                            ? static_cast<float>(speed->valuedouble)
                            : 0.5f;
        controller_.cmd_tilt(a, s);
    } else if (std::strcmp(name, "stow") == 0) {
        controller_.cmd_stow();
    } else if (std::strcmp(name, "stop") == 0) {
        controller_.cmd_stop("mqtt");
    } else {
        ack_unknown("unknown command (level|tilt|stow|stop)");
    }

    cJSON_Delete(root);
}

}  // namespace openj5
