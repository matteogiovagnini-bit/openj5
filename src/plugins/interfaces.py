"""
OpenJ5 Plugin Interfaces - Specific plugin type contracts

Specific plugin categories (vision, speech, AI, ...) extending the base
contracts defined in base.py.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from abc import abstractmethod

from .base import (
    IConfigurablePlugin,
    ILifecyclePlugin,
    IPlugin,
    PluginConfigSchema,
    PluginContext,
    PluginDependency,
    PluginHealth,
    PluginMetadata,
    PluginPermission,
    PluginState,
    PluginType,
    Result,
)

__all__ = [
    "IPlugin",
    "IConfigurablePlugin",
    "ILifecyclePlugin",
    "IVisionPlugin",
    "ISpeechPlugin",
    "IAIPlugin",
    "INavigationPlugin",
    "IBatteryPlugin",
    "IBehaviorPlugin",
    "IHardwarePlugin",
    "ICommunicationPlugin",
    "PluginMetadata",
    "PluginState",
    "PluginType",
    "PluginDependency",
    "PluginPermission",
    "PluginConfigSchema",
    "PluginHealth",
    "PluginContext",
    "FaceDetection",
    "ObjectDetection",
    "SegmentationMap",
    "SpeechResult",
    "WakeWordResult",
    "ChatMessage",
    "Tool",
    "ChatResponse",
    "ClassificationResult",
    "PathPlan",
    "LocalizationResult",
    "MapUpdate",
    "BehaviorResult",
    "BehaviorInfo",
]


# === COMMON DATA TYPES ===

@dataclass
class FaceDetection:
    face_id: str
    bbox: tuple[float, float, float, float]  # x, y, w, h normalized 0-1
    confidence: float
    landmarks: dict[str, tuple[float, float]] = field(default_factory=dict)
    pose_3d: tuple[float, float, float] = None  # x, y, z in meters
    attributes: dict = field(default_factory=dict)  # age, gender, emotion, etc.


@dataclass
class ObjectDetection:
    object_id: str
    class_name: str
    class_id: int
    confidence: float
    bbox: tuple[float, float, float, float]  # x, y, w, h normalized
    pose_3d: tuple[float, float, float] = None
    mask: bytes = None  # binary mask if available


@dataclass
class SegmentationMap:
    """Semantic segmentation result."""
    class_map: list[list[int]]  # 2D array of class IDs
    class_names: dict[int, str]
    width: int
    height: int


@dataclass
class SpeechResult:
    text: str
    confidence: float
    language: str
    wake_word_detected: bool = False
    alternatives: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class WakeWordResult:
    detected: bool
    confidence: float
    wake_word: str = ""


@dataclass
class ChatMessage:
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class ChatResponse:
    message: ChatMessage
    finish_reason: str  # stop, length, tool_calls, error
    usage: dict = field(default_factory=dict)  # prompt_tokens, completion_tokens


@dataclass
class ClassificationResult:
    class_name: str
    confidence: float
    all_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class PathPlan:
    """Navigation path."""
    waypoints: list[tuple[float, float, float]]  # x, y, theta
    total_distance: float
    estimated_time: float
    cost: float


@dataclass
class LocalizationResult:
    """SLAM/Localization result."""
    pose: tuple[float, float, float]  # x, y, theta
    covariance: list[float]
    map_version: int


@dataclass
class MapUpdate:
    """Map update from SLAM."""
    grid_data: bytes  # compressed occupancy grid
    origin: tuple[float, float]
    resolution: float
    width: int
    height: int


@dataclass
class BehaviorResult:
    behavior_id: str
    status: str  # running, completed, failed, interrupted
    result_data: dict = field(default_factory=dict)


@dataclass
class BehaviorInfo:
    behavior_id: str
    name: str
    description: str
    params_schema: dict = field(default_factory=dict)
    required_plugins: list[str] = field(default_factory=list)


# === SPECIFIC PLUGIN INTERFACES ===

class IVisionPlugin(IConfigurablePlugin):
    """Computer vision plugin interface."""

    @abstractmethod
    async def detect_faces(self, image: bytes) -> list[FaceDetection]:
        """Detect faces in image."""
        pass

    @abstractmethod
    async def recognize_faces(self, image: bytes) -> list[FaceDetection]:
        """Detect and recognize known faces."""
        pass

    @abstractmethod
    async def detect_objects(self, image: bytes, classes: list[str] = None) -> list[ObjectDetection]:
        """Detect objects in image."""
        pass

    @abstractmethod
    async def segment_image(self, image: bytes) -> SegmentationMap:
        """Semantic segmentation."""
        pass

    @abstractmethod
    async def estimate_depth(self, image: bytes) -> bytes:
        """Estimate depth map (returns encoded depth image)."""
        pass

    @abstractmethod
    async def track_objects(self, image: bytes) -> dict[str, ObjectDetection]:
        """Track objects across frames."""
        pass


class ISpeechPlugin(IConfigurablePlugin):
    """Speech processing plugin interface."""

    @abstractmethod
    async def transcribe(self, audio: bytes, language: str = "it") -> SpeechResult:
        """Speech-to-text."""
        pass

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default", language: str = "it") -> bytes:
        """Text-to-speech. Returns audio bytes."""
        pass

    @abstractmethod
    async def detect_wake_word(self, audio: bytes) -> WakeWordResult:
        """Detect wake word in audio stream."""
        pass

    @abstractmethod
    async def start_streaming_stt(self, callback: callable) -> Result:
        """Start continuous STT with callback."""
        pass

    @abstractmethod
    async def stop_streaming_stt(self) -> Result:
        """Stop continuous STT."""
        pass


class IAIPlugin(IConfigurablePlugin):
    """AI/LLM plugin interface."""

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], tools: list[Tool] = None) -> ChatResponse:
        """Chat completion with optional tool use."""
        pass

    @abstractmethod
    async def classify(self, text: str, labels: list[str]) -> ClassificationResult:
        """Zero-shot text classification."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings."""
        pass

    @abstractmethod
    async def reason(self, prompt: str, context: dict = None) -> str:
        """Structured reasoning/planning."""
        pass


