"""
OpenJ5 Core Domain - Entities

Entities have identity and lifecycle. Pure domain objects.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid

from .value_objects import (
    NodeIdentity, NodeState, NodeHealth,
    BatteryState,
    ServoConfig, MotorConfig, StepperConfig, CalibrationData,
    PluginMetadata
)


@dataclass
class Entity:
    """Base entity with identity and version."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 0
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def touch(self) -> None:
        self.version += 1
        self.updated_at = datetime.now().timestamp()


@dataclass
class Robot(Entity):
    """Robot aggregate root."""
    name: str = "OpenJ5"
    nodes: dict[str, Node] = field(default_factory=dict)
    plugins: dict[str, Plugin] = field(default_factory=dict)
    state: Optional[NodeState] = None      # robot-level lifecycle (ADR-009 states)
    battery: Optional[BatteryState] = None  # latest battery telemetry (safety input)
    errors: list[str] = field(default_factory=list)  # robot-level errors (e.g. emergency stop)

    def add_node(self, node: Node) -> None:
        self.nodes[node.identity.node_id] = node
        self.touch()

    def remove_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        self.touch()

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def get_healthy_nodes(self) -> list[Node]:
        return [n for n in self.nodes.values() if n.health.state == NodeState.RUNNING]

    def get_errors(self) -> list[str]:
        """Robot-level errors plus every node health error (inputs to ISafetyPolicy)."""
        errors = list(self.errors)
        for node in self.nodes.values():
            errors.extend(node.health.errors)
        return errors


@dataclass
class Node(Entity):
    """Robot node entity."""
    identity: NodeIdentity = field(kw_only=True)
    health: NodeHealth = field(kw_only=True)
    config: dict = field(default_factory=dict)
    servos: dict[str, Servo] = field(default_factory=dict)
    motors: dict[str, Motor] = field(default_factory=dict)
    steppers: dict[str, Stepper] = field(default_factory=dict)

    def update_health(self, health: NodeHealth) -> None:
        self.health = health
        self.touch()

    def add_servo(self, servo: Servo) -> None:
        self.servos[servo.config.name] = servo
        self.touch()

    def add_motor(self, motor: Motor) -> None:
        self.motors[motor.config.motor_id] = motor
        self.touch()

    def add_stepper(self, stepper: Stepper) -> None:
        self.steppers[stepper.config.name] = stepper
        self.touch()


@dataclass
class Servo(Entity):
    """Servo entity."""
    node_id: str = field(kw_only=True)
    config: ServoConfig = field(kw_only=True)
    current_position: float = 0.0  # degrees
    target_position: float = 0.0
    is_moving: bool = False
    calibration: CalibrationData = None

    def move_to(self, angle: float, speed: float = 1.0) -> None:
        self.target_position = max(self.config.min_angle.to_degrees(),
                                   min(self.config.max_angle.to_degrees(), angle))
        self.is_moving = True
        self.touch()

    def update_position(self, angle: float) -> None:
        self.current_position = angle
        self.is_moving = abs(self.current_position - self.target_position) > 0.5
        self.touch()


@dataclass
class Motor(Entity):
    """Motor entity."""
    node_id: str = field(kw_only=True)
    config: MotorConfig = field(kw_only=True)
    current_velocity: float = 0.0  # RPM
    target_velocity: float = 0.0
    position: float = 0.0  # encoder ticks
    odometry_x: float = 0.0
    odometry_y: float = 0.0
    odometry_theta: float = 0.0

    def set_velocity(self, rpm: float) -> None:
        self.target_velocity = max(-self.config.max_rpm, min(self.config.max_rpm, rpm))
        self.touch()

    def update_odometry(self, x: float, y: float, theta: float) -> None:
        self.odometry_x = x
        self.odometry_y = y
        self.odometry_theta = theta
        self.touch()


@dataclass
class Stepper(Entity):
    """Stepper motor entity (ADR-017, STEP/DIR driver + optional reduction)."""
    node_id: str = field(kw_only=True)
    config: StepperConfig = field(kw_only=True)
    current_position_steps: int = 0
    target_position_steps: int = 0
    enabled: bool = False
    is_moving: bool = False

    def move_relative_deg(self, deg: float) -> None:
        """Move by a relative joint angle (handles inverted + reduction)."""
        steps = self.config.deg_to_steps(deg)
        if self.config.inverted:
            steps = -steps
        self.move_to_steps(self.current_position_steps + steps)

    def move_to_steps(self, target_steps: int) -> None:
        self.target_position_steps = target_steps
        self.is_moving = self.current_position_steps != target_steps
        self.touch()

    def update_position_steps(self, steps: int) -> None:
        self.current_position_steps = steps
        self.is_moving = abs(self.current_position_steps - self.target_position_steps) > 0
        self.touch()

    @property
    def current_angle_deg(self) -> float:
        deg = self.config.steps_to_deg(self.current_position_steps)
        return -deg if self.config.inverted else deg


@dataclass
class Plugin(Entity):
    """Plugin entity."""
    metadata: PluginMetadata = field(kw_only=True)
    state: str = "loaded"  # loaded, starting, running, stopping, stopped, error
    config: dict = field(default_factory=dict)
    instance: object = None  # Plugin instance (set by PluginManager)

    def start(self) -> None:
        self.state = "starting"
        self.touch()

    def mark_running(self) -> None:
        self.state = "running"
        self.touch()

    def stop(self) -> None:
        self.state = "stopping"
        self.touch()

    def mark_stopped(self) -> None:
        self.state = "stopped"
        self.touch()

    def mark_error(self, error: str) -> None:
        self.state = "error"
        self.touch()


@dataclass
class Calibration(Entity):
    """Calibration entity."""
    node_id: str = field(kw_only=True)
    component: str = field(kw_only=True)  # servo:head:neck_yaw, imu:head, etc.
    data: CalibrationData = field(kw_only=True)
    verified: bool = False
    verified_at: Optional[float] = None

    def verify(self) -> None:
        self.verified = True
        self.verified_at = datetime.now().timestamp()
        self.touch()