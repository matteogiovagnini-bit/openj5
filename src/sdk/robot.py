"""
OpenJ5 Robot SDK - High-level Facade for Applications

This is the SINGLE public API for all applications.
Applications MUST use only this SDK - never direct MQTT/ROS/serial.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Awaitable
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import uuid

from ..core.domain import (
    Result, CommandBus, QueryBus,
    MoveHeadCommand, MoveArmCommand, MoveTracksCommand,
    SayTextCommand, SetExpressionCommand, SetLEDCommand,
    BehaviorCommand, EmergencyStopCommand, DeployOTACommand,
    GetRobotStateQuery, GetNodeHealthQuery, GetBatteryStateQuery,
    Position3D, Pose3D, JointAngles, BatteryState,
    NodeState, NodeHealth, RobotState,
)


class RobotMode(Enum):
    REAL = "real"      # Physical robot
    SIM = "sim"        # Gazebo/Isaac Sim
    MOCK = "mock"      # Test double


class CommunicationProtocol(Enum):
    MQTT = "mqtt"
    ROS2 = "ros2"
    WEBSOCKET = "websocket"
    SERIAL = "serial"
    BLE = "ble"
    CAN = "can"


@dataclass
class RobotConfig:
    """Robot SDK configuration."""
    node_id: str = "robot_core"
    mode: RobotMode = RobotMode.REAL
    communication: CommunicationProtocol = CommunicationProtocol.MQTT
    mqtt_host: str = "localhost"
    mqtt_port: int = 8883
    mqtt_tls: bool = True
    mqtt_ca_cert: str = "/etc/openj5/certs/ca.crt"
    mqtt_client_cert: str = "/etc/openj5/certs/client.crt"
    mqtt_client_key: str = "/etc/openj5/certs/client.key"
    ros2_domain: int = 42
    websocket_url: str = "wss://localhost:8081"
    timeout: float = 30.0
    auto_connect: bool = True


# === SUBSYSTEM APIS ===

class HeadAPI:
    """Head control API."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def look_at(
        self,
        x: float, y: float, z: float,
        frame: str = "base",
        speed: float = 1.0,
        blocking: bool = True
    ) -> Result:
        """Look at 3D point in space."""
        return await self._cmd.dispatch(MoveHeadCommand(
            target_x=x, target_y=y, target_z=z,
            frame=frame, speed=speed, blocking=blocking
        ))

    async def look_at_entity(self, entity_id: str, speed: float = 1.0) -> Result:
        """Track a detected entity (face, person, object) by ID."""
        return await self._cmd.dispatch(MoveHeadCommand(
            target_entity=entity_id, speed=speed, blocking=True
        ))

    async def home(self, speed: float = 0.5, blocking: bool = True) -> Result:
        """Return to neutral position."""
        return await self._cmd.dispatch(MoveHeadCommand(
            target_x=0, target_y=0, target_z=1.2,
            frame="base", speed=speed, blocking=blocking
        ))

    async def nod(self, count: int = 1, speed: float = 1.0, blocking: bool = True) -> Result:
        """Nod head (yes gesture)."""
        # Implemented as behavior primitive
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="nod", params={"count": count, "speed": speed}, blocking=blocking
        ))

    async def shake(self, count: int = 1, speed: float = 1.0, blocking: bool = True) -> Result:
        """Shake head (no gesture)."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="shake", params={"count": count, "speed": speed}, blocking=blocking
        ))

    async def blink(self, duration: float = 0.15) -> Result:
        """Natural blink."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="blink", params={"duration": duration}, blocking=False
        ))

    async def scan(
        self,
        yaw_range: tuple[float, float] = (-90, 90),
        pitch_range: tuple[float, float] = (-30, 30),
        speed: float = 0.3,
        pattern: str = "raster"
    ) -> Result:
        """Scan environment with head."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="scan", params={
                "yaw_range": yaw_range, "pitch_range": pitch_range,
                "speed": speed, "pattern": pattern
            }, blocking=False
        ))

    async def set_expression(self, expression: str, intensity: float = 1.0, duration: float = 0) -> Result:
        """Set facial expression: neutral, happy, sad, angry, surprised, curious, sleepy, confused, thinking, excited."""
        return await self._cmd.dispatch(SetExpressionCommand(
            expression=expression, intensity=intensity, duration=duration
        ))

    async def smile(self, intensity: float = 1.0) -> Result:
        return await self.set_expression("happy", intensity)

    async def frown(self, intensity: float = 1.0) -> Result:
        return await self.set_expression("sad", intensity)

    async def surprise(self, intensity: float = 1.0) -> Result:
        return await self.set_expression("surprised", intensity)

    async def set_led(self, color: tuple[int, int, int], brightness: float = 1.0, pattern: str = "solid") -> Result:
        """Set head LED strip."""
        return await self._cmd.dispatch(SetLEDCommand(
            node_id="node2", pattern=pattern, color=color, brightness=brightness
        ))

    async def display_image(self, image: bytes, duration: float = 0) -> Result:
        """Show image on head display."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="display_image", params={"image": image, "duration": duration}
        ))

    async def get_angles(self) -> Result[JointAngles]:
        return await self._qry.dispatch(GetHeadAnglesQuery())

    def is_moving(self) -> Result[bool]:
        return self._qry.dispatch(GetHeadMovingQuery())


