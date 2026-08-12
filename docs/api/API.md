# OpenJ5 Robot SDK API Reference

## Overview

The **Robot SDK** is the **single facade** for all applications. Applications MUST use only these high-level APIs. Direct MQTT topic publishing, ROS 2 topic publishing, or servo angle commands are **FORBIDDEN** in application code.

```python
from openj5 import Robot

robot = Robot()

# High-level commands - NO MQTT, NO SERVO ANGLES
robot.head.look_at(x=1.0, y=0.5, z=1.2)
robot.right_arm.wave()
robot.left_arm.grab()
robot.tracks.move_forward(velocity=0.3)
robot.speech.say("Hello, I am OpenJ5!")
robot.behavior.idle()
```

---

## Installation

```bash
# Python
pip install openj5-sdk

# C++ (via CMake)
find_package(OpenJ5SDK REQUIRED)
target_link_libraries(my_app PRIVATE OpenJ5::SDK)

# TypeScript/Node.js
npm install @openj5/sdk
```

---

## Core Classes

### `Robot` - Main Entry Point

```python
class Robot:
    def __init__(
        self,
        config: Optional[RobotConfig] = None,
        mode: Literal["real", "sim", "mock"] = "real",
        communication: Literal["mqtt", "ros2", "websocket"] = "mqtt"
    ):
        """
        Create robot instance.

        Args:
            config: Configuration object (loads from default locations if None)
            mode: "real" = physical robot, "sim" = Gazebo/Isaac Sim, "mock" = test double
            communication: Transport protocol (abstracted by CommunicationGateway)
        """

    # Subsystem facades (lazy-loaded)
    @property
    def head(self) -> HeadAPI: ...
    @property
    def right_arm(self) -> ArmAPI: ...
    @property
    def left_arm(self) -> ArmAPI: ...
    @property
    def torso(self) -> TorsoAPI: ...
    @property
    def tracks(self) -> TracksAPI: ...
    @property
    def speech(self) -> SpeechAPI: ...
    @property
    def behavior(self) -> BehaviorAPI: ...
    @property
    def vision(self) -> VisionAPI: ...
    @property
    def battery(self) -> BatteryAPI: ...
    @property
    def system(self) -> SystemAPI: ...

    # Lifecycle
    def connect(self) -> Result: ...
    def disconnect(self) -> Result: ...
    def is_connected(self) -> bool: ...

    # Health & Diagnostics
    def health_check(self) -> HealthStatus: ...
    def get_diagnostics(self) -> Diagnostics: ...
```

### `RobotConfig` - Configuration

```python
@dataclass
class RobotConfig:
    node_id: str = "robot_core"
    communication: CommunicationConfig = field(default_factory=CommunicationConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

@dataclass
class CommunicationConfig:
    protocol: Literal["mqtt", "ros2", "websocket", "serial", "ble", "can"] = "mqtt"
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    ros2: ROS2Config = field(default_factory=ROS2Config)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)

@dataclass
class MQTTConfig:
    host: str = "localhost"
    port: int = 8883
    use_tls: bool = True
    ca_cert: str = "/etc/openj5/certs/ca.crt"
    client_cert: str = "/etc/openj5/certs/client.crt"
    client_key: str = "/etc/openj5/certs/client.key"
    username: Optional[str] = None
    password: Optional[str] = None
    keepalive: int = 60
    topic_prefix: str = "openj5/v1"

@dataclass
class SafetyConfig:
    emergency_stop_topic: str = "openj5/v1/system/emergency_stop"
    max_joint_velocity: Dict[str, float] = field(default_factory=dict)
    collision_threshold: float = 0.5  # meters
    battery_critical_voltage: float = 10.5  # V
```

---

## Head API (`robot.head`)

