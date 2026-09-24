/**
 * OpenJ5 Madgwick AHRS (6DOF: gyro + accelerometer, no magnetometer).
 *
 * Port of the canonical open-source Madgwick gradient-descent filter used for
 * the Node 7 body IMU (ADR-017, config "fusion": "madgwick"). Pure math: no
 * ESP-IDF dependencies, compiled and tested on the host
 * (firmware/common/test/host_test.cpp).
 *
 * Conventions: quaternions q = [w, x, y, z], gyro in rad/s, accelerometer in
 * any unit (normalized internally), ZYX Euler angles. Stationary level = q
 * identity = pitch 0, accel reading +1g on Z.
 */
#pragma once

namespace openj5 {

class Madgwick {
public:
    /// beta: filter gain (Madgwick's standard default 0.1; Kconfig-tunable).
    explicit Madgwick(float beta = 0.1f) : beta_(beta) { reset(); }

    void reset();

    /// One fusion step. dt in seconds, gyro rad/s, accel raw units.
    void update(float dt, float gx, float gy, float gz, float ax, float ay, float az);

    /// Pitch (rotation about Y) in degrees, ZYX convention: + = nose up.
    float pitch_deg() const;
    float roll_deg() const;

    float q0() const { return q0_; }
    float q1() const { return q1_; }
    float q2() const { return q2_; }
    float q3() const { return q3_; }

private:
    float beta_;
    float q0_ = 1.0f, q1_ = 0.0f, q2_ = 0.0f, q3_ = 0.0f;
};

}  // namespace openj5