class ArmAPI:
    """Arm control API (right or left)."""

    def __init__(self, arm: str, command_bus: CommandBus, query_bus: QueryBus):
        self._arm = arm  # "right" | "left"
        self._cmd = command_bus
        self._qry = query_bus

    async def wave(self, speed: float = 1.0, blocking: bool = True) -> Result:
        """Wave gesture."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="wave", params={"arm": self._arm, "speed": speed}, blocking=blocking
        ))

    async def point(self, x: float, y: float, z: float, frame: str = "base", speed: float = 1.0) -> Result:
        """Point at 3D position."""
        return await self._cmd.dispatch(MoveArmCommand(
            arm=self._arm, target_x=x, target_y=y, target_z=z,
            frame=frame, speed=speed, blocking=True
        ))

    async def grab(self, object_size: str = "medium", force: float = 0.5, blocking: bool = True) -> Result:
        """Close gripper to grab object."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="grab", params={"arm": self._arm, "object_size": object_size, "force": force},
            blocking=blocking
        ))

    async def release(self, blocking: bool = True) -> Result:
        """Open gripper fully."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="release", params={"arm": self._arm}, blocking=blocking
        ))

    async def reach(
        self,
        x: float, y: float, z: float,
        orientation: tuple[float, float, float, float] = None,  # quaternion
        frame: str = "base",
        speed: float = 1.0,
        blocking: bool = True
    ) -> Result:
        """Reach to 3D position with optional orientation (IK)."""
        return await self._cmd.dispatch(MoveArmCommand(
            arm=self._arm, target_x=x, target_y=y, target_z=z,
            target_orientation=orientation, frame=frame, speed=speed, blocking=blocking
        ))

    async def home(self, speed: float = 0.5, blocking: bool = True) -> Result:
        """Return to home position."""
        return await self._cmd.dispatch(MoveArmCommand(
            arm=self._arm, target_x=0.3, target_y=0 if self._arm == "right" else 0, target_z=0.5,
            frame="base", speed=speed, blocking=blocking
        ))

    async def retract(self, speed: float = 0.5, blocking: bool = True) -> Result:
        """Retract arm close to body (safe transport)."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="retract", params={"arm": self._arm, "speed": speed}, blocking=blocking
        ))

    async def handover(self, target_x: float, target_y: float, target_z: float, speed: float = 0.5) -> Result:
        """Prepare for object handover at position."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="handover", params={"arm": self._arm, "x": target_x, "y": target_y, "z": target_z},
            blocking=True
        ))

    async def get_pose(self) -> Result[Pose3D]:
        return await self._qry.dispatch(GetArmPoseQuery(arm=self._arm))

    async def get_joint_angles(self) -> Result[JointAngles]:
        return await self._qry.dispatch(GetArmJointAnglesQuery(arm=self._arm))

    async def set_gripper(self, position: float, force: float = 0.5) -> Result:
        """Set gripper position (0.0 = open, 1.0 = closed)."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="set_gripper", params={"arm": self._arm, "position": position, "force": force}
        ))


