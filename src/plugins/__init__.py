"""
OpenJ5 Plugins Package
"""
from .interfaces import (
    IPlugin, IConfigurablePlugin, ILifecyclePlugin,
    IVisionPlugin, ISpeechPlugin, IAIPlugin, INavigationPlugin,
    IBatteryPlugin, IBehaviorPlugin, IHardwarePlugin, ICommunicationPlugin,
    PluginMetadata, PluginState, PluginType, PluginDependency,
    PluginPermission, PluginConfigSchema, PluginHealth,
    PluginContext,
    FaceDetection, ObjectDetection, SegmentationMap,
    SpeechResult, WakeWordResult,
    ChatMessage, Tool, ChatResponse, ClassificationResult,
    PathPlan, LocalizationResult, MapUpdate,
    BehaviorResult, BehaviorInfo,
)
from .manager import PluginManager, PluginRegistry, PluginSandbox, create_plugin_manager

__all__ = [
    # Interfaces
    "IPlugin", "IConfigurablePlugin", "ILifecyclePlugin",
    "IVisionPlugin", "ISpeechPlugin", "IAIPlugin", "INavigationPlugin",
    "IBatteryPlugin", "IBehaviorPlugin", "IHardwarePlugin", "ICommunicationPlugin",
    # Types
    "PluginMetadata", "PluginState", "PluginType", "PluginDependency",
    "PluginPermission", "PluginConfigSchema", "PluginHealth",
    "PluginContext",
    "FaceDetection", "ObjectDetection", "SegmentationMap",
    "SpeechResult", "WakeWordResult",
    "ChatMessage", "Tool", "ChatResponse", "ClassificationResult",
    "PathPlan", "LocalizationResult", "MapUpdate",
    "BehaviorResult", "BehaviorInfo",
    # Core
    "PluginManager", "PluginRegistry", "PluginSandbox", "create_plugin_manager",
]