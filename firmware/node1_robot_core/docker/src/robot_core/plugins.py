"""
OpenJ5 Robot Core - Plugin Manager

Dynamic plugin loading, lifecycle management, dependency resolution.
"""

import importlib
import importlib.util
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from robot_core.config import ConfigService
from robot_core.eventbus import EventBus, DomainEvent
from robot_core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PluginMetadata:
    """Plugin metadata from manifest."""
    plugin_id: str
    name: str
    version: str
    author: str
    description: str
    entry_point: str  # module:ClassName
    dependencies: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)
    min_core_version: str = "1.0.0"
    max_core_version: str = "*"


@dataclass
class PluginInstance:
    """Loaded plugin instance."""
    metadata: PluginMetadata
    instance: Any
    state: str = "loaded"  # loaded, starting, running, stopping, stopped, error
    config: dict = field(default_factory=dict)


class IPlugin(ABC):
    """Base plugin interface."""
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata: ...
    
    @abstractmethod
    async def initialize(self, context: "PluginContext") -> None: ...
    
    @abstractmethod
    async def start(self) -> None: ...
    
    @abstractmethod
    async def stop(self) -> None: ...
    
    @abstractmethod
    async def shutdown(self) -> None: ...
    
    @abstractmethod
    async def health_check(self) -> dict: ...
    
    @abstractmethod
    async def handle_config_change(self, config: dict) -> None: ...


@dataclass
class PluginContext:
    """Context provided to plugin during initialization."""
    plugin_id: str
    config: dict
    event_bus: EventBus
    command_bus: Any
    query_bus: Any
    hardware_registry: Any
    config_service: ConfigService
    logger: Any