class TorsoAPI:
    """Torso control API."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def rotate(self, angle: float, speed: float = 1.0, blocking: bool = True) -> Result:
        """Rotate torso yaw (degrees)."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="torso_rotate", params={"angle": angle, "speed": speed}, blocking=blocking
        ))

    async def pitch(self, angle: float, speed: float = 1.0, blocking: bool = True) -> Result:
        """Pitch torso forward/back (degrees)."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="torso_pitch", params={"angle": angle, "speed": speed}, blocking=blocking
        ))

    async def home(self, speed: float = 0.5, blocking: bool = True) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="torso_home", params={"speed": speed}, blocking=blocking
        ))

    async def open_battery_door(self, blocking: bool = True) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="battery_door_open", params={}, blocking=blocking
        ))

    async def close_battery_door(self, blocking: bool = True) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="battery_door_close", params={}, blocking=blocking
        ))

    async def set_led(self, pattern: str, color: tuple[int, int, int] = (255, 255, 255), brightness: float = 0.3) -> Result:
        return await self._cmd.dispatch(SetLEDCommand(
            node_id="node5", pattern=pattern, color=color, brightness=brightness
        ))

    async def set_fan(self, speed: float) -> Result:
        """Set fan speed (0.0 - 1.0)."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="fan_speed", params={"speed": speed}, blocking=False
        ))


