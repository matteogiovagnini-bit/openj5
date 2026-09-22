"""Unit tests for core domain services (T-003).

KinematicsService (DH forward/numerical IK), SafetyPolicyService (command
validation + emergency conditions + fallbacks), MotionPlannerService
(trapezoidal joint/cartesian trajectories).
"""
import math

import pytest

from core.domain import (
    Angle, IKinematicsService, IMotionPlanner, ISafetyPolicy, JointAngles,
    KinematicsService, MotionPlannerService, NodeState, NodeType,
    Position3D, Robot, SafetyPolicyService,
)

# Planar 2R arm: two 0.3 m links, rotation about Z, no offsets.
PLANAR_2R = [
    {"joint": "j1", "d": 0.0, "a": 0.3, "alpha": 0.0, "theta_offset": 0.0},
    {"joint": "j2", "d": 0.0, "a": 0.3, "alpha": 0.0, "theta_offset": 0.0},
]


def _joints(j1_deg: float, j2_deg: float = 0.0) -> JointAngles:
    return JointAngles({
        "j1": Angle.from_degrees(j1_deg),
        "j2": Angle.from_degrees(j2_deg),
    })


# === Interfaces are contracts ===

def test_services_are_abstract_contracts():
    for cls in (IKinematicsService, IMotionPlanner, ISafetyPolicy):
        with pytest.raises(TypeError):
            cls()  # type: ignore[abstract]


# === Kinematics ===

def test_forward_kinematics_stretched_arm():
    pose = KinematicsService().forward_kinematics(_joints(0.0, 0.0), PLANAR_2R)
    assert pose.position.x == pytest.approx(0.6, abs=1e-9)
    assert pose.position.y == pytest.approx(0.0, abs=1e-9)
    assert pose.position.z == pytest.approx(0.0, abs=1e-9)
    assert pose.position.frame == "base"


def test_forward_kinematics_matches_analytic_2r():
    pose = KinematicsService().forward_kinematics(_joints(0.0, 90.0), PLANAR_2R)
    assert pose.position.x == pytest.approx(0.3, abs=1e-9)
    assert pose.position.y == pytest.approx(0.3, abs=1e-9)


def test_forward_kinematics_theta_offset():
    dh = [{"joint": "j1", "d": 0.0, "a": 0.3, "alpha": 0.0, "theta_offset": 90.0}]
    joints = JointAngles({"j1": Angle.from_degrees(0.0)})
    pose = KinematicsService().forward_kinematics(joints, dh)
    # theta = 0 + offset 90 -> link points along +Y
    assert pose.position.x == pytest.approx(0.0, abs=1e-9)
    assert pose.position.y == pytest.approx(0.3, abs=1e-9)


def test_inverse_kinematics_reaches_target():
    svc = KinematicsService()
    target = Position3D(0.4, 0.3, 0.0)
    solution = svc.inverse_kinematics(target, ["j1", "j2"], PLANAR_2R)

    assert set(solution.angles) == {"j1", "j2"}
    reached = svc.forward_kinematics(solution, PLANAR_2R).position
    error = math.sqrt(
        (reached.x - target.x) ** 2 + (reached.y - target.y) ** 2
        + (reached.z - target.z) ** 2
    )
    assert error < 2e-3  # IK_TOLERANCE_M = 1 mm, small slack for iteration end


# DH chain whose links have zero length: the end-effector position is always
# the origin, so the Jacobian columns are all zero (fully singular posture).
DEGENERATE_DH = [
    {"joint": "j1", "d": 0.0, "a": 0.0, "alpha": 0.0, "theta_offset": 0.0},
    {"joint": "j2", "d": 0.0, "a": 0.0, "alpha": 0.0, "theta_offset": 0.0},
]


def test_inverse_kinematics_bails_out_when_normal_matrix_is_singular():
    # J = 0 and damping disabled -> A = J^T J + 0*I is the zero matrix,
    # _mat_inv returns None and the solver must stop instead of crashing.
    svc = KinematicsService()
    svc.IK_DAMPING = 0.0  # instance attribute shadows the class default
    solution = svc.inverse_kinematics(
        Position3D(0.1, 0.2, 0.0), ["j1", "j2"], DEGENERATE_DH,
    )
    assert solution["j1"].to_degrees() == pytest.approx(0.0, abs=1e-9)


