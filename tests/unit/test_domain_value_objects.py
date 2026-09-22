"""Unit tests for core domain value objects (T-003).

Immutable primitives: Angle, Position3D, Quaternion, Pose3D, Twist,
JointAngles, configuration VOs and telemetry readings.
"""
import math
from dataclasses import FrozenInstanceError

import pytest

from core.domain import (
    Angle, AngleUnit, BalanceConfig, BatteryHealth, BatteryState,
    CalibrationData, DistanceReading, IMUReading, JointAngles, NodeHealth,
    NodeIdentity, NodeState, NodeType, Odometry, PIDConfig,
    Position3D, Pose3D, Quaternion, RobotState, StepperConfig,
    TemperatureReading, Twist,
)


# === Angle ===

def test_angle_clamps_degrees():
    assert Angle(270.0).value == 180.0
    assert Angle(-400.0).value == -180.0
    assert Angle(45.0).value == 45.0


def test_angle_clamps_radians():
    assert Angle.from_radians(4.0).value == pytest.approx(math.pi)
    assert Angle.from_radians(-4.0).value == pytest.approx(-math.pi)


def test_angle_unit_conversion():
    a = Angle.from_degrees(180.0)
    assert a.to_radians() == pytest.approx(math.pi)
    assert Angle.from_radians(math.pi).to_degrees() == pytest.approx(180.0)


def test_angle_arithmetic_returns_degrees():
    result = Angle.from_radians(math.pi / 2) + Angle(45.0)
    assert result.unit == AngleUnit.DEGREES
    assert result.value == pytest.approx(135.0)
    assert (Angle(90.0) - Angle(30.0)).value == pytest.approx(60.0)
    assert (Angle(30.0) * 2.0).value == pytest.approx(60.0)
    assert abs(Angle(-90.0)).value == pytest.approx(90.0)


def test_angle_sum_is_clamped():
    assert (Angle(100.0) + Angle(100.0)).value == 180.0


def test_angle_rejects_non_angle_operand():
    with pytest.raises(TypeError):
        Angle(10.0) + 5.0  # type: ignore[operator]
    with pytest.raises(TypeError):
        Angle(10.0) - 5.0  # type: ignore[operator]


def test_angle_zero_factory():
    zero = Angle.zero()
    assert zero.value == 0.0 and zero.unit == AngleUnit.DEGREES


def test_angle_is_immutable():
    a = Angle(10.0)
    with pytest.raises(FrozenInstanceError):
        a.value = 5.0  # type: ignore[misc]


# === Position3D ===

def test_position_distance_and_arithmetic():
    p = Position3D(1.0, 2.0, 3.0)
    q = Position3D(4.0, 6.0, 3.0)
    assert p.distance_to(q) == pytest.approx(5.0)
    assert (p + q) == Position3D(5.0, 8.0, 6.0)
    assert (q - p) == Position3D(3.0, 4.0, 0.0)
    assert (p * 2.0) == Position3D(2.0, 4.0, 6.0)


def test_position_rejects_mismatched_frame():
    p = Position3D(0.0, 0.0, 0.0, frame="base")
    other = Position3D(0.0, 0.0, 0.0, frame="map")
    with pytest.raises(TypeError):
        p + other  # type: ignore[operator]
    with pytest.raises(TypeError):
        p - other  # type: ignore[operator]


def test_position_zero_factory_keeps_frame():
    assert Position3D.zero("odom") == Position3D(0.0, 0.0, 0.0, "odom")


# === Quaternion ===

def test_quaternion_identity_and_normalization():
    ident = Quaternion.identity()
    assert (ident.w, ident.x, ident.y, ident.z) == (1.0, 0.0, 0.0, 0.0)
    q = Quaternion(w=2.0, x=0.0, y=0.0, z=0.0)  # non-unit input is normalized
    assert q.w == pytest.approx(1.0)


def test_quaternion_euler_roundtrip():
    for roll, pitch, yaw in [(0.0, 0.0, math.pi / 2), (0.3, -0.2, 1.0),
                             (-1.0, 0.5, -2.0)]:
        q = Quaternion.from_euler(roll, pitch, yaw)
        r, p, y = q.to_euler()
        assert r == pytest.approx(roll, abs=1e-9)
        assert p == pytest.approx(pitch, abs=1e-9)
        assert y == pytest.approx(yaw, abs=1e-9)


def test_quaternion_identity_euler_is_zero():
    assert Quaternion.identity().to_euler() == (0.0, 0.0, 0.0)


# === Pose3D / Twist ===

def test_pose_and_twist_zero_factories():
    pose = Pose3D.zero("map")
    assert pose.position.frame == "map"
    assert pose.orientation == Quaternion.identity()
    twist = Twist.zero()
    assert twist.linear == Position3D.zero()
    assert twist.angular == Position3D.zero()


# === JointAngles ===

def test_joint_angles_access():
    joints = JointAngles({"neck_yaw": Angle(10.0), "neck_pitch": Angle(-5.0)})
    assert joints.get("neck_yaw") == Angle(10.0)
    assert joints.get("missing") is None
    assert joints["neck_pitch"] == Angle(-5.0)
    assert "neck_yaw" in joints and "missing" not in joints
    with pytest.raises(KeyError):
        joints["missing"]