class TracksAPI:
    """Differential drive tracks API."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def move_forward(
        self,
        velocity: float,      # m/s (-0.5 to 0.5)
        distance: float = 0.0,  # m (0 = continuous)
        blocking: bool = True
    ) -> Result:
        return await self._cmd.dispatch(MoveTracksCommand(
            linear_velocity=velocity, distance=distance, blocking=blocking
        ))

    async def rotate(
        self,
        angular_velocity: float,  # rad/s (-1.0 to 1.0)
        angle: float = 0.0,       # rad (0 = continuous)
        blocking: bool = True
    ) -> Result:
        return await self._cmd.dispatch(MoveTracksCommand(
            angular_velocity=angular_velocity, angle=angle, blocking=blocking
        ))

    async def move_to(
        self,
        x: float, y: float, theta: float,
        frame: str = "map",
        max_velocity: float = 0.3,
        max_angular: float = 0.5,
        blocking: bool = True
    ) -> Result:
        """Navigate to pose (uses internal planner or Nav2 plugin)."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="navigate_to",
            params={"x": x, "y": y, "theta": theta, "frame": frame,
                   "max_vel": max_velocity, "max_ang": max_angular},
            blocking=blocking
        ))

    async def arc(
        self,
        linear_velocity: float,
        angular_velocity: float,
        duration: float = 0.0,
        blocking: bool = True
    ) -> Result:
        """Move in arc (different wheel velocities)."""
        return await self._cmd.dispatch(MoveTracksCommand(
            linear_velocity=linear_velocity, angular_velocity=angular_velocity,
            blocking=blocking
        ))

    async def stop(self, emergency: bool = False) -> Result:
        """Stop immediately. If emergency=True, uses motor brake."""
        if emergency:
            return await self._cmd.dispatch(EmergencyStopCommand(
                reason="tracks_emergency_stop", scope="tracks"
            ))
        return await self._cmd.dispatch(MoveTracksCommand(
            linear_velocity=0, angular_velocity=0, blocking=True
        ))

    async def dock(self, dock_id: str, blocking: bool = True) -> Result:
        """Autonomous docking to charging station."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="dock", params={"dock_id": dock_id}, blocking=blocking
        ))

    async def follow_path(self, waypoints: list[tuple[float, float, float]], blocking: bool = True) -> Result:
        """Follow list of (x, y, theta) waypoints."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="follow_path", params={"waypoints": waypoints}, blocking=blocking
        ))

    # Teleoperation
    async def set_velocity(self, linear: float, angular: float) -> Result:
        """Direct velocity command (for teleop)."""
        return await self._cmd.dispatch(MoveTracksCommand(
            linear_velocity=linear, angular_velocity=angular, blocking=False
        ))

    async def enable_teleop(self, timeout: float = 5.0) -> Result:
        """Enable teleop mode with watchdog."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="enable_teleop", params={"timeout": timeout}, blocking=False
        ))

    async def disable_teleop(self) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="disable_teleop", params={}, blocking=False
        ))

    async def get_odometry(self) -> Result[Pose3D]:
        return await self._qry.dispatch(GetOdometryQuery())

    async def get_velocity(self) -> Result[tuple[float, float]]:
        return await self._qry.dispatch(GetTracksVelocityQuery())

    async def get_battery(self) -> Result[BatteryState]:
        return await self._qry.dispatch(GetBatteryStateQuery())

    async def get_collision_status(self) -> Result[dict]:
        return await self._qry.dispatch(GetCollisionStatusQuery())


class SpeechAPI:
    """Speech API."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def say(
        self,
        text: str,
        language: str = "it",
        voice: str = "default",
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        blocking: bool = True
    ) -> Result:
        return await self._cmd.dispatch(SayTextCommand(
            text=text, language=language, voice=voice,
            speed=speed, pitch=pitch, volume=volume, blocking=blocking
        ))

    async def listen(
        self,
        timeout: float = 10.0,
        language: str = "it",
        wake_word: str = None
    ) -> Result[str]:
        """Listen for speech and return transcript."""
        # Implemented via BehaviorCommand to Speech plugin
        result = await self._cmd.dispatch(BehaviorCommand(
            behavior="listen", params={"timeout": timeout, "language": language, "wake_word": wake_word},
            blocking=True
        ))
        if result.success:
            return Result.ok(result.data.get("text", ""))
        return Result.fail(result.error_code, result.error_message)

    async def start_listening(self, callback: Callable[[str], Awaitable[None]], wake_word: str = None) -> Result:
        """Start continuous listening with callback."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="start_continuous_listen", params={"wake_word": wake_word}, blocking=False
        ))

    async def stop_listening(self) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="stop_continuous_listen", params={}, blocking=False
        ))

    async def play_audio(self, audio_data: bytes, sample_rate: int = 22050) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="play_audio", params={"audio": audio_data, "sample_rate": sample_rate}
        ))

    def is_speaking(self) -> Result[bool]:
        return self._qry.dispatch(GetSpeakingStatusQuery())

    def is_listening(self) -> Result[bool]:
        return self._qry.dispatch(GetListeningStatusQuery())


class BehaviorAPI:
    """High-level behavior API."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def idle(self) -> Result:
        """Enter idle behavior (breathing, random look, blink)."""
        return await self._cmd.dispatch(BehaviorCommand(behavior="idle", params={}, blocking=False))

    async def sleep(self) -> Result:
        """Sleep mode (head down, eyes closed, low power)."""
        return await self._cmd.dispatch(BehaviorCommand(behavior="sleep", params={}, blocking=False))

    async def wake_up(self) -> Result:
        """Wake from sleep (stretch, look around, greet)."""
        return await self._cmd.dispatch(BehaviorCommand(behavior="wake_up", params={}, blocking=True))

    async def follow_person(self, person_id: str, distance: float = 1.0) -> Result:
        """Follow a detected person maintaining distance."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="follow_person", params={"person_id": person_id, "distance": distance}, blocking=False
        ))

    async def greet(self, person_id: str = None) -> Result:
        """Greeting behavior."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="greet", params={"person_id": person_id}, blocking=True
        ))

    async def dance(self, style: str = "happy") -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="dance", params={"style": style}, blocking=False
        ))

    async def show_emotion(self, emotion: str, intensity: float = 1.0) -> Result:
        """Express emotion: neutral, happy, sad, angry, fear, surprise, disgust, curiosity, confusion, excitement, boredom, affection."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="show_emotion", params={"emotion": emotion, "intensity": intensity}, blocking=False
        ))

    async def attend_to(self, target: str | tuple[float, float, float]) -> Result:
        """Focus attention on target (entity ID or 3D position)."""
        if isinstance(target, str):
            params = {"entity_id": target}
        else:
            params = {"x": target[0], "y": target[1], "z": target[2]}
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="attend", params=params, blocking=False
        ))

    async def ignore(self, target: str | tuple[float, float, float]) -> Result:
        """Ignore target."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="ignore", params={"target": target}, blocking=False
        ))

    async def get_current_behavior(self) -> Result[str]:
        return await self._qry.dispatch(GetCurrentBehaviorQuery())

    async def get_emotional_state(self) -> Result[dict]:
        return await self._qry.dispatch(GetEmotionalStateQuery())


