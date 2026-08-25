"""
OpenJ5 Core Domain - Commands & Queries (CQRS)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar
import uuid
import time


class CommandError(Exception):
    """Command execution error."""
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")


@dataclass
class Result:
    """Command/Query result wrapper."""
    success: bool = True
    error_code: str = None
    error_message: str = None
    data: Any = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, **metadata) -> Result:
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, code: str, message: str, details: dict = None) -> Result:
        return cls(success=False, error_code=code, error_message=message, metadata=details or {})

    def unwrap(self) -> Any:
        if not self.success:
            raise CommandError(self.error_code, self.error_message, self.metadata)
        return self.data

    def __bool__(self) -> bool:
        return self.success


# === BASE CLASSES ===

TResult = TypeVar('TResult')

@dataclass
class Command(ABC, Generic[TResult]):
    """Base command - mutates state."""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""
    causation_id: str = ""
    metadata: dict = field(default_factory=dict)

    @abstractmethod
    def __post_init__(self):
        pass


@dataclass
class Query(ABC, Generic[TResult]):
    """Base query - reads state, no side effects."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""


# === COMMANDS ===

@dataclass
class MoveHeadCommand(Command[Result]):
    """Move head to target position."""
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    frame: str = "base"
    speed: float = 1.0
    blocking: bool = True

    def __post_init__(self):
        if not (0.0 <= self.speed <= 1.0):
            raise ValueError("speed must be 0.0-1.0")


@dataclass
class MoveArmCommand(Command[Result]):
    """Move arm to target."""
    arm: str = "right"  # "right" | "left"
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    frame: str = "base"
    speed: float = 1.0
    blocking: bool = True

    def __post_init__(self):
        if self.arm not in ("right", "left"):
            raise ValueError("arm must be 'right' or 'left'")
        if not (0.0 <= self.speed <= 1.0):
            raise ValueError("speed must be 0.0-1.0")


@dataclass
class MoveTracksCommand(Command[Result]):
    """Move tracks."""
    linear_velocity: float = 0.0   # m/s
    angular_velocity: float = 0.0  # rad/s
    distance: float = 0.0          # m (0 = continuous)
    angle: float = 0.0             # rad (0 = continuous)
    blocking: bool = True

    def __post_init__(self):
        if abs(self.linear_velocity) > 0.5:
            raise ValueError("linear_velocity max 0.5 m/s")
        if abs(self.angular_velocity) > 1.0:
            raise ValueError("angular_velocity max 1.0 rad/s")


@dataclass
class SayTextCommand(Command[Result]):
    """Speak text."""
    text: str = ""
    language: str = "it"
    voice: str = "default"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    blocking: bool = True

    def __post_init__(self):
        if not self.text:
            raise ValueError("text cannot be empty")


@dataclass
class SetExpressionCommand(Command[Result]):
    """Set facial expression."""
    expression: str = "neutral"
    intensity: float = 1.0
    duration: float = 0.0  # 0 = hold


@dataclass
class SetLEDCommand(Command[Result]):
    """Set LED pattern."""
    node_id: str = ""
    pattern: str = "solid"  # solid, breathing, pulse, rainbow, chase, error
    color_r: int = 255
    color_g: int = 255
    color_b: int = 255
    brightness: float = 1.0


@dataclass
class BehaviorCommand(Command[Result]):
    """Start/stop behavior."""
    behavior: str = "idle"  # idle, follow_person, sleep, wake_up, greet, dance
    params: dict = field(default_factory=dict)
    blocking: bool = False


@dataclass
class EmergencyStopCommand(Command[Result]):
    """Emergency stop."""
    reason: str = "manual"
    scope: str = "all"  # all, head, arms, tracks


@dataclass
class DeployOTACommand(Command[Result]):
    """Deploy OTA update."""
    target_nodes: list[str] = field(default_factory=list)  # empty = all
    firmware_url: str = ""
    firmware_hash: str = ""
    signature: str = ""
    force: bool = False


@dataclass
class LoadPluginCommand(Command[Result]):
    """Load plugin."""
    plugin_id: str = ""
    config: dict = field(default_factory=dict)


@dataclass
class UnloadPluginCommand(Command[Result]):
    """Unload plugin."""
    plugin_id: str = ""


@dataclass
class SaveCalibrationCommand(Command[Result]):
    """Save calibration data."""
    node_id: str = ""
    component: str = ""  # servo:head:neck_yaw, imu:head, etc.
    data: dict = field(default_factory=dict)


@dataclass
class SetConfigurationCommand(Command[Result]):
    """Update configuration at runtime."""
    key: str = ""
    value: Any = None
    persistent: bool = True


# === QUERIES ===

@dataclass
class GetRobotStateQuery(Query[Result]):
    """Get aggregate robot state."""
    include_telemetry: bool = True


@dataclass
class GetNodeHealthQuery(Query[Result]):
    """Get node health."""
    node_id: str = ""


@dataclass
class GetServoPositionQuery(Query[Result]):
    """Get servo position."""
    node_id: str = ""
    servo_name: str = ""


@dataclass
class GetArmPoseQuery(Query[Result]):
    """Get arm end-effector pose."""
    arm: str = "right"


@dataclass
class GetOdometryQuery(Query[Result]):
    """Get odometry."""
    frame: str = "odom"


