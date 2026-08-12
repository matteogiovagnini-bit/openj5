"""
OpenJ5 Core Domain - Domain Services

Pure domain logic services.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import math

from .value_objects import (
    NodeState, NodeHealth, BatteryState, BatteryHealth,
    Position3D, JointAngles, NodeType, Angle
)
from .entities import Robot, Node, Servo, Motor


# === SAFETY POLICY ===

class ISafetyPolicy(ABC):
    """Safety policy interface - domain rules that must never be violated."""

    @abstractmethod
    def validate_command(self, command_type: str, params: dict, robot: Robot) -> tuple[bool, str]:
        """Validate command against safety rules. Returns (allowed, reason)."""
        ...

    @abstractmethod
    def check_emergency_conditions(self, robot: Robot) -> list[str]:
        """Check for conditions requiring emergency stop. Returns list of reasons."""
        ...

    @abstractmethod
    def get_safe_fallback(self, node_type: NodeType, fault: str) -> dict:
        """Get safe fallback behavior for a fault."""
        ...


class SafetyPolicyService(ISafetyPolicy):
    """Concrete safety policy implementation."""

    # Safety limits (from config in real implementation)
    MAX_JOINT_VELOCITY = {
        NodeType.HEAD: 180.0,      # deg/s
        NodeType.RIGHT_ARM: 120.0,
        NodeType.LEFT_ARM: 120.0,
        NodeType.TORSO: 60.0,
    }

    COLLISION_THRESHOLD = 0.3  # meters

    BATTERY_CRITICAL_VOLTAGE = 10.5  # V
    BATTERY_LOW_PERCENT = 20  # %

    TEMPERATURE_CRITICAL = 70.0  # Celsius

    WATCHDOG_TIMEOUTS = {
        NodeType.HEAD: 5.0,        # seconds
        NodeType.RIGHT_ARM: 5.0,
        NodeType.LEFT_ARM: 5.0,
        NodeType.TORSO: 10.0,
        NodeType.TRACKS: 1.0,      # Critical: tracks need fast watchdog
    }

    def validate_command(self, command_type: str, params: dict, robot: Robot) -> tuple[bool, str]:
        """Validate command against safety rules."""

        # Check robot state
        if robot.state and robot.state not in (NodeState.READY, NodeState.RUNNING):
            return False, f"Robot not in operable state: {robot.state}"

        # Emergency stop active
        if any("emergency_stop" in str(e).lower() for e in robot.get_errors()):
            return False, "Emergency stop active"

        # Validate specific commands
        if command_type == "MoveHeadCommand":
            return self._validate_head_move(params)
        elif command_type == "MoveArmCommand":
            return self._validate_arm_move(params)
        elif command_type == "MoveTracksCommand":
            return self._validate_tracks_move(params)

        return True, ""

    def _validate_head_move(self, params: dict) -> tuple[bool, str]:
        target = params.get("target")
        speed = params.get("speed", 1.0)

        if not target:
            return False, "Missing target position"

        if not (0.0 <= speed <= 1.0):
            return False, f"Invalid speed: {speed} (must be 0.0-1.0)"

        # Check workspace limits
        if target.x < 0.2 or target.x > 1.5:
            return False, f"Target X {target.x} outside workspace"
        if abs(target.y) > 0.8:
            return False, f"Target Y {target.y} outside workspace"
        if target.z < 0.5 or target.z > 1.8:
            return False, f"Target Z {target.z} outside workspace"

        return True, ""

    def _validate_arm_move(self, params: dict) -> tuple[bool, str]:
        arm = params.get("arm")
        target = params.get("target")
        speed = params.get("speed", 1.0)

        if arm not in ("right", "left"):
            return False, f"Invalid arm: {arm}"

        if not target:
            return False, "Missing target position"

        if not (0.0 <= speed <= 1.0):
            return False, f"Invalid speed: {speed}"

        # Arm workspace (simplified)
        if target.x < 0.15 or target.x > 0.7:
            return False, f"Target X {target.x} outside arm workspace"
        if abs(target.y) > 0.5:
            return False, f"Target Y {target.y} outside arm workspace"
        if target.z < 0.0 or target.z > 0.8:
            return False, f"Target Z {target.z} outside arm workspace"

        return True, ""

    def _validate_tracks_move(self, params: dict) -> tuple[bool, str]:
        linear = params.get("linear_velocity", 0.0)
        angular = params.get("angular_velocity", 0.0)

        if abs(linear) > 0.5:
            return False, f"Linear velocity {linear} exceeds max 0.5 m/s"

        if abs(angular) > 1.0:
            return False, f"Angular velocity {angular} exceeds max 1.0 rad/s"

        return True, ""

    def check_emergency_conditions(self, robot: Robot) -> list[str]:
        """Check all nodes for emergency conditions."""
        reasons = []

        # Battery critical
        if robot.battery and robot.battery.voltage_v < self.BATTERY_CRITICAL_VOLTAGE:
            reasons.append(f"Battery voltage critical: {robot.battery.voltage_v}V")

        if robot.battery and robot.battery.percentage < self.BATTERY_LOW_PERCENT:
            reasons.append(f"Battery low: {robot.battery.percentage}%")

        # Node health
        for node_id, node in robot.nodes.items():
            health = node.health

            # Temperature
            if health.temperature_c > self.TEMPERATURE_CRITICAL:
                reasons.append(f"Node {node_id} temperature critical: {health.temperature_c}C")

            # Watchdog
            time_since_heartbeat = math.time() - health.last_heartbeat
            timeout = self.WATCHDOG_TIMEOUTS.get(node.identity.node_type, 5.0)
            if time_since_heartbeat > timeout:
                reasons.append(f"Node {node_id} heartbeat timeout: {time_since_heartbeat:.1f}s")

            # Errors
            if health.errors:
                for err in health.errors:
                    if "critical" in err.lower() or "fault" in err.lower():
                        reasons.append(f"Node {node_id} critical error: {err}")

        # Collision detection (simplified)
        if robot.tracks_odometry:
            # Check ToF sensors from track node
            pass

        return reasons

    def get_safe_fallback(self, node_type: NodeType, fault: str) -> dict:
        """Define safe fallback behavior per node type and fault."""
        fallbacks = {
            NodeType.HEAD: {
                "default": {"action": "home", "params": {"speed": 0.3}},
                "servo_fault": {"action": "disable_faulty_servo", "params": {}},
                "comm_loss": {"action": "home_and_hold", "params": {}},
            },
            NodeType.RIGHT_ARM: {
                "default": {"action": "retract", "params": {"speed": 0.2}},
                "servo_fault": {"action": "retract_safe", "params": {}},
                "comm_loss": {"action": "retract_and_brake", "params": {}},
            },
            NodeType.LEFT_ARM: {
                "default": {"action": "retract", "params": {"speed": 0.2}},
                "servo_fault": {"action": "retract_safe", "params": {}},
                "comm_loss": {"action": "retract_and_brake", "params": {}},
            },
            NodeType.TORSO: {
                "default": {"action": "home", "params": {"speed": 0.2}},
                "comm_loss": {"action": "home_and_hold", "params": {}},
            },
            NodeType.TRACKS: {
                "default": {"action": "emergency_brake", "params": {}},
                "motor_fault": {"action": "emergency_brake", "params": {}},
                "comm_loss": {"action": "emergency_brake", "params": {}},
                "collision": {"action": "emergency_brake", "params": {}},
            },
        }

        return fallbacks.get(node_type, {}).get(fault, fallbacks.get(node_type, {}).get("default", {}))


# === MOTION PLANNER (simplified) ===

class MotionPlannerService:
    """Trajectory generation service."""

    def plan_joint_trajectory(
        self,
        start: JointAngles,
        goal: JointAngles,
        max_velocity: dict[str, float],
        max_acceleration: dict[str, float],
        frequency: float = 100.0
    ) -> list[JointAngles]:
        """Generate trapezoidal velocity profile for each joint."""
        trajectory = []

        # Find longest move to determine total time
        max_time = 0.0
        joint_profiles = {}

        for name in start.angles:
            if name not in goal.angles:
                continue

            start_deg = start.angles[name].to_degrees()
            goal_deg = goal.angles[name].to_degrees()
            delta = abs(goal_deg - start_deg)

            if delta < 0.1:
                joint_profiles[name] = None
                continue

            v_max = max_velocity.get(name, 60.0)
            a_max = max_acceleration.get(name, 120.0)

            # Trapezoidal profile time
            t_acc = v_max / a_max
            d_acc = 0.5 * a_max * t_acc**2

            if 2 * d_acc >= delta:
                # Triangular profile
                t_total = 2 * math.sqrt(delta / a_max)
            else:
                # Trapezoidal profile
                d_cruise = delta - 2 * d_acc
                t_cruise = d_cruise / v_max
                t_total = 2 * t_acc + t_cruise

            max_time = max(max_time, t_total)
            joint_profiles[name] = (start_deg, goal_deg, v_max, a_max, t_total)

        # Generate trajectory points
        num_steps = max(1, int(max_time * frequency))
        dt = max_time / num_steps if num_steps > 0 else 0

        for step in range(num_steps + 1):
            t = step * dt
            angles = {}

            for name, profile in joint_profiles.items():
                if profile is None:
                    angles[name] = start.angles[name]
                    continue

                start_deg, goal_deg, v_max, a_max, t_total = profile
                delta = goal_deg - start_deg
                direction = 1 if delta > 0 else -1
                delta = abs(delta)

                t_acc = v_max / a_max
                d_acc = 0.5 * a_max * t_acc**2

                if t <= t_acc:
                    # Acceleration phase
                    pos = 0.5 * a_max * t**2
                elif t <= t_total - t_acc:
                    # Cruise phase
                    pos = d_acc + v_max * (t - t_acc)
                elif t <= t_total:
                    # Deceleration phase
                    t_dec = t_total - t
                    pos = delta - 0.5 * a_max * t_dec**2
                else:
                    pos = delta

                angles[name] = Angle.from_degrees(start_deg + direction * pos)

            trajectory.append(JointAngles(angles))

        return trajectory


    def plan_cartesian_trajectory(
        self,
        start: Position3D,
        goal: Position3D,
        max_velocity: float,
        max_acceleration: float,
        frequency: float = 100.0
    ) -> list[Position3D]:
        """Straight line cartesian trajectory with trapezoidal profile."""
        delta = goal - start
        distance = math.sqrt(delta.x**2 + delta.y**2 + delta.z**2)

        if distance < 0.001:
            return [goal]

        t_acc = max_velocity / max_acceleration
        d_acc = 0.5 * max_acceleration * t_acc**2

        if 2 * d_acc >= distance:
            t_total = 2 * math.sqrt(distance / max_acceleration)
        else:
            d_cruise = distance - 2 * d_acc
            t_cruise = d_cruise / max_velocity
            t_total = 2 * t_acc + t_cruise

        num_steps = max(1, int(t_total * frequency))
        dt = t_total / num_steps

        trajectory = []
        for step in range(num_steps + 1):
            t = step * dt
            if t <= t_acc:
                s = 0.5 * max_acceleration * t**2
            elif t <= t_total - t_acc:
                s = d_acc + max_velocity * (t - t_acc)
            elif t <= t_total:
                t_dec = t_total - t
                s = distance - 0.5 * max_acceleration * t_dec**2
            else:
                s = distance

            ratio = s / distance
            pos = Position3D(
                start.x + delta.x * ratio,
                start.y + delta.y * ratio,
                start.z + delta.z * ratio,
                frame=start.frame
            )
            trajectory.append(pos)

        return trajectory