def test_inverse_kinematics_line_search_halves_step_then_gives_up():
    # Damping keeps A invertible, so dq is computed but is all zeros (J = 0):
    # no trial step can reduce the error, the line search halves alpha down to
    # IK_MIN_STEP_ALPHA, then the solver returns the best solution found.
    svc = KinematicsService()
    solution = svc.inverse_kinematics(
        Position3D(0.1, 0.2, 0.0), ["j1", "j2"], DEGENERATE_DH,
    )
    assert solution["j1"].to_degrees() == pytest.approx(0.0, abs=1e-9)
    assert solution["j2"].to_degrees() == pytest.approx(0.0, abs=1e-9)


def test_inverse_kinematics_uses_initial_guess_when_given():
    svc = KinematicsService()
    initial = _joints(10.0, 10.0)
    solution = svc.inverse_kinematics(
        Position3D(0.3, 0.3, 0.0), ["j1", "j2"], PLANAR_2R, initial=initial,
    )
    reached = svc.forward_kinematics(solution, PLANAR_2R).position
    assert math.dist((reached.x, reached.y, reached.z), (0.3, 0.3, 0.0)) < 2e-3


def test_matrix_inverse_and_multiplication():
    svc = KinematicsService()
    inverse = svc._mat_inv([[2.0, 0.0], [0.0, 4.0]])
    assert inverse == [[0.5, 0.0], [0.0, 0.25]]
    assert svc._mat_inv([[1.0, 2.0], [2.0, 4.0]]) is None  # singular

    identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    product = svc._mat_mul(identity, identity)
    assert product == identity


def test_dh_transform_rotation():
    t = KinematicsService()._dh_transform(90.0, d=0.1, a=0.0, alpha_deg=0.0)
    assert t[0][3] == pytest.approx(0.0, abs=1e-9)   # a*cos(90)
    assert t[1][3] == pytest.approx(0.0, abs=1e-9)
    assert t[0][1] == pytest.approx(-1.0, abs=1e-9)  # -sin(90)
    assert t[1][0] == pytest.approx(1.0, abs=1e-9)
    assert t[2][3] == pytest.approx(0.1)             # d


# === Safety policy: command validation ===

@pytest.fixture
def policy():
    return SafetyPolicyService()


def test_validate_rejects_when_robot_not_operable(policy, robot):
    robot.state = NodeState.ERROR
    allowed, reason = policy.validate_command("MoveHeadCommand", {}, robot)
    assert not allowed
    assert "operable" in reason


def test_validate_allows_when_state_unset_or_running(policy, robot):
    robot.state = None
    assert policy.validate_command("WhateverCommand", {}, robot)[0]
    robot.state = NodeState.RUNNING
    assert policy.validate_command("WhateverCommand", {}, robot)[0]


def test_validate_blocks_during_emergency_stop(policy, robot):
    robot.errors.append("emergency_stop active")
    allowed, reason = policy.validate_command("MoveTracksCommand", {}, robot)
    assert not allowed
    assert reason == "Emergency stop active"


def test_validate_head_move_workspace(policy, robot):
    ok_target = Position3D(0.8, 0.1, 1.2)
    assert policy.validate_command(
        "MoveHeadCommand", {"target": ok_target, "speed": 0.5}, robot,
    )[0]

    cases = [
        ({"speed": 0.5}, "Missing target"),
        ({"target": ok_target, "speed": 1.5}, "Invalid speed"),
        ({"target": Position3D(0.1, 0.0, 1.0)}, "outside workspace"),
        ({"target": Position3D(1.6, 0.0, 1.0)}, "outside workspace"),
        ({"target": Position3D(0.8, 0.9, 1.0)}, "outside workspace"),
        ({"target": Position3D(0.8, 0.0, 0.2)}, "outside workspace"),
        ({"target": Position3D(0.8, 0.0, 1.9)}, "outside workspace"),
    ]
    for params, expected in cases:
        allowed, reason = policy.validate_command("MoveHeadCommand", params, robot)
        assert not allowed, params
        assert expected in reason, reason