class VisionAPI:
    """Vision API (requires VisionPlugin)."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def detect_faces(self) -> Result[list]:
        return await self._qry.dispatch(GetFaceDetectionsQuery())

    async def recognize_faces(self) -> Result[list]:
        return await self._qry.dispatch(GetFaceRecognitionsQuery())

    async def detect_objects(self, classes: list[str] = None) -> Result[list]:
        return await self._qry.dispatch(GetObjectDetectionsQuery(classes=classes))

    async def segment_scene(self) -> Result[bytes]:
        return await self._qry.dispatch(GetSegmentationQuery())

    async def estimate_pose(self, object_id: str) -> Result[Pose3D]:
        return await self._qry.dispatch(GetObjectPoseQuery(object_id=object_id))

    async def track_entity(self, entity_id: str) -> Result[dict]:
        return await self._qry.dispatch(GetEntityTrackingQuery(entity_id=entity_id))

    async def enable_detector(self, detector: str) -> Result:
        """Enable detector: face, yolo, mediapipe, etc."""
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="enable_detector", params={"detector": detector}
        ))

    async def disable_detector(self, detector: str) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="disable_detector", params={"detector": detector}
        ))


class BatteryAPI:
    """Battery monitoring API."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def get_voltage(self) -> Result[float]:
        return await self._qry.dispatch(GetBatteryVoltageQuery())

    async def get_current(self) -> Result[float]:
        return await self._qry.dispatch(GetBatteryCurrentQuery())

    async def get_percentage(self) -> Result[float]:
        return await self._qry.dispatch(GetBatteryPercentageQuery())

    async def get_temperature(self) -> Result[float]:
        return await self._qry.dispatch(GetBatteryTemperatureQuery())

    async def get_time_remaining(self) -> Result[float]:
        return await self._qry.dispatch(GetBatteryTimeRemainingQuery())

    async def is_charging(self) -> Result[bool]:
        return await self._qry.dispatch(GetBatteryChargingQuery())

    async def get_health(self) -> Result[str]:
        return await self._qry.dispatch(GetBatteryHealthQuery())

    async def on_low_battery(self, threshold: float, callback: Callable[[float], Awaitable[None]]) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="register_low_battery_callback", params={"threshold": threshold, "callback": callback}
        ))

    async def on_critical_battery(self, callback: Callable[[], Awaitable[None]]) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="register_critical_battery_callback", params={"callback": callback}
        ))


class SystemAPI:
    """System-level API."""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self._cmd = command_bus
        self._qry = query_bus

    async def get_state(self) -> Result[RobotState]:
        return await self._qry.dispatch(GetRobotStateQuery())

    async def get_node_health(self) -> Result[dict[str, NodeHealth]]:
        return await self._qry.dispatch(GetNodeHealthQuery())

    async def get_temperatures(self) -> Result[dict[str, float]]:
        return await self._qry.dispatch(GetTemperaturesQuery())

    async def get_cpu_usage(self) -> Result[float]:
        return await self._qry.dispatch(GetCPUUsageQuery())

    async def get_memory_usage(self) -> Result[float]:
        return await self._qry.dispatch(GetMemoryUsageQuery())

    async def reboot_node(self, node_id: int) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="reboot_node", params={"node_id": node_id}
        ))

    async def shutdown_node(self, node_id: int) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(
            behavior="shutdown_node", params={"node_id": node_id}
        ))

    async def emergency_stop(self) -> Result:
        return await self._cmd.dispatch(EmergencyStopCommand(reason="system_emergency_stop"))

    async def clear_emergency_stop(self) -> Result:
        return await self._cmd.dispatch(BehaviorCommand(behavior="clear_emergency_stop"))

    async def trigger_ota_update(self, node_id: int, firmware_url: str) -> Result:
        return await self._cmd.dispatch(DeployOTACommand(
            target_nodes=[f"node{node_id}"], firmware_url=firmware_url
        ))

    async def get_firmware_versions(self) -> Result[dict[str, str]]:
        return await self._qry.dispatch(GetFirmwareVersionsQuery())


# === MAIN ROBOT CLASS ===

