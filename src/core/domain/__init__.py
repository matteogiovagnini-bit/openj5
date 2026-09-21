"""
OpenJ5 Core Domain - Package Exports
"""
from .value_objects import (
    Angle, AngleUnit,
    Position3D, Quaternion, Pose3D, Twist,
    JointAngles, ServoConfig, MotorConfig, PIDConfig,
    StepperConfig, BalanceConfig,
    CalibrationData,
    BatteryState, BatteryHealth,
    TemperatureReading, DistanceReading, IMUReading, Odometry,
    NodeIdentity, NodeType, NodeState, NodeHealth, RobotState,
)

from .events import (
    DomainEvent, EventCategory,
    # Commands
    MoveHeadCommandEvent, MoveArmCommandEvent, MoveTracksCommandEvent,
    SayTextCommandEvent, BehaviorCommandEvent, EmergencyStopCommandEvent,
    BodyCommandEvent,
    # Telemetry
    ServoTelemetryEvent, MotorTelemetryEvent, BatteryTelemetryEvent,
    IMUTelemetryEvent, DistanceTelemetryEvent, OdometryTelemetryEvent,
    BodyTelemetryEvent,
    # State
    NodeStateChangedEvent, RobotStateChangedEvent, PluginStateChangedEvent,
    BalanceStateChangedEvent,
    # Errors
    HardwareFaultEvent, CommunicationLostEvent, SafetyViolationEvent,
    # Business
    FaceDetectedEvent, FaceRecognizedEvent, ObjectDetectedEvent,
    ObjectGraspedEvent, SpeechRecognizedEvent, PersonFollowedEvent,
    DockingCompleteEvent, OTADeployedEvent,
)

from .commands import (
    Result, CommandError,
    Command, Query,
    CommandBus, QueryBus,
    CommandHandler, QueryHandler,
    # Commands
    MoveHeadCommand, MoveArmCommand, MoveTracksCommand,
    BodyCommand,
    SayTextCommand, SetExpressionCommand, SetLEDCommand,
    BehaviorCommand, EmergencyStopCommand, DeployOTACommand,
    LoadPluginCommand, UnloadPluginCommand,
    # Queries
    GetRobotStateQuery, GetNodeHealthQuery, GetServoPositionQuery,
    GetArmPoseQuery, GetOdometryQuery, GetBatteryStateQuery,
    GetPluginListQuery, GetFirmwareVersionsQuery,
    GetHeadAnglesQuery, GetHeadMovingQuery, GetArmJointAnglesQuery,
    GetTracksVelocityQuery, GetCollisionStatusQuery,
    GetBodyTiltQuery, GetBalanceStateQuery,
    GetSpeakingStatusQuery, GetListeningStatusQuery,
    GetCurrentBehaviorQuery, GetEmotionalStateQuery,
    GetFaceDetectionsQuery, GetFaceRecognitionsQuery,
    GetObjectDetectionsQuery, GetSegmentationQuery, GetObjectPoseQuery,
    GetEntityTrackingQuery, GetBatteryVoltageQuery, GetBatteryCurrentQuery,
    GetBatteryPercentageQuery, GetBatteryTemperatureQuery,
    GetBatteryTimeRemainingQuery, GetBatteryChargingQuery, GetBatteryHealthQuery,
    GetTemperaturesQuery, GetCPUUsageQuery, GetMemoryUsageQuery,
)

from .entities import (
    Entity, Robot, Node, Servo, Motor, Stepper, Plugin, Calibration,
)

from .services import (
    IKinematicsService, KinematicsService,
    IMotionPlanner, MotionPlannerService,
    ISafetyPolicy, SafetyPolicyService,
)

from .repositories import (
    IRobotRepository, INodeRepository, IServoRepository, IMotorRepository,
    IPluginRepository, ICalibrationRepository, IEventStore,
    IConfigRepository, IUnitOfWork, UnitOfWorkConfig,
)