def test_validate_arm_move_workspace(policy, robot):
    ok_target = Position3D(0.4, 0.1, 0.4)
    assert policy.validate_command(
        "MoveArmCommand",
        {"arm": "right", "target": ok_target, "speed": 1.0}, robot,
    )[0]

    cases = [
        ({"arm": "middle", "target": ok_target}, "Invalid arm"),
        ({"arm": "right"}, "Missing target"),
        ({"arm": "right", "target": ok_target, "speed": 2.0}, "Invalid speed"),
        ({"arm": "right", "target": Position3D(0.8, 0.0, 0.4)}, "outside arm"),
        ({"arm": "right", "target": Position3D(0.1, 0.0, 0.4)}, "outside arm"),
        ({"arm": "left", "target": Position3D(0.4, 0.6, 0.4)}, "outside arm"),
        ({"arm": "right", "target": Position3D(0.4, 0.0, -0.1)}, "outside arm"),
        ({"arm": "right", "target": Position3D(0.4, 0.0, 0.9)}, "outside arm"),
    ]
    for params, expected in cases:
        allowed, reason = policy.validate_command("MoveArmCommand", params, robot)
        assert not allowed, params
        assert expected in reason, reason


def test_validate_tracks_velocity_limits(policy, robot):
    assert policy.validate_command(
        "MoveTracksCommand",
        {"linear_velocity": 0.3, "angular_velocity": 0.5}, robot,
    )[0]

    allowed, reason = policy.validate_command(
        "MoveTracksCommand", {"linear_velocity": 0.6}, robot,
    )
    assert not allowed and "0.5 m/s" in reason

    allowed, reason = policy.validate_command(
        "MoveTracksCommand", {"angular_velocity": -1.5}, robot,
    )
    assert not allowed and "1.0 rad/s" in reason


def test_node_health_errors_trigger_emergency_gate(policy, robot):
    # Emergency state reported on a node (not robot-level) must block commands.
    robot.nodes["node2"].health.errors.append("emergency_stop triggered by e-stop button")
    allowed, reason = policy.validate_command("MoveTracksCommand", {}, robot)
    assert not allowed
    assert reason == "Emergency stop active"


# === Safety policy: emergency conditions ===

def test_no_emergency_on_healthy_robot(policy, robot, make_node):
    from core.domain import BatteryHealth, BatteryState

    robot.battery = BatteryState(
        voltage_v=11.8, current_a=0.0, percentage=90.0,
        temperature_c=30.0, health=BatteryHealth.GOOD,
    )
    assert policy.check_emergency_conditions(robot) == []


def test_emergency_battery_voltage_and_percentage(policy, robot):
    from core.domain import BatteryHealth, BatteryState

    robot.battery = BatteryState(10.0, 0.0, 90.0, 30.0, BatteryHealth.GOOD)
    reasons = policy.check_emergency_conditions(robot)
    assert len(reasons) == 1 and "voltage critical" in reasons[0]

    robot.battery = BatteryState(11.8, 0.0, 15.0, 30.0, BatteryHealth.GOOD)
    reasons = policy.check_emergency_conditions(robot)
    assert len(reasons) == 1 and "Battery low" in reasons[0]


def test_emergency_missing_battery_is_not_a_crash(policy, robot):
    # battery=None must be tolerated (aggregate default)
    assert policy.check_emergency_conditions(robot) == []


def test_emergency_node_temperature(policy, make_node):
    # NodeHealth is an immutable VO: build the state instead of mutating it.
    robot = Robot()
    robot.add_node(make_node(temperature_c=85.0))
    reasons = policy.check_emergency_conditions(robot)
    assert any("temperature critical" in r for r in reasons)


def test_emergency_heartbeat_timeout_uses_node_type_watchdog(policy, make_node):
    robot = Robot()
    robot.add_node(make_node(heartbeat_age_s=30.0))  # HEAD watchdog = 5 s
    reasons = policy.check_emergency_conditions(robot)
    assert any("heartbeat timeout" in r for r in reasons)


def test_emergency_node_critical_error(policy, make_node):
    robot = Robot()
    robot.add_node(make_node(errors=["motor fault overcurrent"]))
    reasons = policy.check_emergency_conditions(robot)
    assert any("critical error" in r for r in reasons)


def test_non_critical_node_errors_do_not_trigger(policy, make_node):
    robot = Robot()
    robot.add_node(make_node(errors=["minor warning only"]))
    assert policy.check_emergency_conditions(robot) == []


# === Safety policy: fallbacks ===

