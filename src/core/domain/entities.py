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
    NodeIdentity, NodeState, NodeHealth, RobotState,
    ServoConfig, MotorConfig, CalibrationData,
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
    state: RobotState = None

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


@dataclass
class Node(Entity):
    """Robot node entity."""
    identity: NodeIdentity
    health: NodeHealth
    config: dict = field(default_factory=dict)
    servos: dict[str, Servo] = field(default_factory=dict)
    motors: dict[str, Motor] = field(default_factory=dict)

    def update_health(self, health: NodeHealth) -> None:
        self.health = health
        self.touch()

    def add_servo(self, servo: Servo) -> None:
        self.servos[servo.config.name] = servo
        self.touch()

    def add_motor(self, motor: Motor) -> None:
        self.motors[motor.config.motor_id] = motor
        self.touch()


@dataclass
class Servo(Entity):
    """Servo entity."""
    node_id: str
    config: ServoConfig
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
    node_id: str
    config: MotorConfig
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
class Plugin(Entity):
    """Plugin entity."""
    metadata: PluginMetadata
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
    node_id: str
    component: str  # servo:head:neck_yaw, imu:head, etc.
    data: CalibrationData
    verified: bool = False
    verified_at: Optional[float] = None

    def verify(self) -> None:
        self.verified = True
        self.verified_at = datetime.now().timestamp()
        self.touch()