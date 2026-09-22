"""Unit tests for core domain entities (T-003).

Identity/lifecycle semantics: Entity versioning, Robot aggregate root,
Node, Servo, Motor, Stepper (ADR-017), Plugin and Calibration.
"""
import pytest

from core.domain import (
    Angle, Calibration, CalibrationData, Entity, Motor, Node, NodeState,
    NodeType, Plugin, Robot, Servo, Stepper, StepperConfig,
)
from core.domain.value_objects import PluginMetadata


def test_entity_identity_and_touch():
    first, second = Entity(), Entity()
    assert first.id != second.id
    assert first.version == 0
    before = first.updated_at
    first.touch()
    assert first.version == 1
    assert first.updated_at >= before


# === Robot aggregate root ===

def test_robot_add_get_remove_node(robot, make_node):
    node = make_node(node_id="node2")
    robot.add_node(node)
    assert robot.get_node("node2") is node
    assert robot.get_node("node_missing") is None

    version_after_add = robot.version
    robot.remove_node("node2")
    assert robot.get_node("node2") is None
    assert robot.version == version_after_add + 1
    robot.remove_node("node2")  # idempotent


def test_robot_get_healthy_nodes(make_node):
    robot = Robot()
    robot.add_node(make_node(node_id="ok", state=NodeState.RUNNING))
    robot.add_node(make_node(node_id="broken", state=NodeState.ERROR))
    healthy = robot.get_healthy_nodes()
    assert [n.identity.node_id for n in healthy] == ["ok"]


def test_robot_get_errors_aggregates_robot_and_node_level(robot, make_node):
    robot.errors.append("emergency_stop active")
    robot.add_node(make_node(node_id="n2", errors=["servo fault", "warn only"]))
    errors = robot.get_errors()
    assert "emergency_stop active" in errors
    assert "servo fault" in errors
    assert "warn only" in errors


def test_robot_defaults(robot):
    assert robot.name == "OpenJ5"
    assert robot.state is None
    assert robot.battery is None
    assert robot.errors == []
    assert robot.plugins == {}


# === Node ===

def test_node_health_update_bumps_version(make_node):
    node = make_node(state=NodeState.READY)
    updated = make_node(state=NodeState.RUNNING)
    version = node.version
    node.update_health(updated.health)
    assert node.health.state is NodeState.RUNNING
    assert node.version == version + 1


def test_node_collects_actuators(make_node, servo_config, motor_config, stepper_config):
    node = make_node()
    servo = Servo(node_id=node.identity.node_id, config=servo_config)
    motor = Motor(node_id=node.identity.node_id, config=motor_config)
    stepper = Stepper(node_id=node.identity.node_id, config=stepper_config)

    node.add_servo(servo)
    node.add_motor(motor)
    node.add_stepper(stepper)

    assert node.servos["neck_yaw"] is servo
    assert node.motors["left_track"] is motor
    assert node.steppers["balance_joint"] is stepper
    assert node.config == {}
    assert node.version == 3


# === Servo ===

def test_servo_move_to_clamps_within_limits(servo_config):
    servo = Servo(node_id="node2", config=servo_config)
    servo.move_to(120.0)
    assert servo.target_position == 90.0
    assert servo.is_moving

    servo.move_to(-999.0)
    assert servo.target_position == -90.0


def test_servo_update_position_sets_moving_flag(servo_config):
    servo = Servo(node_id="node2", config=servo_config)
    servo.move_to(50.0)
    servo.update_position(20.0)
    assert servo.is_moving  # far from target
    servo.update_position(49.8)
    assert not servo.is_moving  # within 0.5 deg tolerance


def test_servo_defaults_to_zero(servo_config):
    servo = Servo(node_id="node2", config=servo_config)
    assert servo.current_position == 0.0
    assert not servo.is_moving
    assert servo.calibration is None


# === Motor ===

def test_motor_set_velocity_clamps_to_max_rpm(motor_config):
    motor = Motor(node_id="node6", config=motor_config)
    motor.set_velocity(500.0)
    assert motor.target_velocity == 300.0
    motor.set_velocity(-450.0)
    assert motor.target_velocity == -300.0
    motor.set_velocity(120.0)
    assert motor.target_velocity == 120.0


def test_motor_odometry_update(motor_config):
    motor = Motor(node_id="node6", config=motor_config)
    version = motor.version
    motor.update_odometry(1.5, -0.3, 0.7)
    assert (motor.odometry_x, motor.odometry_y, motor.odometry_theta) == (1.5, -0.3, 0.7)
    assert motor.version == version + 1


# === Stepper (ADR-017) ===

def test_stepper_relative_move_and_angle_readback(stepper_config):
    stepper = Stepper(node_id="node7", config=stepper_config)
    stepper.move_relative_deg(45.0)
    assert stepper.target_position_steps == 1600  # 12800 jsteps / 360 * 45
    assert stepper.is_moving

    stepper.update_position_steps(1600)
    assert not stepper.is_moving
    assert stepper.current_angle_deg == pytest.approx(45.0, abs=0.01)


def test_stepper_inverted_joint_flips_direction(stepper_config):
    cfg = StepperConfig(
        name="balance_joint", steps_per_rev=200, microsteps=16,
        gear_ratio=4.0, inverted=True,
    )
    stepper = Stepper(node_id="node7", config=cfg)
    stepper.move_relative_deg(30.0)
    assert stepper.target_position_steps < 0  # direction reversed on the wire

    stepper.update_position_steps(stepper.target_position_steps)
    # Readback still reports the requested joint angle (inversion compensated).
    assert stepper.current_angle_deg == pytest.approx(30.0, abs=0.01)


def test_stepper_absolute_move(stepper_config):
    stepper = Stepper(node_id="node7", config=stepper_config)
    stepper.move_to_steps(-800)
    assert stepper.target_position_steps == -800
    assert stepper.is_moving
    stepper.update_position_steps(-800)  # reached target
    assert not stepper.is_moving
    assert stepper.current_position_steps == -800


def test_stepper_defaults_disabled(stepper_config):
    stepper = Stepper(node_id="node7", config=stepper_config)
    assert not stepper.enabled
    assert stepper.current_position_steps == 0


# === Plugin ===

def test_plugin_lifecycle_transitions():
    plugin = Plugin(metadata=PluginMetadata(plugin_id="vision", name="Vision"))
    assert plugin.state == "loaded"
    assert plugin.instance is None

    plugin.start()
    assert plugin.state == "starting"
    plugin.mark_running()
    assert plugin.state == "running"
    plugin.stop()
    assert plugin.state == "stopping"
    plugin.mark_stopped()
    assert plugin.state == "stopped"

    plugin.mark_error("segfault")
    assert plugin.state == "error"
    assert plugin.version == 5  # one touch per transition


# === Calibration ===

def test_calibration_verify():
    cal = Calibration(
        node_id="node2", component="servo:head:neck_yaw",
        data=CalibrationData(home_position=90.0),
    )
    assert not cal.verified and cal.verified_at is None
    cal.verify()
    assert cal.verified
    assert cal.verified_at is not None
    assert cal.data.home_position == 90.0


def test_robot_and_node_share_entity_contract():
    assert issubclass(Robot, Entity)
    assert issubclass(Node, Entity)
    assert NodeType.BALANCE.value == "balance"
    assert Angle(0.0).value == 0.0
