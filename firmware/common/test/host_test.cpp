/**
 * Host unit tests for the pure firmware logic (no ESP-IDF required):
 *   - openj5::motion: slew / brake bound / position profile / pulse timing
 *   - Madgwick filter: static convergence + tilt extraction
 *   - ADR-009 state machine: legal/illegal transitions
 *   - Node 7 balance PID: parity with src/hardware/sim/leveling.py semantics
 *
 * Run with scripts/test/host_firmware.sh (also a GitHub Actions job).
 * Minimal assert-based runner on purpose: no test framework in firmware yet.
 */
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "hal/stepper_logic.hpp"
#include "imu/madgwick.hpp"
#include "statemachine/state_machine.hpp"
#include "../../node7_balance/main/balance_pid.hpp"

namespace {
int g_checks = 0;

void check(bool ok, const char* what) {
    ++g_checks;
    if (!ok) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        std::exit(1);
    }
}

bool near(double a, double b, double tol) { return std::fabs(a - b) <= tol; }
}

static void test_motion() {
    using namespace openj5::motion;

    // Slew: ramps up at exactly accel*dt per tick from rest.
    double v = 0.0;
    for (int i = 0; i < 10; ++i) {
        v = slew(v, 1600.0, 800.0, 0.01);
    }
    check(near(v, 80.0, 1e-9), "slew ramps 800*0.01*10 = 80 steps/s in 10 ticks");
    check(slew(1600.0, -1600.0, 800.0, 0.01) == 1592.0, "slew decel limited");
    check(near(slew(10.0, 15.0, 800.0, 0.01), 15.0, 1e-9),
          "slew passes small gaps");

    // Brake bound: sqrt(2*a*d).
    check(near(brake_bound(1244.0, 800.0), std::sqrt(2.0 * 800.0 * 1244.0), 1e-6),
          "brake bound = sqrt(2ad)");
    check(brake_bound(0.0, 800.0) == 0.0, "brake bound at target = 0");

    // Position profile: full sweep 0 -> 1244 must start AT REST (v <= a*dt on
    // the first tick) - the defect the Python reference has (1410 step/s).
    const double vmax = 1600.0, accel = 800.0, dt = 0.01;
    double pos = 0.0, vel = 0.0;
    const int64_t target = 1244;
    int ticks = 0;
    while (pos != static_cast<double>(target) && ticks < 100000) {
        const double remaining = static_cast<double>(target) - pos;
        const double v_tgt = position_velocity_target(remaining, vmax, accel);
        vel = slew(vel, v_tgt, accel, dt);
        if (ticks == 0) {
            check(vel <= accel * dt + 1e-9, "first tick ramps, does not jump");
        }
        pos += vel * dt;
        if (remaining > 0 && pos > static_cast<double>(target)) {
            pos = static_cast<double>(target);  // integer step snap (<=2 steps)
        }
        ++ticks;
    }
    check(pos == static_cast<double>(target), "position move reaches target");
    check(ticks < 100000, "position move terminates");
    // Symmetric-ish trapezoid: cannot be faster than pure accel+decel bound.
    const double min_ticks = std::sqrt(2.0 * 1244.0 / accel) / dt;  // triangular
    check(ticks >= min_ticks * 0.9, "move respects acceleration (no teleport)");

    // Pulse timing: 1600 steps/s -> toggle every 312 us (rising edges 625 us).
    check(toggle_interval_us(1600.0, 5.0) == 313, "toggle period at 1600 steps/s");
    check(toggle_interval_us(0.0, 5.0) == 0, "stopped axis issues no pulses");
    check(toggle_interval_us(4.0, 5.0) == 0, "below min freq = hold");
    check(toggle_interval_us(5.0, 5.0) > 0, "at min freq pulses resume");
    check(clamp(5.0, 0.0, 1.0) == 1.0 && clamp(-5.0, 0.0, 1.0) == 0.0, "clamp");
}