```python
class HeadAPI:
    """Head control: Neck (Yaw/Pitch/Roll), Eyes (Horizontal/Vertical), Eyelids"""

    # === Movement Primitives ===
    def look_at(
        self,
        x: float, y: float, z: float,
        frame: Literal["base", "head", "camera"] = "base",
        speed: float = 1.0,      # 0.0 - 1.0
        blocking: bool = True,
        timeout: float = 5.0
    ) -> Result:
        """Look at a 3D point in space. Uses IK to compute neck+eye angles."""

    def look_at_entity(self, entity_id: str, speed: float = 1.0) -> Result:
        """Track a detected entity (face, person, object) by ID."""

    def home(self, speed: float = 0.5, blocking: bool = True) -> Result:
        """Return to neutral home position."""

    def nod(self, count: int = 1, speed: float = 1.0, blocking: bool = True) -> Result:
        """Nod head up/down (yes gesture)."""

    def shake(self, count: int = 1, speed: float = 1.0, blocking: bool = True) -> Result:
        """Shake head left/right (no gesture)."""

    def blink(self, duration: float = 0.15, blocking: bool = False) -> Result:
        """Close and open eyelids (natural blink)."""

    def scan(
        self,
        yaw_range: Tuple[float, float] = (-90, 90),
        pitch_range: Tuple[float, float] = (-30, 30),
        speed: float = 0.3,
        pattern: Literal["raster", "spiral", "random"] = "raster"
    ) -> Result:
        """Scan environment with head movement."""

    # === Direct Control (Advanced) ===
    def set_neck_angles(
        self,
        yaw: float, pitch: float, roll: float,
        speed: float = 1.0
    ) -> Result:
        """Set neck joint angles directly (degrees). Use look_at() instead."""

    def set_eye_angles(
        self,
        horizontal: float, vertical: float,
        speed: float = 1.0
    ) -> Result:
        """Set eye angles directly (degrees)."""

    def set_eyelid_position(self, position: float, speed: float = 1.0) -> Result:
        """Set eyelid position (0.0 = open, 1.0 = closed)."""

    # === Expressions ===
    def set_expression(self, expression: Expression) -> Result:
        """Set predefined facial expression."""

    def smile(self, intensity: float = 1.0) -> Result: ...
    def frown(self, intensity: float = 1.0) -> Result: ...
    def surprise(self, intensity: float = 1.0) -> Result: ...
    def angry(self, intensity: float = 1.0) -> Result: ...
    def sad(self, intensity: float = 1.0) -> Result: ...
    def neutral(self) -> Result: ...

    # === LED/Display ===
    def set_led_color(self, color: RGB, brightness: float = 1.0) -> Result:
        """Set head LED strip color."""

    def set_led_pattern(self, pattern: LEDPattern) -> Result:
        """Set LED animation pattern."""

    def display_image(self, image: ImageData, duration: float = 0) -> Result:
        """Show image on head display (OLED/TFT)."""

    def display_text(self, text: str, font_size: int = 16, color: RGB = WHITE) -> Result: ...

    # === State Queries ===
    def get_neck_angles(self) -> NeckAngles: ...
    def get_eye_angles(self) -> EyeAngles: ...
    def get_eyelid_position(self) -> float: ...
    def is_moving(self) -> bool: ...
```

### `Expression` Enum

```python
class Expression(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    CURIOUS = "curious"
    SLEEPY = "sleepy"
    CONFUSED = "confused"
    THINKING = "thinking"
    EXCITED = "excited"
```

---

## Arm API (`robot.right_arm`, `robot.left_arm`)