@dataclass
class GetBatteryStateQuery(Query[Result]):
    """Get battery state."""
    pass


@dataclass
class GetPluginListQuery(Query[Result]):
    """Get loaded plugins."""
    pass


@dataclass
class GetConfigQuery(Query[Result]):
    """Get configuration value."""
    key: str = ""
    default: Any = None


@dataclass
class GetCalibrationQuery(Query[Result]):
    """Get calibration data."""
    node_id: str = ""
    component: str = ""


@dataclass
class GetHeadAnglesQuery(Query[Result]):
    """Get head joint angles."""
    pass


@dataclass
class GetHeadMovingQuery(Query[Result]):
    """Get head motion status."""
    pass


@dataclass
class GetArmJointAnglesQuery(Query[Result]):
    """Get arm joint angles."""
    arm: str = "right"


@dataclass
class GetTracksVelocityQuery(Query[Result]):
    """Get track velocities (left, right)."""
    pass


@dataclass
class GetCollisionStatusQuery(Query[Result]):
    """Get collision sensor status."""
    pass


@dataclass
class GetSpeakingStatusQuery(Query[Result]):
    """Get TTS speaking status."""
    pass


@dataclass
class GetListeningStatusQuery(Query[Result]):
    """Get STT listening status."""
    pass


@dataclass
class GetCurrentBehaviorQuery(Query[Result]):
    """Get currently active behavior."""
    pass


@dataclass
class GetEmotionalStateQuery(Query[Result]):
    """Get emotional state."""
    pass


@dataclass
class GetFaceDetectionsQuery(Query[Result]):
    """Get latest face detections."""
    pass


@dataclass
class GetFaceRecognitionsQuery(Query[Result]):
    """Get latest face recognitions."""
    pass


@dataclass
class GetObjectDetectionsQuery(Query[Result]):
    """Get latest object detections."""
    classes: Optional[list[str]] = None


@dataclass
class GetSegmentationQuery(Query[Result]):
    """Get scene segmentation mask."""
    pass


@dataclass
class GetObjectPoseQuery(Query[Result]):
    """Get 6D pose of a detected object."""
    object_id: str = ""


@dataclass
class GetEntityTrackingQuery(Query[Result]):
    """Get tracked entities."""
    entity_type: str = ""


@dataclass
class GetBatteryVoltageQuery(Query[Result]):
    """Get battery voltage."""
    pass


@dataclass
class GetBatteryCurrentQuery(Query[Result]):
    """Get battery current."""
    pass


@dataclass
class GetBatteryPercentageQuery(Query[Result]):
    """Get battery charge percentage."""
    pass


@dataclass
class GetBatteryTemperatureQuery(Query[Result]):
    """Get battery temperature."""
    pass


@dataclass
class GetBatteryTimeRemainingQuery(Query[Result]):
    """Get estimated battery time remaining."""
    pass


@dataclass
class GetBatteryChargingQuery(Query[Result]):
    """Get charging status."""
    pass


@dataclass
class GetBatteryHealthQuery(Query[Result]):
    """Get battery health metrics."""
    pass


@dataclass
class GetTemperaturesQuery(Query[Result]):
    """Get all temperature readings."""
    pass


@dataclass
class GetCPUUsageQuery(Query[Result]):
    """Get CPU usage statistics."""
    pass


@dataclass
class GetMemoryUsageQuery(Query[Result]):
    """Get memory usage statistics."""
    pass


@dataclass
class GetFirmwareVersionsQuery(Query[Result]):
    """Get firmware versions across nodes."""
    node_id: str = ""


# === HANDLERS ===

class CommandHandler(ABC):
    """Handler for a specific command type (registered on CommandBus)."""

    @abstractmethod
    async def handle(self, command: Command) -> Result:
        """Process the command."""


class QueryHandler(ABC):
    """Handler for a specific query type (registered on QueryBus)."""

    @abstractmethod
    async def handle(self, query: Query) -> Result:
        """Process the query."""


# === COMMAND/QUERY BUS ===

class CommandBus:
    """Command dispatcher."""

    def __init__(self):
        self._handlers: dict[type[Command], Any] = {}

    def register(self, command_type: type[Command], handler: Any):
        self._handlers[command_type] = handler

    async def dispatch(self, command: Command) -> Result:
        handler = self._handlers.get(type(command))
        if not handler:
            return Result.fail("NO_HANDLER", f"No handler for {type(command).__name__}")

        try:
            result = await handler.handle(command)
            return result if isinstance(result, Result) else Result.ok(result)
        except CommandError as e:
            return Result.fail(e.code, e.message, e.details)
        except Exception as e:
            return Result.fail("HANDLER_ERROR", str(e))


class QueryBus:
    """Query dispatcher."""

    def __init__(self):
        self._handlers: dict[type[Query], Any] = {}

    def register(self, query_type: type[Query], handler: Any):
        self._handlers[query_type] = handler

    async def dispatch(self, query: Query) -> Result:
        handler = self._handlers.get(type(query))
        if not handler:
            return Result.fail("NO_HANDLER", f"No handler for {type(query).__name__}")

        try:
            result = await handler.handle(query)
            return result if isinstance(result, Result) else Result.ok(result)
        except CommandError as e:
            return Result.fail(e.code, e.message, e.details)
        except Exception as e:
            return Result.fail("HANDLER_ERROR", str(e))