def test_get_safe_fallback_per_node_and_fault(policy):
    head_default = policy.get_safe_fallback(NodeType.HEAD, "unknown")
    assert head_default["action"] == "home"

    head_fault = policy.get_safe_fallback(NodeType.HEAD, "servo_fault")
    assert head_fault["action"] == "disable_faulty_servo"

    head_comm = policy.get_safe_fallback(NodeType.HEAD, "comm_loss")
    assert head_comm["action"] == "home_and_hold"

    tracks_default = policy.get_safe_fallback(NodeType.TRACKS, "default")
    assert tracks_default["action"] == "emergency_brake"

    tracks_collision = policy.get_safe_fallback(NodeType.TRACKS, "collision")
    assert tracks_collision["action"] == "emergency_brake"

    arm = policy.get_safe_fallback(NodeType.RIGHT_ARM, "comm_loss")
    assert arm["action"] == "retract_and_brake"


def test_get_safe_fallback_for_unsupported_node_or_fault(policy):
    # Balance node has no dedicated fallback yet: returns {} instead of raising.
    assert policy.get_safe_fallback(NodeType.BALANCE, "default") == {}
    # Known node, unknown fault falls back to its default entry.
    tracks = policy.get_safe_fallback(NodeType.TRACKS, "weird_fault")
    assert tracks["action"] == "emergency_brake"


# === Motion planner ===

@pytest.fixture
def planner():
    return MotionPlannerService()


def test_joint_trajectory_reaches_goal(planner):
    trajectory = planner.plan_joint_trajectory(
        _joints(0.0), _joints(90.0),
        max_velocity={"j1": 90.0}, max_acceleration={"j1": 180.0},
        frequency=100.0,
    )
    assert len(trajectory) > 2
    assert trajectory[0]["j1"].to_degrees() == pytest.approx(0.0, abs=1e-9)
    assert trajectory[-1]["j1"].to_degrees() == pytest.approx(90.0, abs=1e-6)

    degrees = [p["j1"].to_degrees() for p in trajectory]
    assert degrees == sorted(degrees)  # monotonic ramp, no overshoot


def test_joint_trajectory_keeps_static_and_skipped_joints(planner):
    start = JointAngles({"j1": Angle(0.0), "j2": Angle(10.0), "j3": Angle(5.0)})
    goal = JointAngles({"j1": Angle(45.0), "j2": Angle(10.05)})  # j3 absent

    trajectory = planner.plan_joint_trajectory(
        start, goal,
        max_velocity={"j1": 90.0, "j2": 90.0, "j3": 90.0},
        max_acceleration={"j1": 180.0, "j2": 180.0, "j3": 180.0},
    )
    final = trajectory[-1]
    assert final["j1"].to_degrees() == pytest.approx(45.0, abs=1e-6)
    assert final["j2"].to_degrees() == pytest.approx(10.0, abs=1e-6)  # <0.1 deg: static
    assert "j3" not in final.angles  # not part of the goal


def test_joint_trajectory_when_nothing_moves(planner):
    start = _joints(0.0)
    trajectory = planner.plan_joint_trajectory(
        start, start, max_velocity={}, max_acceleration={},
    )
    assert trajectory  # still returns a (degenerate) trajectory
    assert trajectory[0]["j1"] == Angle(0.0)


def test_cartesian_trajectory_is_straight_line(planner):
    start = Position3D(0.0, 0.0, 0.5)
    goal = Position3D(0.6, 0.0, 0.5)
    trajectory = planner.plan_cartesian_trajectory(
        start, goal, max_velocity=0.3, max_acceleration=0.6, frequency=50.0,
    )
    assert trajectory[0] == start
    assert trajectory[-1].x == pytest.approx(goal.x, abs=1e-6)
    for point in trajectory:
        assert point.y == pytest.approx(0.0, abs=1e-9)
        assert point.z == pytest.approx(0.5, abs=1e-9)
        assert start.x - 1e-9 <= point.x <= goal.x + 1e-9


def test_cartesian_trajectory_degenerate_distance(planner):
    start = Position3D(1.0, 2.0, 3.0)
    goal = Position3D(1.0, 2.0, 3.0001)  # < 1 mm: no ramp to plan
    assert planner.plan_cartesian_trajectory(
        start, goal, max_velocity=0.3, max_acceleration=0.6,
    ) == [goal]


def test_cartesian_trajectory_triangular_profile(planner):
    # Very short distance: 2*d_acc >= distance -> triangular profile branch.
    start = Position3D(0.0, 0.0, 0.0)
    goal = Position3D(0.05, 0.0, 0.0)
    trajectory = planner.plan_cartesian_trajectory(
        start, goal, max_velocity=1.0, max_acceleration=0.5, frequency=200.0,
    )
    assert trajectory[-1].x == pytest.approx(goal.x, abs=1e-6)