```python
class ArmAPI:
    """Arm control: Shoulder (Pitch/Roll/Rotation), Elbow, Wrist, Gripper"""

    # === Movement Primitives ===
    def wave(
        self,
        hand: Literal["right", "left"] = "auto",
        speed: float = 1.0,
        blocking: bool = True
    ) -> Result:
        """Wave gesture."""

    def point(
        self,
        x: float, y: float, z: float,
        frame: Literal["base", "torso", "shoulder"] = "base",
        speed: float = 1.0,
        blocking: bool = True
    ) -> Result:
        """Point at a 3D position."""

    def grab(
        self,
        object_size: Literal["small", "medium", "large"] = "medium",
        force: float = 0.5,  # 0.0 - 1.0
        blocking: bool = True
    ) -> Result:
        """Close gripper to grab object."""

    def release(self, blocking: bool = True) -> Result:
        """Open gripper fully."""

    def reach(
        self,
        x: float, y: float, z: float,
        orientation: Optional[Quaternion] = None,
        frame: Literal["base", "torso", "shoulder"] = "base",
        speed: float = 1.0,
        blocking: bool = True
    ) -> Result:
        """Reach to a 3D position with optional orientation (IK)."""

    def home(self, speed: float = 0.5, blocking: bool = True) -> Result:
        """Return to home/rest position."""

    def retract(self, speed: float = 0.5, blocking: bool = True) -> Result:
        """Retract arm close to body (safe transport position)."""

    def handover(
        self,
        target_position: Tuple[float, float, float],
        speed: float = 0.5,
        blocking: bool = True
    ) -> Result:
        """Prepare for object handover at position."""

    # === Direct Joint Control (Advanced) ===
    def set_joint_angles(
        self,
        angles: JointAngles,  # shoulder_pitch, shoulder_roll, shoulder_rot, elbow, wrist, gripper
        speed: float = 1.0
    ) -> Result: ...

    def set_gripper_position(self, position: float, force: float = 0.5) -> Result:
        """Set gripper position (0.0 = open, 1.0 = closed)."""

    # === State Queries ===
    def get_joint_angles(self) -> JointAngles: ...
    def get_gripper_position(self) -> float: ...
    def get_end_effector_pose(self) -> Pose: ...
    def is_moving(self) -> bool: ...
    def get_force_torque(self) -> Optional[ForceTorque]: ...  # If force sensor equipped
```

### `JointAngles` Dataclass

```python
@dataclass
class JointAngles:
    shoulder_pitch: float   # degrees
    shoulder_roll: float    # degrees
    shoulder_rotation: float  # degrees
    elbow: float            # degrees
    wrist: float            # degrees
    gripper: float          # 0.0 - 1.0
```

---

## Torso API (`robot.torso`)

```python
class TorsoAPI:
    """Torso control: Rotation, Pitch, Battery Door, Expansion"""

    def rotate(self, angle: float, speed: float = 1.0, blocking: bool = True) -> Result:
        """Rotate torso yaw (degrees)."""

    def pitch(self, angle: float, speed: float = 1.0, blocking: bool = True) -> Result:
        """Pitch torso forward/back (degrees)."""

    def home(self, speed: float = 0.5, blocking: bool = True) -> Result:
        """Return to neutral position."""

    def open_battery_door(self, blocking: bool = True) -> Result: ...
    def close_battery_door(self, blocking: bool = True) -> Result: ...

    def set_expansion_servo(self, channel: int, angle: float, speed: float = 1.0) -> Result:
        """Control expansion servo (channel 3 on PCA9685)."""

    def set_led_pattern(self, pattern: LEDPattern) -> Result: ...
    def set_fan_speed(self, speed: float) -> Result: ...  # 0.0 - 1.0

    def get_rotation_angle(self) -> float: ...
    def get_pitch_angle(self) -> float: ...
    def is_battery_door_open(self) -> bool: ...
    def is_moving(self) -> bool: ...
```

---

## Tracks API (`robot.tracks`)

```python
class TracksAPI:
    """Differential drive tracks: Move, Rotate, Navigate"""

    # === Motion Primitives ===
    def move_forward(
        self,
        velocity: float,          # m/s (-0.5 to 0.5)
        distance: float = 0.0,    # meters (0 = continuous)
        blocking: bool = True
    ) -> Result:
        """Move forward/backward at velocity."""

    def rotate(
        self,
        angular_velocity: float,  # rad/s (-1.0 to 1.0)
        angle: float = 0.0,       # radians (0 = continuous)
        blocking: bool = True
    ) -> Result:
        """Rotate in place."""

    def move_to(
        self,
        x: float, y: float, theta: float,
        frame: Literal["map", "odom", "base"] = "map",
        max_velocity: float = 0.3,
        max_angular: float = 0.5,
        blocking: bool = True
    ) -> Result:
        """Navigate to pose (uses internal planner or Nav2 plugin)."""

    def arc(
        self,
        linear_velocity: float,
        angular_velocity: float,
        duration: float = 0.0,    # 0 = continuous
        blocking: bool = True
    ) -> Result:
        """Move in an arc (different wheel velocities)."""

    def stop(self, emergency: bool = False) -> Result:
        """Stop immediately. If emergency=True, uses motor brake."""

    def dock(self, dock_id: str, blocking: bool = True) -> Result:
        """Autonomous docking to charging station."""

    def follow_path(self, path: List[Pose], blocking: bool = True) -> Result:
        """Follow a sequence of poses."""

    # === Teleoperation ===
    def set_velocity(self, linear: float, angular: float) -> Result:
        """Direct velocity command (for teleop)."""

    def enable_teleop(self, timeout: float = 5.0) -> Result:
        """Enable teleop mode with watchdog."""

    def disable_teleop(self) -> Result: ...

    # === State Queries ===
    def get_odometry(self) -> Odometry: ...
    def get_velocity(self) -> Twist: ...
    def get_battery_voltage(self) -> float: ...  # From Node 5
    def is_moving(self) -> bool: ...
    def get_collision_status(self) -> CollisionStatus: ...
```

