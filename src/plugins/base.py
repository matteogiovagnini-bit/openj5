"""
OpenJ5 Plugin Base Contracts

Fundamental plugin framework contracts shared by interfaces and manager.
Defined ONCE here to avoid circular imports (see ADR-007).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..core.domain import Result


# === ENUMS ===

class PluginType(Enum):
    """Plugin category."""
    VISION = "vision"
    SPEECH = "speech"
    AI = "ai"
    NAVIGATION = "navigation"
    MOTION = "motion"
    HARDWARE = "hardware"
    COMMUNICATION = "communication"
    BEHAVIOR = "behavior"
    BATTERY = "battery"
    GENERIC = "generic"


class PluginState(Enum):
    """Plugin lifecycle state."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"
    UNLOADED = "unloaded"


# === DATA CONTRACTS ===

@dataclass
class PluginDependency:
    """Declared dependency on another plugin."""
    plugin_id: str
    required: bool = True
    version_spec: str = "*"


@dataclass
class PluginPermission:
    """Permission granted to a plugin (checked by PluginSandbox)."""
    resource: str = "*"
    actions: list[str] = field(default_factory=lambda: ["*"])
    scope: str = "*"


@dataclass
class PluginConfigSchema:
    """JSON Schema describing the plugin configuration."""
    schema: dict = field(default_factory=dict)


@dataclass
class PluginHealth:
    """Plugin health report."""
    healthy: bool = True
    status: str = "ok"
    details: dict = field(default_factory=dict)


@dataclass
class PluginMetadata:
    """Plugin descriptor returned by the 'metadata' property."""
    plugin_id: str = ""
    name: str = ""
    version: str = "0.0.0"
    author: str = ""
    description: str = ""
    plugin_type: PluginType = PluginType.GENERIC
    entry_point: str = ""
    dependencies: list[PluginDependency] = field(default_factory=list)
    permissions: list[PluginPermission] = field(default_factory=list)
    config_schema: Optional[PluginConfigSchema] = None


@dataclass
class PluginContext:
    """Context passed to a plugin on initialization."""
    plugin_id: str = ""
    config: dict = field(default_factory=dict)
    event_bus: Any = None
    command_bus: Any = None
    query_bus: Any = None
    hardware_registry: Any = None
    config_service: Any = None
    logger: Any = None
    node_identity: Any = None


# === BASE INTERFACES ===

class IPlugin(ABC):
    """Base plugin contract (ADR-007)."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin descriptor."""

    @abstractmethod
    async def initialize(self, context: PluginContext) -> Result:
        """Initialize with the given context. Called once after load."""

    @abstractmethod
    async def start(self) -> Result:
        """Start plugin operation."""

    @abstractmethod
    async def stop(self) -> Result:
        """Stop plugin operation (idempotent)."""

    @abstractmethod
    async def shutdown(self) -> Result:
        """Release all resources. Called before unload."""

    @abstractmethod
    async def health_check(self) -> PluginHealth:
        """Report plugin health."""


class IConfigurablePlugin(IPlugin):
    """Plugin supporting runtime configuration reload."""

    @abstractmethod
    async def validate_config(self, config: dict) -> Result:
        """Validate a candidate configuration without applying it."""

    @abstractmethod
    async def handle_config_change(self, config: dict) -> Result:
        """Apply a validated configuration at runtime."""


class ILifecyclePlugin(IPlugin):
    """Plugin requiring extended lifecycle notifications.

    Marker interface: hosts that detect it emit lifecycle events
    (before_start / after_stop) when available.
    """
    pass


class IPluginManager(ABC):
    """Plugin lifecycle management contract."""

    @abstractmethod
    async def load_plugin(self, plugin_path: str, config: dict = None) -> Result[IPlugin]:
        """Load a plugin from module path or file path."""

    @abstractmethod
    async def unload_plugin(self, plugin_id: str) -> Result:
        """Unload a plugin gracefully."""

    @abstractmethod
    async def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """Get a loaded plugin by id."""

    @abstractmethod
    async def get_all_plugins(self) -> list[IPlugin]:
        """List all loaded plugins."""

    @abstractmethod
    async def enable_plugin(self, plugin_id: str) -> Result:
        """Start a loaded plugin."""

    @abstractmethod
    async def disable_plugin(self, plugin_id: str) -> Result:
        """Stop a loaded plugin."""

    @abstractmethod
    async def resolve_dependencies(self, plugin: IPlugin) -> Result[list[IPlugin]]:
        """Resolve and load plugin dependencies."""

    @abstractmethod
    async def discover_plugins(self, plugin_dirs: list[str]) -> list[PluginMetadata]:
        """Discover available plugins in directories."""


class IPluginRegistry(ABC):
    """Plugin marketplace registry contract."""

    @abstractmethod
    async def register(self, metadata: PluginMetadata, artifact: bytes) -> Result:
        """Register a plugin artifact."""

    @abstractmethod
    async def unregister(self, plugin_id: str, version: str) -> Result:
        """Remove a plugin version."""

    @abstractmethod
    async def get_available(self, plugin_type: Optional[PluginType] = None) -> list[PluginMetadata]:
        """List available plugins, optionally filtered by type."""

    @abstractmethod
    async def install(self, plugin_id: str, version: str, target_dir: str) -> Result:
        """Install a plugin version into a target directory."""

    @abstractmethod
    async def verify_signature(self, plugin_id: str, version: str) -> Result[bool]:
        """Verify the cryptographic signature of a plugin artifact."""