static void test_madgwick() {
    openj5::Madgwick filter(0.1f);
    const float dt = 0.005f;  // 200 Hz

    // 1) Static tilt: accelerometer specific force at rest reads
    //    a = R^T * (0,0,+g), so nose-up +theta gives ax = -g*sin(theta).
    //    Converge to +20 deg (accel is the truth source for static tilt).
    const float theta = 20.0f * 3.14159265358979f / 180.0f;
    const float ax = -std::sin(theta), ay = 0.0f, az = std::cos(theta);
    for (int i = 0; i < 4000; ++i) {  // 20 s
        filter.update(dt, 0.0f, 0.0f, 0.0f, ax, ay, az);
    }
    check(near(filter.pitch_deg(), 20.0, 1.0), "converges to static +20 deg pitch");

    // 1b) Mirror case: nose-down converges to -20 deg.
    openj5::Madgwick mirror(0.1f);
    for (int i = 0; i < 4000; ++i) {
        mirror.update(dt, 0.0f, 0.0f, 0.0f, std::sin(theta), 0.0f, std::cos(theta));
    }
    check(near(mirror.pitch_deg(), -20.0, 1.0), "converges to static -20 deg pitch");

    // 2) Level: accel +1g on Z -> pitch 0.
    openj5::Madgwick level(0.1f);
    for (int i = 0; i < 4000; ++i) {
        level.update(dt, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f);
    }
    check(near(level.pitch_deg(), 0.0, 0.5), "converges to level");

    // 3) Gyro integration: constant +10 deg/s pitch rate for 1 s from level
    //    (accel kept at level would fight it - use zero accel: free-fall style
    //    gyro-only path) -> about +10 deg.
    openj5::Madgwick gyro_only(0.0f);  // beta 0: pure gyro integration
    const float w = 10.0f * 3.14159265358979f / 180.0f;
    for (int i = 0; i < 200; ++i) {
        gyro_only.update(dt, 0.0f, w, 0.0f, 0.0f, 0.0f, 0.0f);
    }
    check(near(gyro_only.pitch_deg(), 10.0, 0.5), "gyro integration pitch +10 deg");

    // 4) Degenerate input (no accel signal) must not produce NaN.
    openj5::Madgwick fragile(0.1f);
    for (int i = 0; i < 100; ++i) {
        fragile.update(dt, 0.1f, 0.1f, 0.1f, 0.0f, 0.0f, 0.0f);
    }
    check(!std::isnan(fragile.pitch_deg()), "zero accel does not NaN");
}

static void test_state_machine() {
    using openj5::NodeEvent;
    using openj5::NodeState;
    using openj5::transition;

    auto r = transition(NodeState::Boot, NodeEvent::InitStarted);
    check(r.valid && r.next == NodeState::Init, "boot -> init");
    r = transition(r.next, NodeEvent::PeripheralsOk);
    check(r.valid && r.next == NodeState::Ready, "init -> ready");
    r = transition(r.next, NodeEvent::Start);
    check(r.valid && r.next == NodeState::Running, "ready -> running");
    r = transition(r.next, NodeEvent::Stop);
    check(r.valid && r.next == NodeState::Ready, "running -> ready");
    r = transition(NodeState::Ready, NodeEvent::Start);
    r = transition(r.next, NodeEvent::Fault);
    check(r.valid && r.next == NodeState::Error, "fault -> error");
    r = transition(r.next, NodeEvent::Recovered);
    check(r.valid && r.next == NodeState::Recovery, "error -> recovery");
    r = transition(r.next, NodeEvent::SelfCheckOk);
    check(r.valid && r.next == NodeState::Ready, "recovery -> ready");

    // Illegal: start from boot, stop from ready, start from error.
    r = transition(NodeState::Boot, NodeEvent::Start);
    check(!r.valid && r.next == NodeState::Boot, "start from boot rejected");
    r = transition(NodeState::Ready, NodeEvent::Stop);
    check(!r.valid && r.next == NodeState::Ready, "stop from ready rejected");
    r = transition(NodeState::Error, NodeEvent::Start);
    check(!r.valid && r.next == NodeState::Error, "start from error rejected");

    // Shutdown from anywhere.
    r = transition(NodeState::Running, NodeEvent::Shutdown);
    check(r.valid && r.next == NodeState::Shutdown, "shutdown from running");
    check(std::strcmp(openj5::to_string(NodeState::Running), "running") == 0,
          "state name");
}

static void test_balance_pid() {
    // Params mirroring config/node7_balance/node.json.
    BalancePidParams p{};
    BalancePid pid(p);

    // Divergenza INTENZIONALE dalla sim: il firmware non fa il primo
    // derivativo (la sim parte da last_error=0 e produce un kick all'enable;
    // allineamento in T-029). Prima iterazione: kp*e + ki*e*dt.
    float out = pid.update(2.0f, 0.01f, true);
    check(near(out, 15.0f * 2.0f + 1.0f * 2.0f * 0.01f, 1e-3),
          "first tick: kp*error + ki*e*dt, no D kick");

    // Deadband behaviour is the caller's, but output clamp is ours.
    BalancePid clamped(p);
    out = clamped.update(1000.0f, 0.01f, true);  // huge error
    check(out == p.output_max, "output clamped to motor limit");

    // Integral windup bound: run long with persistent error.
    BalancePid windup(p);
    for (int i = 0; i < 100000; ++i) {
        (void)windup.update(5.0f, 0.01f, true);
    }
    check(windup.integral() <= p.integral_max + 5.0f * 0.01f + 1e-3,
          "integral bounded");

    // Disabled -> zero output (sim parity: leveling_enabled false).
    BalancePid off(p);
    check(off.update(50.0f, 0.01f, false) == 0.0f, "disabled outputs 0");

    // Anti-windup direction: integral stays put when disabled? Sim keeps state
    // but zeroes command - reset() must clear it.
    off.reset();
    check(off.integral() == 0.0f, "reset clears integral");
}

int main() {
    test_motion();
    test_madgwick();
    test_state_machine();
    test_balance_pid();
    std::printf("host_firmware: %d checks OK\n", g_checks);
    return 0;
}