### `Odometry` Dataclass

```python
@dataclass
class Odometry:
    pose: Pose          # x, y, theta in map/odom frame
    twist: Twist        # linear.x, angular.z
    covariance: List[float]  # 6x6 matrix
    timestamp: float    # Unix timestamp
```

---

## Speech API (`robot.speech`)

```python
class SpeechAPI:
    """Text-to-Speech and Speech-to-Text"""

    # === TTS ===
    def say(
        self,
        text: str,
        language: str = "it",
        voice: str = "default",
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        blocking: bool = True
    ) -> Result:
        """Speak text."""

    def say_ssml(self, ssml: str, blocking: bool = True) -> Result:
        """Speak using SSML markup."""

    def set_voice(self, voice: str) -> Result: ...
    def set_language(self, language: str) -> Result: ...
    def set_speed(self, speed: float) -> Result: ...
    def set_volume(self, volume: float) -> Result: ...

    # === STT ===
    def listen(
        self,
        timeout: float = 10.0,
        language: str = "it",
        wake_word: Optional[str] = None
    ) -> SpeechResult:
        """Listen for speech and return transcript."""

    def start_continuous_listening(
        self,
        callback: Callable[[SpeechResult], None],
        wake_word: Optional[str] = None
    ) -> Result: ...

    def stop_continuous_listening(self) -> Result: ...

    # === Audio ===
    def play_audio(self, audio_data: bytes, sample_rate: int = 22050) -> Result: ...
    def record_audio(self, duration: float, sample_rate: int = 16000) -> AudioData: ...

    # === State ===
    def is_speaking(self) -> bool: ...
    def is_listening(self) -> bool: ...
```

### `SpeechResult` Dataclass

```python
@dataclass
class SpeechResult:
    text: str
    confidence: float
    language: str
    duration: float
    wake_word_detected: bool
    alternatives: List[str]
```

---

## Behavior API (`robot.behavior`)

```python
class BehaviorAPI:
    """High-level behaviors and emotional states"""

    def idle(self) -> Result:
        """Enter idle behavior (breathing, random look, blink)."""

    def sleep(self) -> Result:
        """Enter sleep mode (head down, eyes closed, low power)."""

    def wake_up(self) -> Result:
        """Wake from sleep (stretch, look around, greet)."""

    def follow_person(self, person_id: str, distance: float = 1.0) -> Result:
        """Follow a detected person maintaining distance."""

    def greet(self, person_id: Optional[str] = None) -> Result:
        """Greeting behavior (wave, look at person, say hello)."""

    def dance(self, style: Literal["happy", "excited", "calm"] = "happy") -> Result: ...

    def show_emotion(self, emotion: Emotion, intensity: float = 1.0) -> Result:
        """Express emotion via face, head, arms, voice."""

    def attend_to(self, target: Union[str, Tuple[float, float, float]]) -> Result:
        """Focus attention on target (entity ID or 3D position)."""

    def ignore(self, target: Union[str, Tuple[float, float, float]]) -> Result: ...

    def set_personality(self, personality: Personality) -> Result: ...

    def get_current_behavior(self) -> BehaviorState: ...
    def get_emotional_state(self) -> EmotionalState: ...
```

### `Emotion` Enum

```python
class Emotion(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    CURIOSITY = "curiosity"
    CONFUSION = "confusion"
    EXCITEMENT = "excitement"
    BOREDOM = "boredom"
    AFFECTION = "affection"
```