class INavigationPlugin(IConfigurablePlugin):
    """Navigation/SLAM plugin interface."""

    @abstractmethod
    async def plan_path(self, start: tuple[float, float, float], goal: tuple[float, float, float]) -> PathPlan:
        """Plan path from start to goal (x, y, theta)."""
        pass

    @abstractmethod
    async def localize(self) -> LocalizationResult:
        """Get current robot pose in map."""
        pass

    @abstractmethod
    async def update_map(self, scan: bytes, pose: tuple[float, float, float]) -> MapUpdate:
        """Update map with new scan data."""
        pass

    @abstractmethod
    async def get_map(self) -> bytes:
        """Get current occupancy grid map."""
        pass

    @abstractmethod
    async def set_goal(self, x: float, y: float, theta: float) -> Result:
        """Set navigation goal."""
        pass

    @abstractmethod
    async def cancel_goal(self) -> Result:
        """Cancel current navigation goal."""
        pass


class IBatteryPlugin(IConfigurablePlugin):
    """Battery management plugin."""

    @abstractmethod
    async def get_state(self) -> dict:
        """Get battery state (voltage, current, %, temp, health)."""
        pass

    @abstractmethod
    async def start_charging(self, dock_id: str) -> Result:
        """Initiate autonomous docking for charging."""
        pass

    @abstractmethod
    async def stop_charging(self) -> Result:
        """Stop charging/undock."""
        pass

    @abstractmethod
    async def get_charging_status(self) -> dict:
        """Get charging status (docked, current, time_to_full)."""
        pass

    @abstractmethod
    async def register_low_battery_callback(self, threshold: float, callback: callable) -> Result:
        """Register callback for low battery."""
        pass


class IBehaviorPlugin(IConfigurablePlugin):
    """Behavior engine plugin."""

    @abstractmethod
    async def start_behavior(self, behavior_id: str, params: dict = None) -> BehaviorResult:
        """Start a behavior."""
        pass

    @abstractmethod
    async def stop_behavior(self, behavior_id: str) -> Result:
        """Stop a behavior."""
        pass

    @abstractmethod
    async def get_available_behaviors(self) -> list[BehaviorInfo]:
        """List available behaviors."""
        pass

    @abstractmethod
    async def get_active_behaviors(self) -> list[BehaviorResult]:
        """Get currently running behaviors."""
        pass

    @abstractmethod
    async def set_emotional_state(self, emotion: str, intensity: float) -> Result:
        """Set robot emotional state."""
        pass


class IHardwarePlugin(IConfigurablePlugin):
    """Hardware abstraction plugin (servo drivers, motor drivers, sensors)."""

    @abstractmethod
    async def initialize_hardware(self, config: dict) -> Result:
        """Initialize hardware with config."""
        pass

    @abstractmethod
    async def get_hardware_info(self) -> dict:
        """Get hardware capabilities."""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check hardware health."""
        pass


class ICommunicationPlugin(IConfigurablePlugin):
    """Communication protocol plugin."""

    @abstractmethod
    async def connect(self, config: dict) -> Result:
        """Establish connection."""
        pass

    @abstractmethod
    async def disconnect(self) -> Result:
        """Close connection."""
        pass

    @abstractmethod
    async def publish(self, topic: str, payload: dict, qos: int = 1) -> Result:
        """Publish message."""
        pass

    @abstractmethod
    async def subscribe(self, topic: str, handler: callable, qos: int = 1) -> Result:
        """Subscribe to topic."""
        pass

    @abstractmethod
    async def request(self, topic: str, payload: dict, timeout: float) -> Result:
        """Request-response pattern."""
        pass