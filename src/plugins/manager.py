"""
OpenJ5 Plugin Architecture - Core Implementation

Plugin Manager, Registry, Loader, and Sandbox.
"""
from __future__ import annotations
import asyncio
import importlib
import importlib.util
import inspect
import sys
import traceback
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from datetime import datetime

from .interfaces import (
    IPlugin, IPluginManager, IPluginRegistry,
    PluginMetadata, PluginState, PluginHealth,
    PluginContext, PluginDependency, PluginType,
    IConfigurablePlugin, ILifecyclePlugin,
    Result,
)


class PluginLoadError(Exception):
    def __init__(self, plugin_id: str, message: str):
        self.plugin_id = plugin_id
        super().__init__(f"Plugin {plugin_id}: {message}")


class PluginManager(IPluginManager):
    """Core plugin manager - loads, manages lifecycle, resolves dependencies."""

    def __init__(
        self,
        plugin_dirs: list[str] = None,
        event_bus=None,
        command_bus=None,
        query_bus=None,
        hardware_registry=None,
        config_service=None,
        logger=None,
    ):
        self._plugin_dirs = [Path(d) for d in (plugin_dirs or ["plugins"])]
        self._event_bus = event_bus
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._hardware_registry = hardware_registry
        self._config_service = config_service
        self._logger = logger

        self._plugins: dict[str, IPlugin] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._contexts: dict[str, PluginContext] = {}
        self._load_order: list[str] = []
        self._lock = asyncio.Lock()

    async def load_plugin(self, plugin_path: str, config: dict = None) -> Result[IPlugin]:
        """Load plugin from Python module path or file path."""
        async with self._lock:
            try:
                # Resolve path
                path = Path(plugin_path)
                if not path.is_absolute():
                    path = self._resolve_plugin_path(path)

                if not path.exists():
                    return Result.fail("NOT_FOUND", f"Plugin not found: {path}")

                # Load module
                module_name = f"openj5_plugin_{path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, path)
                if not spec or not spec.loader:
                    return Result.fail("INVALID_MODULE", f"Cannot load module from {path}")

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # Find plugin class
                plugin_class = self._find_plugin_class(module)
                if not plugin_class:
                    return Result.fail("NO_PLUGIN_CLASS", f"No IPlugin subclass found in {path}")

                # Instantiate
                plugin = plugin_class()

                # Validate metadata
                if not hasattr(plugin, 'metadata') or not isinstance(plugin.metadata, PluginMetadata):
                    return Result.fail("INVALID_METADATA", "Plugin must have 'metadata' property returning PluginMetadata")

                metadata = plugin.metadata

                # Check version compatibility
                # TODO: implement version check

                # Resolve dependencies
                dep_result = await self.resolve_dependencies(plugin)
                if not dep_result.success:
                    return dep_result

                # Create context
                context = PluginContext(
                    plugin_id=metadata.plugin_id,
                    config=config or {},
                    event_bus=self._event_bus,
                    command_bus=self._command_bus,
                    query_bus=self._query_bus,
                    hardware_registry=self._hardware_registry,
                    config_service=self._config_service,
                    logger=self._logger,
                    node_identity=None,  # Set by node
                )

                # Initialize
                init_result = await plugin.initialize(context)
                if not init_result.success:
                    return Result.fail("INIT_FAILED", f"Plugin init failed: {init_result.error_message}")

                # Register
                self._plugins[metadata.plugin_id] = plugin
                self._metadata[metadata.plugin_id] = metadata
                self._contexts[metadata.plugin_id] = context
                self._load_order.append(metadata.plugin_id)

                # Publish plugin loaded event
                if self._event_bus:
                    await self._event_bus.publish(
                        "PluginLoadedEvent",
                        {"plugin_id": metadata.plugin_id, "version": metadata.version}
                    )

                return Result.ok(plugin)

            except Exception as e:
                return Result.fail("LOAD_ERROR", f"Failed to load plugin: {e}")

    def _resolve_plugin_path(self, path: Path) -> Path:
        """Resolve relative plugin path against plugin dirs."""
        for base in self._plugin_dirs:
            full = base / path
            if full.exists():
                return full
            # Also check with .py extension
            if not path.suffix:
                py_path = base / f"{path}.py"
                if py_path.exists():
                    return py_path
        return path  # Return as-is if not found

    def _find_plugin_class(self, module) -> type | None:
        """Find IPlugin subclass in module."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, IPlugin) and obj is not IPlugin:
                return obj
        return None

    async def unload_plugin(self, plugin_id: str) -> Result:
        """Unload plugin gracefully."""
        async with self._lock:
            plugin = self._plugins.get(plugin_id)
            if not plugin:
                return Result.fail("NOT_LOADED", f"Plugin {plugin_id} not loaded")

            try:
                # Stop and shutdown
                await plugin.stop()
                await plugin.shutdown()

                # Remove from registry
                del self._plugins[plugin_id]
                del self._metadata[plugin_id]
                del self._contexts[plugin_id]
                self._load_order.remove(plugin_id)

                # Publish event
                if self._event_bus:
                    await self._event_bus.publish(
                        "PluginUnloadedEvent",
                        {"plugin_id": plugin_id}
                    )

                return Result.ok(True)

            except Exception as e:
                return Result.fail("UNLOAD_ERROR", f"Failed to unload plugin: {e}")

    async def get_plugin(self, plugin_id: str) -> IPlugin | None:
        return self._plugins.get(plugin_id)

    async def get_all_plugins(self) -> list[IPlugin]:
        return list(self._plugins.values())

    async def enable_plugin(self, plugin_id: str) -> Result:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return Result.fail("NOT_LOADED", f"Plugin {plugin_id} not loaded")

        try:
            result = await plugin.start()
            if result.success:
                if self._event_bus:
                    await self._event_bus.publish(
                        "PluginStartedEvent",
                        {"plugin_id": plugin_id}
                    )
            return result
        except Exception as e:
            return Result.fail("START_ERROR", f"Failed to start plugin: {e}")

    async def disable_plugin(self, plugin_id: str) -> Result:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return Result.fail("NOT_LOADED", f"Plugin {plugin_id} not loaded")

        try:
            result = await plugin.stop()
            if result.success and self._event_bus:
                await self._event_bus.publish(
                    "PluginStoppedEvent",
                    {"plugin_id": plugin_id}
                )
            return result
        except Exception as e:
            return Result.fail("STOP_ERROR", f"Failed to stop plugin: {e}")

    async def reload_plugin(self, plugin_id: str, config: dict = None) -> Result:
        """Hot-reload plugin with new config."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return Result.fail("NOT_LOADED", f"Plugin {plugin_id} not loaded")

        if isinstance(plugin, IConfigurablePlugin):
            try:
                # Validate new config
                validated = await plugin.validate_config(config or {})
                if not validated.success:
                    return validated

                # Apply config change
                result = await plugin.handle_config_change(validated.data)
                if result.success and self._event_bus:
                    await self._event_bus.publish(
                        "PluginConfigChangedEvent",
                        {"plugin_id": plugin_id, "config": config}
                    )
                return result
            except Exception as e:
                return Result.fail("RELOAD_ERROR", f"Failed to reload plugin: {e}")

        return Result.fail("NOT_CONFIGURABLE", "Plugin does not support config reload")

    async def resolve_dependencies(self, plugin: IPlugin) -> Result[list[IPlugin]]:
        """Resolve and load plugin dependencies."""
        metadata = plugin.metadata
        resolved = []

        for dep in metadata.dependencies:
            if dep.plugin_id in self._plugins:
                resolved.append(self._plugins[dep.plugin_id])
                continue

            # Try to discover and load
            discovered = await self.discover_plugins([str(d) for d in self._plugin_dirs])
            dep_meta = next((m for m in discovered if m.plugin_id == dep.plugin_id), None)

            if not dep_meta:
                if dep.required:
                    return Result.fail(
                        "DEPENDENCY_MISSING",
                        f"Required dependency {dep.plugin_id} not found"
                    )
                continue

            # Check version
            # TODO: semver check

            # Load dependency
            load_result = await self.load_plugin(dep_meta.entry_point)
            if not load_result.success:
                if dep.required:
                    return Result.fail(
                        "DEPENDENCY_LOAD_FAILED",
                        f"Failed to load dependency {dep.plugin_id}: {load_result.error_message}"
                    )
                continue

            # Enable dependency
            enable_result = await self.enable_plugin(dep.plugin_id)
            if not enable_result.success:
                if dep.required:
                    return enable_result

            resolved.append(self._plugins[dep.plugin_id])

        return Result.ok(resolved)

    async def discover_plugins(self, plugin_dirs: list[str]) -> list[PluginMetadata]:
        """Discover available plugins in directories."""
        discovered = []

        for dir_str in plugin_dirs:
            dir_path = Path(dir_str)
            if not dir_path.exists():
                continue

            for py_file in dir_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue

                try:
                    # Load module to read metadata
                    module_name = f"openj5_discover_{py_file.stem}"
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    # Find plugin class and get metadata
                    plugin_class = self._find_plugin_class(module)
                    if plugin_class:
                        # Create temp instance to get metadata
                        temp = plugin_class()
                        if hasattr(temp, 'metadata'):
                            discovered.append(temp.metadata)

                except Exception:
                    # Skip invalid plugins
                    continue

        return discovered