---

## Vision API (`robot.vision`) - Plugin

```python
class VisionAPI:
    """Computer Vision (requires VisionPlugin)"""

    def detect_faces(self) -> List[FaceDetection]: ...
    def recognize_faces(self) -> List[FaceRecognition]: ...
    def detect_objects(self, classes: Optional[List[str]] = None) -> List[ObjectDetection]: ...
    def segment_scene(self) -> SegmentationMap: ...
    def estimate_pose(self, object_id: str) -> Optional[Pose]: ...
    def track_entity(self, entity_id: str) -> TrackingResult: ...

    def enable_detection(self, detector: str) -> Result: ...  # "face", "yolo", "mediapipe"
    def disable_detection(self, detector: str) -> Result: ...

    def get_camera_image(self) -> ImageData: ...
    def get_depth_map(self) -> DepthMap: ...
```

---

## Battery API (`robot.battery`)

```python
class BatteryAPI:
    """Battery monitoring (from Node 5 Torso Controller)"""

    def get_voltage(self) -> float: ...
    def get_current(self) -> float: ...        # Amps (+ charging, - discharging)
    def get_percentage(self) -> float: ...     # 0.0 - 100.0
    def get_temperature(self) -> float: ...    # Celsius
    def get_time_remaining(self) -> float: ... # Minutes estimated
    def is_charging(self) -> bool: ...
    def get_health(self) -> BatteryHealth: ... # GOOD, DEGRADED, CRITICAL, FAULT

    def register_low_battery_callback(self, threshold: float, callback: Callable) -> Result: ...
    def register_critical_battery_callback(self, callback: Callable) -> Result: ...
```

---

## System API (`robot.system`)

```python
class SystemAPI:
    """System-level control"""

    def get_state(self) -> RobotState: ...  # BOOT, INIT, READY, RUNNING, ERROR, RECOVERY, SHUTDOWN
    def get_node_health(self) -> Dict[str, NodeHealth]: ...
    def get_temperatures(self) -> Dict[str, float]: ...
    def get_cpu_usage(self) -> float: ...
    def get_memory_usage(self) -> float: ...

    def reboot_node(self, node_id: int) -> Result: ...
    def shutdown_node(self, node_id: int) -> Result: ...
    def emergency_stop(self) -> Result: ...
    def clear_emergency_stop(self) -> Result: ...

    def trigger_ota_update(self, node_id: int, firmware_url: str) -> Result: ...
    def get_firmware_versions(self) -> Dict[str, str]: ...

    def save_calibration(self, calibration: CalibrationData) -> Result: ...
    def load_calibration(self, node_id: int) -> CalibrationData: ...
```

---

## Result Type (Error Handling)

```python
@dataclass
class Result:
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    data: Any = None

    def unwrap(self) -> Any:
        if not self.success:
            raise RobotError(self.error_code, self.error_message)
        return self.data

    def __bool__(self) -> bool:
        return self.success

# Usage
result = robot.head.look_at(1.0, 0.0, 1.0)
if not result:
    logger.error(f"Failed: {result.error_message}")
# or
try:
    robot.head.look_at(1.0, 0.0, 1.0).unwrap()
except RobotError as e:
    handle_error(e)
```

---

## Async/Await Support (Python)

```python
import asyncio
from openj5 import Robot

async def main():
    robot = Robot(mode="real")
    await robot.connect_async()

    # Parallel execution
    await asyncio.gather(
        robot.head.look_at_async(1.0, 0.0, 1.0),
        robot.right_arm.wave_async(),
        robot.speech.say_async("Hello!")
    )

    # Sequential with timeout
    try:
        await asyncio.wait_for(
            robot.tracks.move_to_async(2.0, 0.0, 0.0),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        robot.tracks.stop()

    await robot.disconnect_async()

asyncio.run(main())
```

---

## C++ API (Header-Only)