# === Configuration VOs ===

def test_servo_config_fields(servo_config):
    assert servo_config.name == "neck_yaw"
    assert servo_config.min_angle.to_degrees() == -90.0
    assert servo_config.max_angle.to_degrees() == 90.0
    assert servo_config.home_pulse == 300


def test_motor_and_pid_config(motor_config):
    assert motor_config.motor_id == "left_track"
    assert motor_config.pid.kp == 1.0
    assert motor_config.pid.output_min == -1.0


def test_pid_config_is_immutable():
    pid = PIDConfig(1.0, 0.0, 0.0, -1.0, 1.0, -1.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        pid.kp = 2.0  # type: ignore[misc]


def test_stepper_config_steps_math(stepper_config):
    assert stepper_config.steps_per_joint_rev == 200 * 16 * 4
    assert stepper_config.steps_per_deg == pytest.approx(12800 / 360.0)
    assert stepper_config.deg_to_steps(45.0) == 1600
    assert stepper_config.steps_to_deg(6400) == pytest.approx(180.0)
    assert not stepper_config.inverted


def test_stepper_config_defaults():
    cfg = StepperConfig(name="joint")
    assert cfg.steps_per_rev == 200
    assert cfg.microsteps == 16
    assert cfg.gear_ratio == 1.0


def test_stepper_config_steps_per_joint_rev_never_zero():
    cfg = StepperConfig(name="joint", steps_per_rev=0, microsteps=0)
    assert cfg.steps_per_joint_rev == 1


def test_balance_config_defaults_and_custom_pid():
    defaults = BalanceConfig()
    assert defaults.target_pitch_deg == 0.0
    assert defaults.max_tilt_deg == 35.0
    assert defaults.deadband_deg == 0.5
    assert defaults.control_hz == 100
    assert defaults.reference == "gravity"
    assert not defaults.enabled_on_boot
    assert defaults.pid.output_max == 1600.0

    pid = PIDConfig(15.0, 1.0, 0.3, -1600.0, 1600.0, -4000.0, 4000.0)
    custom = BalanceConfig(target_pitch_deg=2.5, pid=pid)
    assert custom.target_pitch_deg == 2.5
    assert custom.pid.kp == 15.0


def test_calibration_data_defaults():
    cal = CalibrationData()
    assert (cal.raw_min, cal.raw_max) == (0, 4095)
    assert cal.scale == 1.0
    assert not cal.verified
    assert cal.extra == {}


def test_plugin_metadata_defaults():
    # Domain projection only: the rich descriptor lives in plugins/base (T-015),
    # so it is intentionally NOT re-exported by core.domain.
    from core.domain.value_objects import PluginMetadata

    meta = PluginMetadata(plugin_id="face", name="Face Detection")
    assert meta.version == "0.0.0"
    assert meta.plugin_type == "generic"


# === Telemetry readings ===

def test_battery_state_and_health_enum():
    battery = BatteryState(
        voltage_v=11.8, current_a=-0.5, percentage=85.0,
        temperature_c=32.0, health=BatteryHealth.GOOD,
        time_remaining_min=90.0,
    )
    assert battery.percentage == 85.0
    assert battery.time_remaining_min == 90.0
    assert {h.value for h in BatteryHealth} == {"good", "degraded", "critical", "fault"}


def test_sensor_readings():
    temp = TemperatureReading(sensor_id="bms", celsius=41.5, timestamp=1.0)
    dist = DistanceReading(sensor_id="tof_left", distance_m=0.42, confidence=0.9, timestamp=2.0)
    imu = IMUReading(
        sensor_id="mpu6050_body", orientation=Quaternion.identity(),
        angular_velocity=Position3D.zero(), linear_acceleration=Position3D.zero(),
        timestamp=3.0,
    )
    odo = Odometry(
        pose=Pose3D.zero("odom"), twist=Twist.zero(),
        covariance=[0.0] * 36, timestamp=4.0,
    )
    assert temp.celsius == 41.5
    assert dist.confidence == 0.9
    assert imu.orientation == Quaternion.identity()
    assert len(odo.covariance) == 36


# === Node / robot state VOs ===

def test_node_identity_and_enums():
    identity = NodeIdentity(
        node_id="node7", name="balance", node_type=NodeType.BALANCE,
        hardware="esp32-s3", firmware_version="0.2.0", hardware_version="1.0",
    )
    assert identity.node_type is NodeType.BALANCE
    assert len(NodeType) == 7  # robot_core + 5 limbs/tracks + balance (ADR-017)
    assert {s.value for s in NodeState} == {
        "boot", "init", "ready", "running", "error", "recovery", "shutdown",
    }


def test_node_health_and_robot_state():
    health = NodeHealth(
        node_id="node1", state=NodeState.RUNNING, cpu_percent=5.0,
        memory_percent=30.0, temperature_c=45.0, uptime_sec=100.0,
        last_heartbeat=1.0, errors=[], warnings=["fan noisy"],
    )
    assert health.state is NodeState.RUNNING
    state = RobotState(
        node_health={"node1": health},
        battery=BatteryState(11.8, -0.5, 85.0, 32.0, BatteryHealth.GOOD),
        pose=None, timestamp=1.0,
    )
    assert "node1" in state.node_health
    assert state.pose is None