__all__ = [
    # Value Objects
    "Angle", "AngleUnit",
    "Position3D", "Quaternion", "Pose3D", "Twist",
    "JointAngles", "ServoConfig", "MotorConfig", "PIDConfig",
    "StepperConfig", "BalanceConfig",
    "CalibrationData",
    "BatteryState", "BatteryHealth",
    "TemperatureReading", "DistanceReading", "IMUReading", "Odometry",
    "NodeIdentity", "NodeType", "NodeState", "NodeHealth", "RobotState",
    # Events
    "DomainEvent", "EventCategory",
    "MoveHeadCommandEvent", "MoveArmCommandEvent", "MoveTracksCommandEvent",
    "SayTextCommandEvent", "BehaviorCommandEvent", "EmergencyStopCommandEvent",
    "BodyCommandEvent",
    "ServoTelemetryEvent", "MotorTelemetryEvent", "BatteryTelemetryEvent",
    "IMUTelemetryEvent", "DistanceTelemetryEvent", "OdometryTelemetryEvent",
    "BodyTelemetryEvent",
    "NodeStateChangedEvent", "RobotStateChangedEvent", "PluginStateChangedEvent",
    "BalanceStateChangedEvent",
    "HardwareFaultEvent", "CommunicationLostEvent", "SafetyViolationEvent",
    "FaceDetectedEvent", "FaceRecognizedEvent", "ObjectDetectedEvent",
    "ObjectGraspedEvent", "SpeechRecognizedEvent", "PersonFollowedEvent",
    "DockingCompleteEvent", "OTADeployedEvent",
    # Commands/Queries
    "Result", "CommandError",
    "Command", "Query",
    "CommandBus", "QueryBus",
    "CommandHandler", "QueryHandler",
    "MoveHeadCommand", "MoveArmCommand", "MoveTracksCommand",
    "BodyCommand",
    "SayTextCommand", "SetExpressionCommand", "SetLEDCommand",
    "BehaviorCommand", "EmergencyStopCommand", "DeployOTACommand",
    "LoadPluginCommand", "UnloadPluginCommand",
    "GetRobotStateQuery", "GetNodeHealthQuery", "GetServoPositionQuery",
    "GetArmPoseQuery", "GetOdometryQuery", "GetBatteryStateQuery",
    "GetPluginListQuery", "GetFirmwareVersionsQuery",
    "GetHeadAnglesQuery", "GetHeadMovingQuery", "GetArmJointAnglesQuery",
    "GetTracksVelocityQuery", "GetCollisionStatusQuery",
    "GetBodyTiltQuery", "GetBalanceStateQuery",
    "GetSpeakingStatusQuery", "GetListeningStatusQuery",
    "GetCurrentBehaviorQuery", "GetEmotionalStateQuery",
    "GetFaceDetectionsQuery", "GetFaceRecognitionsQuery",
    "GetObjectDetectionsQuery", "GetSegmentationQuery", "GetObjectPoseQuery",
    "GetEntityTrackingQuery", "GetBatteryVoltageQuery", "GetBatteryCurrentQuery",
    "GetBatteryPercentageQuery", "GetBatteryTemperatureQuery",
    "GetBatteryTimeRemainingQuery", "GetBatteryChargingQuery", "GetBatteryHealthQuery",
    "GetTemperaturesQuery", "GetCPUUsageQuery", "GetMemoryUsageQuery",
    # Entities
    "Entity", "Robot", "Node", "Servo", "Motor", "Stepper", "Plugin", "Calibration",
    # Services
    "IKinematicsService", "KinematicsService",
    "IMotionPlanner", "MotionPlannerService",
    "ISafetyPolicy", "SafetyPolicyService",
    # Repositories
    "IRobotRepository", "INodeRepository", "IServoRepository", "IMotorRepository",
    "IPluginRepository", "ICalibrationRepository", "IEventStore",
    "IConfigRepository", "IUnitOfWork", "UnitOfWorkConfig",
]