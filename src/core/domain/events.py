"""
OpenJ5 Core Domain - Domain Events

Immutable events for Event-Driven Architecture.
"""
from __future__ import annotations
from dataclasses import dataclass, field, fields
from enum import Enum
from datetime import datetime
import uuid


class EventCategory(Enum):
    COMMAND = "command"
    TELEMETRY = "telemetry"
    STATE = "state"
    ERROR = "error"
    BUSINESS = "business"


@dataclass(frozen=True)
class DomainEvent:
    """Base domain event - immutable, versioned."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    event_version: int = 1
    category: EventCategory = EventCategory.BUSINESS
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    source_node: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    payload: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.event_type:
            object.__setattr__(self, 'event_type', self.__class__.__name__)
        if not self.correlation_id:
            object.__setattr__(self, 'correlation_id', self.event_id)

    def to_dict(self) -> dict:
        """Serialize the whole event, including subclass-specific fields.

        Only serializing the base fields would silently drop payload data
        (target_x, voltage_v, ...) on every publish to the event bus.
        """
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        if isinstance(data.get("category"), EventCategory):
            data["category"] = data["category"].value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> DomainEvent:
        """Rebuild an event of this class, ignoring unknown keys.

        Unknown keys are dropped so the base class can safely read a dict
        produced by a subclass (use ``deserialize_event`` for typed
        reconstruction). Scalar wire values may arrive as strings from Redis.
        """
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        if isinstance(kwargs.get("category"), str):
            kwargs["category"] = EventCategory(kwargs["category"])
        if isinstance(kwargs.get("event_version"), str):
            kwargs["event_version"] = int(kwargs["event_version"])
        if isinstance(kwargs.get("timestamp"), str):
            kwargs["timestamp"] = float(kwargs["timestamp"])
        return cls(**kwargs)


# === COMMAND EVENTS ===

@dataclass(frozen=True)
class MoveHeadCommandEvent(DomainEvent):
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    frame: str = "base"
    speed: float = 1.0
    blocking: bool = True

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.COMMAND)


@dataclass(frozen=True)
class MoveArmCommandEvent(DomainEvent):
    arm: str = "right"
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    frame: str = "base"
    speed: float = 1.0
    blocking: bool = True

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.COMMAND)


@dataclass(frozen=True)
class MoveTracksCommandEvent(DomainEvent):
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    distance: float = 0.0
    angle: float = 0.0
    blocking: bool = True

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.COMMAND)


@dataclass(frozen=True)
class SayTextCommandEvent(DomainEvent):
    text: str = ""
    language: str = "it"
    voice: str = "default"
    speed: float = 1.0
    blocking: bool = True

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.COMMAND)


@dataclass(frozen=True)
class BodyCommandEvent(DomainEvent):
    """Logical command for the body leveling joint (ADR-017).

    action: "level" | "tilt" | "stow" | "stop". Only logical intent crosses
    the bus: the ESP32 translates it into stepper trajectories.
    """
    action: str = "level"
    angle_deg: float = 0.0
    speed: float = 0.5
    blocking: bool = True

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.COMMAND)


@dataclass(frozen=True)
class BehaviorCommandEvent(DomainEvent):
    behavior: str = ""
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.COMMAND)


@dataclass(frozen=True)
class EmergencyStopCommandEvent(DomainEvent):
    reason: str = "manual"
    scope: str = "all"

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.COMMAND)


# === TELEMETRY EVENTS ===

@dataclass(frozen=True)
class ServoTelemetryEvent(DomainEvent):
    servo_name: str = ""
    position_deg: float = 0.0
    target_deg: float = 0.0
    velocity_dps: float = 0.0
    current_ma: float = 0.0
    temperature_c: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.TELEMETRY)


@dataclass(frozen=True)
class MotorTelemetryEvent(DomainEvent):
    motor_id: str = ""
    velocity_rpm: float = 0.0
    target_rpm: float = 0.0
    position_ticks: int = 0
    current_ma: float = 0.0
    temperature_c: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.TELEMETRY)


@dataclass(frozen=True)
class BatteryTelemetryEvent(DomainEvent):
    voltage_v: float = 0.0
    current_a: float = 0.0
    percentage: float = 0.0
    temperature_c: float = 0.0
    health: str = "good"
    time_remaining_min: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.TELEMETRY)


@dataclass(frozen=True)
class IMUTelemetryEvent(DomainEvent):
    sensor_id: str = ""
    orientation_w: float = 1.0
    orientation_x: float = 0.0
    orientation_y: float = 0.0
    orientation_z: float = 0.0
    angular_vel_x: float = 0.0
    angular_vel_y: float = 0.0
    angular_vel_z: float = 0.0
    linear_acc_x: float = 0.0
    linear_acc_y: float = 0.0
    linear_acc_z: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.TELEMETRY)


@dataclass(frozen=True)
class DistanceTelemetryEvent(DomainEvent):
    sensor_id: str = ""
    distance_m: float = 0.0
    confidence: float = 1.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.TELEMETRY)


@dataclass(frozen=True)
class OdometryTelemetryEvent(DomainEvent):
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    linear_vel: float = 0.0
    angular_vel: float = 0.0
    covariance: list = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.TELEMETRY)


@dataclass(frozen=True)
class BodyTelemetryEvent(DomainEvent):
    """Leveling joint + body pitch telemetry (ADR-017)."""
    body_pitch_deg: float = 0.0
    track_pitch_deg: float = 0.0
    joint_angle_deg: float = 0.0
    target_angle_deg: float = 0.0
    leveling_enabled: bool = False
    control_hz: int = 0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.TELEMETRY)


# === STATE EVENTS ===

@dataclass(frozen=True)
class NodeStateChangedEvent(DomainEvent):
    node_id: str = ""
    previous_state: str = ""
    new_state: str = ""
    reason: str = ""

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.STATE)


@dataclass(frozen=True)
class RobotStateChangedEvent(DomainEvent):
    previous_state: str = ""
    new_state: str = ""
    reason: str = ""

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.STATE)


@dataclass(frozen=True)
class PluginStateChangedEvent(DomainEvent):
    plugin_id: str = ""
    previous_state: str = ""
    new_state: str = ""

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.STATE)


@dataclass(frozen=True)
class BalanceStateChangedEvent(DomainEvent):
    """Body leveling state change (ADR-017)."""
    enabled: bool = False
    target_pitch_deg: float = 0.0
    reason: str = ""

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.STATE)


# === ERROR EVENTS ===

@dataclass(frozen=True)
class HardwareFaultEvent(DomainEvent):
    node_id: str = ""
    component: str = ""  # servo, motor, sensor, comm
    component_id: str = ""
    fault_code: str = ""
    description: str = ""
    severity: str = "error"  # warning, error, critical

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.ERROR)


@dataclass(frozen=True)
class CommunicationLostEvent(DomainEvent):
    node_id: str = ""
    last_seen: float = 0.0
    timeout_ms: int = 5000

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.ERROR)


@dataclass(frozen=True)
class SafetyViolationEvent(DomainEvent):
    node_id: str = ""
    violation_type: str = ""  # velocity_limit, workspace_limit, collision, battery_critical
    description: str = ""
    command_id: str = ""

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.ERROR)


# === BUSINESS EVENTS ===

@dataclass(frozen=True)
class FaceDetectedEvent(DomainEvent):
    face_id: str = ""
    bbox_x: float = 0.0
    bbox_y: float = 0.0
    bbox_w: float = 0.0
    bbox_h: float = 0.0
    confidence: float = 0.0
    landmarks: dict = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


@dataclass(frozen=True)
class FaceRecognizedEvent(DomainEvent):
    face_id: str = ""
    identity: str = ""
    confidence: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


@dataclass(frozen=True)
class ObjectDetectedEvent(DomainEvent):
    object_id: str = ""
    class_name: str = ""
    bbox_x: float = 0.0
    bbox_y: float = 0.0
    bbox_w: float = 0.0
    bbox_h: float = 0.0
    confidence: float = 0.0
    position_3d: dict = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


@dataclass(frozen=True)
class ObjectGraspedEvent(DomainEvent):
    object_id: str = ""
    arm: str = "right"
    grasp_success: bool = True

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


@dataclass(frozen=True)
class SpeechRecognizedEvent(DomainEvent):
    text: str = ""
    confidence: float = 0.0
    language: str = "it"
    wake_word: bool = False
    alternatives: list = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


@dataclass(frozen=True)
class PersonFollowedEvent(DomainEvent):
    person_id: str = ""
    distance_m: float = 0.0
    following: bool = True

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


@dataclass(frozen=True)
class DockingCompleteEvent(DomainEvent):
    dock_id: str = ""
    success: bool = True
    final_position: dict = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


@dataclass(frozen=True)
class OTADeployedEvent(DomainEvent):
    node_id: str = ""
    firmware_version: str = ""
    success: bool = True
    rollback: bool = False

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'category', EventCategory.BUSINESS)


# === EVENT REGISTRY ===

EVENT_CLASSES = {
    "MoveHeadCommandEvent": MoveHeadCommandEvent,
    "MoveArmCommandEvent": MoveArmCommandEvent,
    "MoveTracksCommandEvent": MoveTracksCommandEvent,
    "SayTextCommandEvent": SayTextCommandEvent,
    "BehaviorCommandEvent": BehaviorCommandEvent,
    "EmergencyStopCommandEvent": EmergencyStopCommandEvent,
    "BodyCommandEvent": BodyCommandEvent,
    "ServoTelemetryEvent": ServoTelemetryEvent,
    "MotorTelemetryEvent": MotorTelemetryEvent,
    "BatteryTelemetryEvent": BatteryTelemetryEvent,
    "IMUTelemetryEvent": IMUTelemetryEvent,
    "DistanceTelemetryEvent": DistanceTelemetryEvent,
    "OdometryTelemetryEvent": OdometryTelemetryEvent,
    "BodyTelemetryEvent": BodyTelemetryEvent,
    "NodeStateChangedEvent": NodeStateChangedEvent,
    "RobotStateChangedEvent": RobotStateChangedEvent,
    "PluginStateChangedEvent": PluginStateChangedEvent,
    "BalanceStateChangedEvent": BalanceStateChangedEvent,
    "HardwareFaultEvent": HardwareFaultEvent,
    "CommunicationLostEvent": CommunicationLostEvent,
    "SafetyViolationEvent": SafetyViolationEvent,
    "FaceDetectedEvent": FaceDetectedEvent,
    "FaceRecognizedEvent": FaceRecognizedEvent,
    "ObjectDetectedEvent": ObjectDetectedEvent,
    "ObjectGraspedEvent": ObjectGraspedEvent,
    "SpeechRecognizedEvent": SpeechRecognizedEvent,
    "PersonFollowedEvent": PersonFollowedEvent,
    "DockingCompleteEvent": DockingCompleteEvent,
    "OTADeployedEvent": OTADeployedEvent,
}

def _event_category(cls: type[DomainEvent]) -> str:
    """Resolve the category declared by an event subclass __post_init__."""
    return cls().category.value


# Categories are assigned per-class inside __post_init__, so the class-level
# default (BUSINESS) is wrong here: resolve them from a default instance.
EVENT_CATEGORIES = {name: cls().category for name, cls in EVENT_CLASSES.items()}

EVENT_SCHEMAS = {
    name: {
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "event_type": {"const": name},
            "event_version": {"type": "integer", "const": 1},
            "category": {"type": "string", "const": _event_category(cls)},
            "timestamp": {"type": "number"},
            "source_node": {"type": "string"},
            "correlation_id": {"type": "string"},
            "causation_id": {"type": "string"},
            "payload": {"type": "object"}
        },
        "required": ["event_id", "event_type", "event_version", "category", "timestamp", "source_node", "correlation_id", "payload"]
    }
    for name, cls in EVENT_CLASSES.items()
}


def create_event(event_type: str, **payload) -> DomainEvent:
    """Factory function to create typed events."""
    cls = EVENT_CLASSES.get(event_type)
    if not cls:
        raise ValueError(f"Unknown event type: {event_type}")
    return cls(**payload)


def deserialize_event(data: dict) -> DomainEvent:
    """Deserialize event from dict."""
    event_type = data.get("event_type")
    cls = EVENT_CLASSES.get(event_type)
    if not cls:
        return DomainEvent(**data)  # fallback to base
    return cls.from_dict(data)