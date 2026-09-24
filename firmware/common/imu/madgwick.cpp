#include "imu/madgwick.hpp"

#include <cmath>

namespace openj5 {

namespace {
constexpr float kRadToDeg = 57.29577951308232f;
}

void Madgwick::reset() {
    q0_ = 1.0f;
    q1_ = q2_ = q3_ = 0.0f;
}

void Madgwick::update(float dt, float gx, float gy, float gz, float ax, float ay,
                      float az) {
    // Accelerometer-only fallback: integrate gyro, skip the gradient step when
    // free-falling (accel magnitude ~0) to avoid dividing by ~0.
    const float norm = std::sqrt(ax * ax + ay * ay + az * az);
    const bool use_accel = norm > 1e-6f;

    float q0 = q0_, q1 = q1_, q2 = q2_, q3 = q3_;

    float s0 = 0.0f, s1 = 0.0f, s2 = 0.0f, s3 = 0.0f;
    if (use_accel) {
        ax /= norm;
        ay /= norm;
        az /= norm;

        // Auxiliary variables
        const float _2q0 = 2.0f * q0;
        const float _2q1 = 2.0f * q1;
        const float _2q2 = 2.0f * q2;
        const float _2q3 = 2.0f * q3;
        const float _4q0 = 4.0f * q0;
        const float _4q1 = 4.0f * q1;
        const float _4q2 = 4.0f * q2;
        const float _8q1 = 8.0f * q1;
        const float _8q2 = 8.0f * q2;
        const float q0q0 = q0 * q0;
        const float q1q1 = q1 * q1;
        const float q2q2 = q2 * q2;
        const float q3q3 = q3 * q3;

        // Gradient descent step toward the gravity direction (IMU only)
        s0 = _4q0 * q2q2 + _2q2 * ax + _4q0 * q1q1 - _2q1 * ay;
        s1 = _4q1 * q3q3 - _2q3 * ax + 4.0f * q0q0 * q1 - _2q0 * ay - _4q1 +
             _8q1 * q1q1 + _8q1 * q2q2 + _4q1 * az;
        s2 = 4.0f * q0q0 * q2 + _2q0 * ax + _4q2 * q3q3 - _2q3 * ay - _4q2 +
             _8q2 * q1q1 + _8q2 * q2q2 + _4q2 * az;
        s3 = 4.0f * q1q1 * q3 - _2q1 * ax + 4.0f * q2q2 * q3 - _2q2 * ay;

        float snorm = std::sqrt(s0 * s0 + s1 * s1 + s2 * s2 + s3 * s3);
        if (snorm > 1e-9f) {
            s0 /= snorm;
            s1 /= snorm;
            s2 /= snorm;
            s3 /= snorm;
        }
    }

    // Quaternion rate from gyro + gradient correction
    const float qDot0 = 0.5f * (-q1 * gx - q2 * gy - q3 * gz) - beta_ * s0;
    const float qDot1 = 0.5f * (q0 * gx + q2 * gz - q3 * gy) - beta_ * s1;
    const float qDot2 = 0.5f * (q0 * gy - q1 * gz + q3 * gx) - beta_ * s2;
    const float qDot3 = 0.5f * (q0 * gz + q1 * gy - q2 * gx) - beta_ * s3;

    q0_ = q0 + qDot0 * dt;
    q1_ = q1 + qDot1 * dt;
    q2_ = q2 + qDot2 * dt;
    q3_ = q3 + qDot3 * dt;

    const float qn = std::sqrt(q0_ * q0_ + q1_ * q1_ + q2_ * q2_ + q3_ * q3_);
    if (qn > 1e-9f) {
        q0_ /= qn;
        q1_ /= qn;
        q2_ /= qn;
        q3_ /= qn;
    } else {
        reset();
    }
}

float Madgwick::pitch_deg() const {
    // ZYX: pitch = asin(2 (w*y - x*z))
    float s = 2.0f * (q0_ * q2_ - q1_ * q3_);
    s = s > 1.0f ? 1.0f : (s < -1.0f ? -1.0f : s);
    return std::asin(s) * kRadToDeg;
}

float Madgwick::roll_deg() const {
    // ZYX: roll = atan2(2 (w*x + y*z), 1 - 2 (x^2 + y^2))
    return std::atan2(2.0f * (q0_ * q1_ + q2_ * q3_),
                      1.0f - 2.0f * (q1_ * q1_ + q2_ * q2_)) *
           kRadToDeg;
}

}  // namespace openj5
