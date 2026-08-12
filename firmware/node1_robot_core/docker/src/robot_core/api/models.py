"""
OpenJ5 Robot Core - API Models

Pydantic models for REST API request/response schemas.
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class NodeState(str, Enum):
    BOOT = "boot"
    INIT = "init"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    RECOVERY = "recovery"
    SHUTDOWN = "shutdown"
    UNKNOWN = "unknown"


class RobotMode(str, Enum):
    MANUAL = "manual"
    AUTONOMOUS = "autonomous"
    TEACH = "teach"
    RECOVERY = "recovery"
    SAFE = "safe"


class JointCommand(BaseModel):
    joint_id: str
    position: Optional[float] = None
    velocity: Optional[float] = None
    torque: Optional[float] = None


class PoseCommand(BaseModel):
    x: float
    y: float
    z: float
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


class RobotCommand(BaseModel):
    command_id: str = Field(default="", description="Client-generated UUID for idempotency")
    target_node: str = Field(..., description="node1-node6, or 'robot' for aggregate")
    command_type: str = Field(..., description="move_joints, move_pose, stop, home, grip, speak, etc")
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout: float = Field(default=10.0, ge=1.0, le=300.0)


class CommandResponse(BaseModel):
    command_id: str
    status: str  # accepted, queued, rejected, completed, failed
    message: str = ""
    result: Optional[dict] = None


class PluginInfo(BaseModel):
    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    state: str  # loaded, enabled, disabled, error
    dependencies: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)


class PluginAction(BaseModel):
    action: str  # enable, disable, reload, load, unload


class OTAPackage(BaseModel):
    firmware_id: str
    node_id: str
    version: str
    file_url: str
    checksum_sha256: str
    signature: str = ""
    staged_rollout: bool = False
    rollout_percentage: int = 100
    force: bool = False


class OTAStatus(BaseModel):
    firmware_id: str
    node_id: str
    status: str  # pending, downloading, applying, rebooting, success, failed, rollback
    progress: float = 0.0
    error: str = ""


class ConfigUpdate(BaseModel):
    path: str = Field(..., description="Dot-notation config path, e.g. 'node3.joints.shoulder_pitch.max_speed'")
    value: Any
    persist: bool = Field(default=True, description="Save to disk")
    node_id: Optional[str] = None


class ConfigSchema(BaseModel):
    path: str
    schema_type: str  # number, string, boolean, object, array
    description: str = ""
    default: Any = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    enum: list[str] = Field(default_factory=list)
    required: bool = False


class Position(BaseModel):
    x: float
    y: float
    z: float


class Orientation(BaseModel):
    x: float
    y: float
    z: float
    w: float


class Pose(BaseModel):
    position: Position
    orientation: Orientation


class Twist(BaseModel):
    linear: Position
    angular: Position


class JointState(BaseModel):
    joint_id: str
    position: float
    velocity: float = 0.0
    torque: float = 0.0
    temperature: float = 0.0


class NodeInfo(BaseModel):
    node_id: str
    state: str
    firmware_version: str
    uptime: float
    cpu_percent: float
    memory_percent: float
    temperature: float
    joints: list[JointState] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RobotStatus(BaseModel):
    mode: RobotMode
    state: str
    battery: Optional[float] = None
    nodes: dict[str, NodeInfo] = Field(default_factory=dict)
    pose: Optional[Pose] = None
    twist: Optional[Twist] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ScheduleJob(BaseModel):
    job_id: str = ""
    name: str
    cron: str = ""
    interval: Optional[float] = None
    command: RobotCommand
    enabled: bool = True


class ScheduleJobResponse(BaseModel):
    job_id: str
    status: str


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    code: str = "internal_error"
    request_id: str = ""


class EventStream(BaseModel):
    event_type: str
    source_node: str
    payload: dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class RobotControlRequest(BaseModel):
    command: RobotCommand
    wait_for_completion: bool = False


class CalibrationPosition(BaseModel):
    name: str
    joints: dict[str, float]
    description: str = ""


class CalibrationProfile(BaseModel):
    profile_id: str
    name: str
    version: str
    positions: dict[str, CalibrationPosition]
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