```cpp
#include <openj5/sdk.hpp>

using namespace openj5;

int main() {
    Robot robot(RobotConfig{
        .communication = CommunicationConfig{
            .protocol = Protocol::MQTT,
            .mqtt = MQTTConfig{"localhost", 8883, true}
        }
    });

    auto result = robot.connect();
    if (!result) {
        std::cerr << "Connect failed: " << result.error_message() << std::endl;
        return 1;
    }

    // High-level commands
    robot.head().lookAt(1.0, 0.0, 1.0, 1.0, true);
    robot.rightArm().wave();
    robot.tracks().moveForward(0.3);
    robot.speech().say("Ciao!");

    robot.disconnect();
    return 0;
}
```

---

## TypeScript/JavaScript API

```typescript
import { Robot, RobotConfig, Protocol } from '@openj5/sdk';

const robot = new Robot({
    communication: {
        protocol: Protocol.MQTT,
        mqtt: { host: 'localhost', port: 8883, useTLS: true }
    }
});

await robot.connect();

// Async/await
await robot.head.lookAt(1.0, 0.0, 1.0);
await robot.rightArm.wave();
await robot.tracks.moveForward(0.3);
await robot.speech.say("Hello from TypeScript!");

// Event-based
robot.on('batteryLow', (level) => {
    console.log(`Battery low: ${level}%`);
    robot.behavior.sleep();
});

await robot.disconnect();
```

---

## Simulation Mode (Digital Twin)

```python
# Same API, different mode - ZERO code changes
robot = Robot(mode="sim")  # Connects to Gazebo/Isaac Sim

# Or via config
config = RobotConfig(
    mode="sim",
    simulation=SimulationConfig(
        backend="gazebo",  # or "isaac_sim", "webots", "mujoco"
        host="localhost",
        port=11345
    )
)
robot = Robot(config=config)

# All commands work identically
robot.head.look_at(1.0, 0.0, 1.0)  # Moves simulated robot
robot.tracks.move_forward(0.3)      # Moves simulated tracks
```

---

## Plugin Development (Extend SDK)

```python
# plugins/my_custom_plugin.py
from openj5.sdk import Plugin, PluginMetadata, RobotExtension

@PluginMetadata(
    name="my_custom_arm",
    version="1.0.0",
    description="Custom 7-DOF arm control",
    dependencies=["hardware_plugin"],
    config_schema=MyArmConfigSchema
)
class MyCustomArmPlugin(Plugin):
    def initialize(self, robot: Robot, config: MyArmConfig) -> Result:
        self.robot = robot
        self.arm = MyArmDriver(config)
        # Extend SDK
        robot.extensions["my_arm"] = MyArmAPI(self.arm)
        return Result.success()

    def start(self) -> Result:
        return self.arm.connect()

    def stop(self) -> Result:
        return self.arm.disconnect()

# Register in config/plugins.yaml:
# - name: my_custom_arm
#   path: plugins/my_custom_plugin.py
#   enabled: true
```

---

## Versioning & Compatibility

| SDK Version | Robot Core | Firmware | Protocol |
|-------------|------------|----------|----------|
| 1.0.x       | 1.0.x      | 1.0.x    | v1       |
| 1.1.x       | 1.0.x      | 1.0.x    | v1       |
| 2.0.x       | 2.0.x      | 2.0.x    | v2       |

- **Semantic Versioning** strictly enforced
- **Breaking changes** only in MAJOR version
- **Migration guide** provided for each MAJOR release
- **Deprecation cycle**: 2 minor versions minimum

---

## Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `OK` | 200 | Success |
| `NOT_CONNECTED` | 503 | Robot not connected |
| `NODE_UNREACHABLE` | 503 | Target node not responding |
| `INVALID_COMMAND` | 400 | Command parameters invalid |
| `SAFETY_VIOLATION` | 409 | Command violates safety policy |
| `HARDWARE_FAULT` | 500 | Hardware error (servo, motor, sensor) |
| `COMMUNICATION_ERROR` | 502 | MQTT/Transport error |
| `TIMEOUT` | 504 | Operation timed out |
| `NOT_IMPLEMENTED` | 501 | Feature not available in current mode |
| `CALIBRATION_REQUIRED` | 412 | Node needs calibration |
| `EMERGENCY_STOP_ACTIVE` | 423 | E-stop engaged |
| `FIRMWARE_MISMATCH` | 426 | Firmware version incompatible |