class Robot:
    """
    Main Robot SDK entry point.
    
    Usage:
        robot = Robot()  # Auto-connects to real robot
        await robot.connect()
        
        robot.head.look_at(1.0, 0.0, 1.2)
        robot.right_arm.wave()
        robot.tracks.move_forward(0.3)
        robot.speech.say("Ciao!")
        robot.behavior.idle()
        
        await robot.disconnect()
    """

    def __init__(
        self,
        config: RobotConfig = None,
        command_bus: CommandBus = None,
        query_bus: QueryBus = None
    ):
        self._config = config or RobotConfig()
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._connected = False
        self._connection_task = None

        # Lazy-initialized subsystem APIs
        self._head: HeadAPI = None
        self._right_arm: ArmAPI = None
        self._left_arm: ArmAPI = None
        self._torso: TorsoAPI = None
        self._tracks: TracksAPI = None
        self._speech: SpeechAPI = None
        self._behavior: BehaviorAPI = None
        self._vision: VisionAPI = None
        self._battery: BatteryAPI = None
        self._system: SystemAPI = None

    @classmethod
    def from_config(cls, config_path: str) -> Robot:
        """Create robot from config file."""
        # TODO: Load from JSON/YAML
        return cls()

    @property
    def head(self) -> HeadAPI:
        if self._head is None:
            self._head = HeadAPI(self._command_bus, self._query_bus)
        return self._head

    @property
    def right_arm(self) -> ArmAPI:
        if self._right_arm is None:
            self._right_arm = ArmAPI("right", self._command_bus, self._query_bus)
        return self._right_arm

    @property
    def left_arm(self) -> ArmAPI:
        if self._left_arm is None:
            self._left_arm = ArmAPI("left", self._command_bus, self._query_bus)
        return self._left_arm

    @property
    def torso(self) -> TorsoAPI:
        if self._torso is None:
            self._torso = TorsoAPI(self._command_bus, self._query_bus)
        return self._torso

    @property
    def tracks(self) -> TracksAPI:
        if self._tracks is None:
            self._tracks = TracksAPI(self._command_bus, self._query_bus)
        return self._tracks

    @property
    def speech(self) -> SpeechAPI:
        if self._speech is None:
            self._speech = SpeechAPI(self._command_bus, self._query_bus)
        return self._speech

    @property
    def behavior(self) -> BehaviorAPI:
        if self._behavior is None:
            self._behavior = BehaviorAPI(self._command_bus, self._query_bus)
        return self._behavior

    @property
    def vision(self) -> VisionAPI:
        if self._vision is None:
            self._vision = VisionAPI(self._command_bus, self._query_bus)
        return self._vision

    @property
    def battery(self) -> BatteryAPI:
        if self._battery is None:
            self._battery = BatteryAPI(self._command_bus, self._query_bus)
        return self._battery

    @property
    def system(self) -> SystemAPI:
        if self._system is None:
            self._system = SystemAPI(self._command_bus, self._query_bus)
        return self._system

    async def connect(self) -> Result:
        """Connect to robot (initializes command/query buses)."""
        if self._connected:
            return Result.ok(True)

        # TODO: Initialize actual command/query buses based on config
        # For now, use in-memory buses
        self._command_bus = CommandBus()
        self._query_bus = QueryBus()

        # Register default handlers (would be done by Robot Core service)
        # self._register_default_handlers()

        self._connected = True
        return Result.ok(True)

    async def disconnect(self) -> Result:
        """Disconnect from robot."""
        self._connected = False
        self._command_bus = None
        self._query_bus = None
        return Result.ok(True)

    def is_connected(self) -> bool:
        return self._connected

    async def health_check(self) -> Result[RobotState]:
        """Full robot health check."""
        return await self.system.get_state()

    async def __aenter__(self) -> Robot:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# === SYNC WRAPPER (for simple scripts) ===

class SyncRobot:
    """Synchronous wrapper for Robot SDK."""

    def __init__(self, config: RobotConfig = None):
        self._robot = Robot(config)
        self._loop = None

    def __enter__(self) -> SyncRobot:
        import asyncio
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._robot.connect())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._loop.run_until_complete(self._robot.disconnect())

    @property
    def head(self) -> HeadAPI:
        return self._robot.head

    @property
    def right_arm(self) -> ArmAPI:
        return self._robot.right_arm

    @property
    def left_arm(self) -> ArmAPI:
        return self._robot.left_arm

    @property
    def torso(self) -> TorsoAPI:
        return self._robot.torso

    @property
    def tracks(self) -> TracksAPI:
        return self._robot.tracks

    @property
    def speech(self) -> SpeechAPI:
        return self._robot.speech

    @property
    def behavior(self) -> BehaviorAPI:
        return self._robot.behavior

    @property
    def vision(self) -> VisionAPI:
        return self._robot.vision

    @property
    def battery(self) -> BatteryAPI:
        return self._robot.battery

    @property
    def system(self) -> SystemAPI:
        return self._robot.system


# === CONVENIENCE FUNCTIONS ===

def create_robot(
    mode: RobotMode = RobotMode.REAL,
    protocol: CommunicationProtocol = CommunicationProtocol.MQTT,
    **kwargs
) -> Robot:
    """Factory function to create robot with common config."""
    config = RobotConfig(mode=mode, communication=protocol, **kwargs)
    return Robot(config)


# For backwards compatibility
RobotSDK = Robot