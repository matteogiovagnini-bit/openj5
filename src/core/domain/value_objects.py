"""
OpenJ5 Core Domain - Value Objects

Zero external dependencies. Pure Python domain primitives.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Self
import math


class AngleUnit(Enum):
    DEGREES = "deg"
    RADIANS = "rad"


@dataclass(frozen=True, slots=True)
class Angle:
    """Immutable angle value with unit safety."""
    value: float
    unit: AngleUnit = AngleUnit.DEGREES

    def __post_init__(self):
        if self.unit == AngleUnit.DEGREES:
            object.__setattr__(self, 'value', max(-180.0, min(180.0, self.value)))
        else:
            object.__setattr__(self, 'value', max(-math.pi, min(math.pi, self.value)))

    def to_degrees(self) -> float:
        return self.value if self.unit == AngleUnit.DEGREES else math.degrees(self.value)

    def to_radians(self) -> float:
        return math.radians(self.value) if self.unit == AngleUnit.DEGREES else self.value

    def __add__(self, other: Self) -> Self:
        if not isinstance(other, Angle):
            return NotImplemented
        return Angle(self.to_degrees() + other.to_degrees(), AngleUnit.DEGREES)

    def __sub__(self, other: Self) -> Self:
        if not isinstance(other, Angle):
            return NotImplemented
        return Angle(self.to_degrees() - other.to_degrees(), AngleUnit.DEGREES)

    def __mul__(self, scalar: float) -> Self:
        return Angle(self.to_degrees() * scalar, AngleUnit.DEGREES)

    def __abs__(self) -> Self:
        return Angle(abs(self.to_degrees()), AngleUnit.DEGREES)

    @classmethod
    def from_degrees(cls, degrees: float) -> Self:
        return cls(degrees, AngleUnit.DEGREES)

    @classmethod
    def from_radians(cls, radians: float) -> Self:
        return cls(radians, AngleUnit.RADIANS)

    @classmethod
    def zero(cls) -> Self:
        return cls(0.0, AngleUnit.DEGREES)


@dataclass(frozen=True, slots=True)
class Position3D:
    """Immutable 3D position in meters."""
    x: float
    y: float
    z: float
    frame: str = "base"  # base, head, camera, map, odom

    def distance_to(self, other: Self) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def __add__(self, other: Self) -> Self:
        if not isinstance(other, Position3D) or self.frame != other.frame:
            return NotImplemented
        return Position3D(self.x + other.x, self.y + other.y, self.z + other.z, self.frame)

    def __sub__(self, other: Self) -> Self:
        if not isinstance(other, Position3D) or self.frame != other.frame:
            return NotImplemented
        return Position3D(self.x - other.x, self.y - other.y, self.z - other.z, self.frame)

    def __mul__(self, scalar: float) -> Self:
        return Position3D(self.x * scalar, self.y * scalar, self.z * scalar, self.frame)

    @classmethod
    def zero(cls, frame: str = "base") -> Self:
        return cls(0.0, 0.0, 0.0, frame)


@dataclass(frozen=True, slots=True)
class Quaternion:
    """Immutable quaternion for orientation (w, x, y, z)."""
    w: float
    x: float
    y: float
    z: float

    def __post_init__(self):
        norm = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if abs(norm - 1.0) > 1e-6:
            object.__setattr__(self, 'w', self.w / norm)
            object.__setattr__(self, 'x', self.x / norm)
            object.__setattr__(self, 'y', self.y / norm)
            object.__setattr__(self, 'z', self.z / norm)

    def to_euler(self) -> tuple[float, float, float]:
        """Returns (roll, pitch, yaw) in radians."""
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (self.w * self.x + self.y * self.z)
        cosr_cosp = 1 - 2 * (self.x * self.x + self.y * self.y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (self.w * self.y - self.z * self.x)
        pitch = math.asin(max(-1.0, min(1.0, sinp)))

        # Yaw (z-axis rotation)
        siny_cosp = 2 * (self.w * self.z + self.x * self.y)
        cosy_cosp = 1 - 2 * (self.y * self.y + self.z * self.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    @classmethod
    def from_euler(cls, roll: float, pitch: float, yaw: float) -> Self:
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return cls(w, x, y, z)

    @classmethod
    def identity(cls) -> Self:
        return cls(1.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class Pose3D:
    """Immutable 3D pose (position + orientation)."""
    position: Position3D
    orientation: Quaternion

    @classmethod
    def zero(cls, frame: str = "base") -> Self:
        return cls(Position3D.zero(frame), Quaternion.identity())


@dataclass(frozen=True, slots=True)
class Twist:
    """Immutable velocity (linear + angular)."""
    linear: Position3D
    angular: Position3D

    @classmethod
    def zero(cls) -> Self:
        return cls(Position3D.zero(), Position3D.zero())


@dataclass(frozen=True, slots=True)
class JointAngles:
    """Immutable joint angles for a kinematic chain."""
    angles: dict[str, Angle]  # joint_name -> angle

    def get(self, joint_name: str) -> Optional[Angle]:
        return self.angles.get(joint_name)

    def __getitem__(self, joint_name: str) -> Angle:
        return self.angles[joint_name]

    def __contains__(self, joint_name: str) -> bool:
        return joint_name in self.angles


@dataclass(frozen=True, slots=True)
class ServoConfig:
    """Immutable servo configuration (from JSON config)."""
    name: str
    channel: int
    min_pulse: int
    max_pulse: int
    home_pulse: int
    min_angle: Angle
    max_angle: Angle
    home_angle: Angle
    speed_dps: float      # degrees per second
    acceleration_dps2: float  # degrees per second^2
    offset: Angle
    reversed: bool
    calibration: dict


@dataclass(frozen=True, slots=True)
class MotorConfig:
    """Immutable motor configuration."""
    motor_id: str
    motor_type: str  # dc_geared, bldc, stepper
    encoder_ppr: int
    gear_ratio: float
    wheel_diameter_mm: float
    max_rpm: float
    pid: PIDConfig


@dataclass(frozen=True, slots=True)
class PIDConfig:
    """Immutable PID configuration."""
    kp: float
    ki: float
    kd: float
    output_min: float
    output_max: float
    integral_min: float
    integral_max: float


@dataclass(frozen=True, slots=True)
class BatteryState:
    """Immutable battery telemetry."""
    voltage_v: float
    current_a: float        # positive = charging
    percentage: float       # 0.0 - 100.0
    temperature_c: float
    health: BatteryHealth
    time_remaining_min: Optional[float] = None


class BatteryHealth(Enum):
    GOOD = "good"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FAULT = "fault"


@dataclass(frozen=True, slots=True)
class TemperatureReading:
    """Immutable temperature reading."""
    sensor_id: str
    celsius: float
    timestamp: float


@dataclass(frozen=True, slots=True)
class DistanceReading:
    """Immutable distance sensor reading."""
    sensor_id: str
    distance_m: float
    confidence: float  # 0.0 - 1.0
    timestamp: float


@dataclass(frozen=True, slots=True)
class IMUReading:
    """Immutable IMU reading."""
    sensor_id: str
    orientation: Quaternion
    angular_velocity: Position3D  # rad/s
    linear_acceleration: Position3D  # m/s^2
    timestamp: float


@dataclass(frozen=True, slots=True)
class Odometry:
    """Immutable odometry data."""
    pose: Pose3D
    twist: Twist
    covariance: list[float]  # 6x6 matrix flattened
    timestamp: float


@dataclass(frozen=True, slots=True)
class NodeIdentity:
    """Immutable node identity."""
    node_id: str
    name: str
    node_type: NodeType
    hardware: str
    firmware_version: str
    hardware_version: str


class NodeType(Enum):
    ROBOT_CORE = "robot_core"
    HEAD = "head"
    RIGHT_ARM = "right_arm"
    LEFT_ARM = "left_arm"
    TORSO = "torso"
    TRACKS = "tracks"


class NodeState(Enum):
    BOOT = "boot"
    INIT = "init"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    RECOVERY = "recovery"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class NodeHealth:
    """Immutable node health status."""
    node_id: str
    state: NodeState
    cpu_percent: float
    memory_percent: float
    temperature_c: float
    uptime_sec: float
    last_heartbeat: float
    errors: list[str]
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class RobotState:
    """Immutable aggregate robot state."""
    node_health: dict[str, NodeHealth]
    battery: BatteryState
    pose: Optional[Pose3D]
    timestamp: float