class PluginManager:
    """
    Manages plugin lifecycle:
    - Discovery (file system, registry)
    - Loading (import, instantiate)
    - Dependency resolution
    - Lifecycle (init, start, stop, shutdown)
    - Hot reload
    """
    
    def __init__(
        self,
        config: ConfigService,
        event_bus: EventBus,
        database=None,
        command_bus: Any = None,
        query_bus: Any = None,
        hardware_registry: Any = None,
    ):
        self.config = config
        self.event_bus = event_bus
        self.database = database
        self.command_bus = command_bus
        self.query_bus = query_bus
        self.hardware_registry = hardware_registry
        
        self._plugins: dict[str, PluginInstance] = {}
        self._load_order: list[str] = []
        self._plugin_dirs: list[Path] = []
        self._config_service = config
    
    async def initialize(self) -> None:
        """Initialize plugin manager and discover plugins."""
        self._discover_plugins()
        logger.info("Plugin manager initialized", dirs=len(self._plugin_dirs))
    
    async def load_all_plugins(self) -> None:
        """Load all enabled plugins from configuration."""
        plugin_configs = self.config.get_section("plugins")
        for plugin_id, plugin_config in plugin_configs.items():
            if isinstance(plugin_config, dict) and plugin_config.get("enabled", True):
                await self.load_plugin(plugin_id, plugin_config)
    
    async def start_all_plugins(self) -> None:
        """Start all loaded plugins in dependency order."""
        for plugin_id in self._load_order:
            await self.start_plugin(plugin_id)
    
    def _discover_plugins(self) -> None:
        """Discover plugin directories."""
        plugin_dirs = self.config.get("plugins.directories", [
            "/opt/openj5/plugins",
            "/home/openj5/.openj5/plugins",
        ])
        
        for dir_path in plugin_dirs:
            path = Path(dir_path)
            if path.exists():
                self._plugin_dirs.append(path)
                logger.debug("Discovered plugin directory", path=str(path))
    
    async def load_plugin(self, plugin_id: str, config: dict) -> bool:
        """Load plugin by ID."""
        if plugin_id in self._plugins:
            logger.warning("Plugin already loaded", plugin_id=plugin_id)
            return True
        
        try:
            # Find plugin manifest
            manifest = await self._find_manifest(plugin_id)
            if not manifest:
                logger.error("Plugin manifest not found", plugin_id=plugin_id)
                return False
            
            # Validate version compatibility
            if not self._check_version_compatibility(manifest):
                logger.error("Plugin version incompatible", plugin_id=plugin_id)
                return False
            
            # Resolve and load dependencies
            for dep_id in manifest.dependencies:
                if dep_id not in self._plugins:
                    dep_config = self.config.get(f"plugins.{dep_id}", {})
                    if not await self.load_plugin(dep_id, dep_config):
                        logger.error("Failed to load dependency", plugin_id=plugin_id, dependency=dep_id)
                        return False
            
            # Load plugin module
            module = await self._load_module(manifest.entry_point)
            plugin_class = getattr(module, manifest.plugin_id.split(".")[-1])
            
            # Create instance
            plugin_instance = plugin_class()
            
            # Verify interface
            if not isinstance(plugin_instance, IPlugin):
                logger.error("Plugin does not implement IPlugin", plugin_id=plugin_id)
                return False
            
            # Verify metadata matches
            if plugin_instance.metadata.plugin_id != plugin_id:
                logger.error("Plugin ID mismatch", expected=plugin_id, actual=plugin_instance.metadata.plugin_id)
                return False
            
            # Create context
            context = PluginContext(
                plugin_id=plugin_id,
                config=config,
                event_bus=self.event_bus,
                command_bus=self.command_bus,
                query_bus=self.query_bus,
                hardware_registry=self.hardware_registry,
                config_service=self._config_service,
                logger=logger.bind(plugin=plugin_id),
            )
            
            # Initialize
            await plugin_instance.initialize(context)
            
            # Register
            self._plugins[plugin_id] = PluginInstance(
                metadata=manifest,
                instance=plugin_instance,
                state="loaded",
                config=config,
            )
            self._load_order.append(plugin_id)
            
            logger.info("Plugin loaded", plugin_id=plugin_id, version=manifest.version)
            return True
            
        except Exception as e:
            logger.error("Failed to load plugin", plugin_id=plugin_id, error=str(e))
            return False
    
    async def _find_manifest(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Find plugin manifest in plugin directories."""
        for plugin_dir in self._plugin_dirs:
            # Look for plugin_id/manifest.json or plugin_id.py
            manifest_path = plugin_dir / plugin_id / "manifest.json"
            if manifest_path.exists():
                import json
                with open(manifest_path) as f:
                    data = json.load(f)
                    return PluginMetadata(**data)
            
            # Or single file plugin
            plugin_file = plugin_dir / f"{plugin_id}.py"
            if plugin_file.exists():
                # Try to import and get metadata
                try:
                    spec = importlib.util.spec_from_file_location(plugin_id, plugin_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # Plugin should have __plugin_metadata__ attribute
                    if hasattr(module, "__plugin_metadata__"):
                        return module.__plugin_metadata__
                except Exception:
                    pass
        
        return None
    
    async def _load_module(self, entry_point: str):
        """Load plugin module from entry point."""
        # entry_point format: "module.submodule:ClassName"
        module_path, class_name = entry_point.split(":")
        
        if module_path in sys.modules:
            return sys.modules[module_path]
        
        # Try to import
        module = importlib.import_module(module_path)
        return module
    
    def _check_version_compatibility(self, manifest: PluginMetadata) -> bool:
        """Check if plugin is compatible with core version."""
        # Simplified - in production use semantic_version
        return True
    
    async def start_plugin(self, plugin_id: str) -> bool:
        """Start loaded plugin."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        try:
            plugin.state = "starting"
            await plugin.instance.start()
            plugin.state = "running"
            
            # Publish event
            await self.event_bus.publish(DomainEvent(
                event_type="PluginStarted",
                source_node="node1",
                payload={"plugin_id": plugin_id},
            ))
            
            logger.info("Plugin started", plugin_id=plugin_id)
            return True
        except Exception as e:
            plugin.state = "error"
            logger.error("Failed to start plugin", plugin_id=plugin_id, error=str(e))
            return False
    
    async def stop_plugin(self, plugin_id: str) -> bool:
        """Stop running plugin."""
        plugin = self._plugins.get(plugin_id)
        if not plugin or plugin.state != "running":
            return False
        
        try:
            plugin.state = "stopping"
            await plugin.instance.stop()
            plugin.state = "stopped"
            
            await self.event_bus.publish(DomainEvent(
                event_type="PluginStopped",
                source_node="node1",
                payload={"plugin_id": plugin_id},
            ))
            
            logger.info("Plugin stopped", plugin_id=plugin_id)
            return True
        except Exception as e:
            plugin.state = "error"
            logger.error("Failed to stop plugin", plugin_id=plugin_id, error=str(e))
            return False
    
    async def reload_plugin(self, plugin_id: str, new_config: dict = None) -> bool:
        """Hot reload plugin with new config."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        try:
            # Handle config change if running
            if plugin.state == "running":
                await plugin.instance.handle_config_change(new_config or plugin.config)
            
            plugin.config = new_config or plugin.config
            logger.info("Plugin config reloaded", plugin_id=plugin_id)
            return True
        except Exception as e:
            logger.error("Failed to reload plugin", plugin_id=plugin_id, error=str(e))
            return False
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload plugin completely."""
        if plugin_id not in self._plugins:
            return False
        
        # Stop if running
        if self._plugins[plugin_id].state == "running":
            await self.stop_plugin(plugin_id)
        
        # Shutdown
        try:
            await self._plugins[plugin_id].instance.shutdown()
        except Exception as e:
            logger.error("Plugin shutdown error", plugin_id=plugin_id, error=str(e))
        
        # Remove
        del self._plugins[plugin_id]
        self._load_order.remove(plugin_id)
        
        await self.event_bus.publish(DomainEvent(
            event_type="PluginUnloaded",
            source_node="node1",
            payload={"plugin_id": plugin_id},
        ))
        
        logger.info("Plugin unloaded", plugin_id=plugin_id)
        return True
    
    async def shutdown(self) -> None:
        """Shutdown all plugins."""
        # Stop in reverse load order
        for plugin_id in reversed(self._load_order):
            await self.stop_plugin(plugin_id)
            await self.unload_plugin(plugin_id)
        
        logger.info("All plugins shut down")
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInstance]:
        """Get plugin instance."""
        return self._plugins.get(plugin_id)
    
    def list_plugins(self) -> list[dict]:
        """List all loaded plugins."""
        return [
            {
                "plugin_id": pid,
                "name": p.metadata.name,
                "version": p.metadata.version,
                "state": p.state,
            }
            for pid, p in self._plugins.items()
        ]