class PluginRegistry(IPluginRegistry):
    """Plugin registry for marketplace."""

    def __init__(self, storage_path: str = "registry"):
        self._storage = Path(storage_path)
        self._storage.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, list[PluginMetadata]] = {}

    async def register(self, metadata: PluginMetadata, artifact: bytes) -> Result:
        """Register plugin artifact."""
        plugin_dir = self._storage / metadata.plugin_id / metadata.version
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Save artifact
        artifact_path = plugin_dir / f"{metadata.plugin_id}-{metadata.version}.py"
        artifact_path.write_bytes(artifact)

        # Save metadata
        import json
        meta_path = plugin_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata.__dict__, default=str, indent=2))

        # Update index
        if metadata.plugin_id not in self._index:
            self._index[metadata.plugin_id] = []
        self._index[metadata.plugin_id].append(metadata)

        return Result.ok(True)

    async def unregister(self, plugin_id: str, version: str) -> Result:
        """Unregister plugin version."""
        plugin_dir = self._storage / plugin_id / version
        if plugin_dir.exists():
            import shutil
            shutil.rmtree(plugin_dir)

        if plugin_id in self._index:
            self._index[plugin_id] = [
                m for m in self._index[plugin_id] if m.version != version
            ]

        return Result.ok(True)

    async def get_available(self, plugin_type: PluginType = None) -> list[PluginMetadata]:
        """Get all available plugins."""
        all_plugins = []
        for versions in self._index.values():
            all_plugins.extend(versions)

        if plugin_type:
            all_plugins = [p for p in all_plugins if p.plugin_type == plugin_type]

        return all_plugins

    async def install(self, plugin_id: str, version: str, target_dir: str) -> Result:
        """Install plugin to target directory."""
        source_dir = self._storage / plugin_id / version
        if not source_dir.exists():
            return Result.fail("NOT_FOUND", f"Plugin {plugin_id}@{version} not in registry")

        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)

        import shutil
        for file in source_dir.iterdir():
            if file.name != "metadata.json":
                shutil.copy2(file, target / file.name)

        return Result.ok(True)

    async def verify_signature(self, plugin_id: str, version: str) -> Result[bool]:
        """Verify plugin signature (placeholder)."""
        # TODO: Implement cryptographic signature verification
        return Result.ok(True)


# === PLUGIN SANDBOX (Security) ===

class PluginSandbox:
    """Sandbox for running plugins with restricted permissions."""

    def __init__(self, permissions: list[PluginPermission]):
        self._permissions = permissions

    def check_permission(self, resource: str, action: str, scope: str = "*") -> bool:
        """Check if action is permitted."""
        for perm in self._permissions:
            if perm.resource == resource or perm.resource == "*":
                if action in perm.actions or "*" in perm.actions:
                    if perm.scope == scope or perm.scope == "*" or scope == "*":
                        return True
        return False

    def wrap_plugin(self, plugin: IPlugin) -> IPlugin:
        """Wrap plugin with permission checks."""
        # TODO: Implement proxy that checks permissions
        return plugin


# === FACTORY ===

def create_plugin_manager(
    plugin_dirs: list[str] = None,
    **services
) -> PluginManager:
    """Factory for creating plugin manager with services."""
    return PluginManager(plugin_dirs=plugin_dirs, **services)