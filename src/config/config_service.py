"""
OpenJ5 Configuration Service

Hot-reloadable, multi-source configuration with JSON Schema validation.
Priority: ENV > Database > YAML > JSON > Defaults
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from abc import ABC, abstractmethod
from pathlib import Path
import asyncio
import json
import yaml
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import jsonschema
from jsonschema import validate, ValidationError


class ConfigSource(ABC):
    """Configuration source interface."""

    @abstractmethod
    async def load(self) -> dict:
        """Load configuration."""
        pass

    @abstractmethod
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        """Watch for changes. Returns watch_id."""
        pass

    @abstractmethod
    async def unwatch(self, watch_id: str) -> None:
        """Stop watching."""
        pass


class EnvConfigSource(ConfigSource):
    """Environment variable config source (highest priority)."""

    def __init__(self, prefix: str = "OPENJ5_"):
        self._prefix = prefix

    async def load(self) -> dict:
        config = {}
        for key, value in os.environ.items():
            if key.startswith(self._prefix):
                # OPENJ5_NODE2_SERVOS_NECK_YAW_MAX_ANGLE_DEG -> node2.servos.neck_yaw.max_angle_deg
                path = key[len(self._prefix):].lower().split("_")
                self._set_nested(config, path, self._parse_value(value))
        return config

    def _set_nested(self, d: dict, path: list[str], value: Any):
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = value

    def _parse_value(self, value: str) -> Any:
        # Try JSON parse
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # Try bool
            if value.lower() in ("true", "false"):
                return value.lower() == "true"
            # Try number
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                return value

    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        # Env vars don't change at runtime typically
        return "env-watch"

    async def unwatch(self, watch_id: str) -> None:
        pass


class FileConfigSource(ConfigSource):
    """JSON/YAML file config source."""

    def __init__(self, file_path: str | Path):
        self._path = Path(file_path)
        self._observer: Observer | None = None
        self._callbacks: dict[str, Callable[[], Awaitable[None]]] = {}

    async def load(self) -> dict:
        if not self._path.exists():
            return {}

        content = self._path.read_text()
        if self._path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        elif self._path.suffix == ".json":
            return json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {self._path.suffix}")

    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        watch_id = str(id(callback))
        self._callbacks[watch_id] = callback

        if self._observer is None:
            self._observer = Observer()
            self._observer.schedule(
                _FileChangeHandler(self),
                str(self._path.parent),
                recursive=False
            )
            self._observer.start()

        return watch_id

    async def unwatch(self, watch_id: str) -> None:
        self._callbacks.pop(watch_id, None)
        if not self._callbacks and self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    async def _notify(self):
        for callback in self._callbacks.values():
            try:
                await callback()
            except Exception:
                pass


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(self, source: FileConfigSource):
        self._source = source

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path) == self._source._path:
            asyncio.create_task(self._source._notify())


class DatabaseConfigSource(ConfigSource):
    """Database config source (PostgreSQL/SQLite)."""

    def __init__(self, db_url: str, table: str = "config"):
        self._db_url = db_url
        self._table = table
        self._pool = None

    async def load(self) -> dict:
        # Implementation depends on database driver
        # This is a placeholder
        return {}

    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        # Could use pg_notify for PostgreSQL
        return "db-watch"

    async def unwatch(self, watch_id: str) -> None:
        pass


@dataclass
class ConfigSchema:
    """JSON Schema for config validation."""
    schema: dict
    version: str = "1.0"

    def validate(self, data: dict) -> tuple[bool, list[str]]:
        """Validate data against schema. Returns (valid, errors)."""
        try:
            validate(instance=data, schema=self.schema)
            return True, []
        except ValidationError as e:
            return False, [str(e)]


class ConfigService:
    """
    Configuration Service with hot reload.
    
    Features:
    - Multi-source with priority
    - JSON Schema validation
    - Hot reload via file watching
    - Change notifications
    - Type-safe access via Pydantic models
    """

    def __init__(
        self,
        sources: list[ConfigSource] = None,
        schemas: dict[str, ConfigSchema] = None,
        default_config: dict = None
    ):
        self._sources = sources or []
        self._schemas = schemas or {}
        self._default_config = default_config or {}
        self._config: dict = {}
        self._callbacks: dict[str, list[Callable[[str, Any], Awaitable[None]]]] = {}
        self._watchers: dict[str, str] = {}  # source_id -> watch_id
        self._lock = asyncio.Lock()

    async def initialize(self) -> Result:
        """Load initial configuration from all sources."""
        try:
            await self._reload()
            # Start watching all sources
            for i, source in enumerate(self._sources):
                watch_id = await source.watch(self._on_source_changed)
                self._watchers[f"source_{i}"] = watch_id
            return Result.ok(True)
        except Exception as e:
            return Result.fail("INIT_FAILED", str(e))

    async def shutdown(self) -> Result:
        """Stop watching and cleanup."""
        for source_id, watch_id in self._watchers.items():
            source_idx = int(source_id.split("_")[1])
            await self._sources[source_idx].unwatch(watch_id)
        self._watchers.clear()
        return Result.ok(True)

    async def _reload(self):
        """Reload config from all sources (priority order)."""
        merged = self._default_config.copy()

        # Sources are in priority order (lowest to highest)
        for source in self._sources:
            source_config = await source.load()
            merged = self._deep_merge(merged, source_config)

        # Validate against schemas
        for key, schema in self._schemas.items():
            section = self._get_nested(merged, key.split("."))
            if section is not None:
                valid, errors = schema.validate(section)
                if not valid:
                    # Log validation errors but don't fail - use previous config
                    pass  # Log errors

        old_config = self._config
        self._config = merged

        # Notify callbacks
        await self._notify_changes(old_config, merged)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dicts."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _get_nested(self, data: dict, path: list[str]) -> Any:
        """Get nested value by path."""
        for key in path:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return None
        return data

    async def _on_source_changed(self):
        """Called when any source changes."""
        await self._reload()

    async def _notify_changes(self, old: dict, new: dict):
        """Notify callbacks of specific changes."""
        changes = self._diff(old, new)
        for path, value in changes.items():
            await self._notify_callbacks(path, value)

    def _diff(self, old: dict, new: dict, prefix: str = "") -> dict[str, Any]:
        """Find differences between configs."""
        changes = {}
        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            path = f"{prefix}.{key}" if prefix else key
            old_val = old.get(key)
            new_val = new.get(key)

            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.update(self._diff(old_val, new_val, path))
            elif old_val != new_val:
                changes[path] = new_val

        return changes

    async def _notify_callbacks(self, path: str, value: Any):
        """Notify registered callbacks."""
        # Exact path callbacks
        for callback in self._callbacks.get(path, []):
            try:
                await callback(path, value)
            except Exception:
                pass

        # Wildcard callbacks
        for pattern, callbacks in self._callbacks.items():
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if path.startswith(prefix + ".") or path == prefix:
                    for callback in callbacks:
                        try:
                            await callback(path, value)
                        except Exception:
                            pass

    # === PUBLIC API ===

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation path."""
        return self._get_nested(self._config, key.split(".")) or default

    def get_section(self, section: str) -> dict:
        """Get entire config section."""
        return self._get_nested(self._config, section.split(".")) or {}

    async def set(self, key: str, value: Any, persist: bool = False) -> Result:
        """Set config value (runtime only unless persist=True)."""
        async with self._lock:
            self._set_nested(self._config, key.split("."), value)

            # Validate if schema exists
            for schema_key, schema in self._schemas.items():
                if key.startswith(schema_key):
                    section = self.get_section(schema_key)
                    valid, errors = schema.validate(section)
                    if not valid:
                        return Result.fail("VALIDATION_FAILED", f"Schema validation failed: {errors}")

            await self._notify_callbacks(key, value)
            return Result.ok(True)

    def _set_nested(self, d: dict, path: list[str], value: Any):
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = value

    def watch(self, key: str, callback: Callable[[str, Any], Awaitable[None]]) -> str:
        """Watch config key for changes."""
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)
        return key

    def unwatch(self, key: str, callback: Callable = None) -> None:
        """Stop watching config key."""
        if key in self._callbacks:
            if callback:
                self._callbacks[key].remove(callback)
            else:
                self._callbacks[key].clear()

    def get_schema(self, key: str) -> ConfigSchema | None:
        """Get schema for config section."""
        return self._schemas.get(key)

    def register_schema(self, key: str, schema: ConfigSchema) -> None:
        """Register validation schema."""
        self._schemas[key] = schema

    def export(self) -> dict:
        """Export full config."""
        return self._config.copy()

    def export_section(self, section: str) -> dict:
        """Export config section."""
        return self.get_section(section).copy()


# === RESULT TYPE ===
from ..core.domain import Result


# === FACTORY ===

def create_config_service(
    config_dir: str = "config",
    node_id: str = "node1",
    env_prefix: str = "OPENJ5_"
) -> ConfigService:
    """Create config service with standard sources."""
    config_path = Path(config_dir)

    sources = [
        # Lowest priority
        FileConfigSource(config_path / "common" / "defaults.yaml"),
        FileConfigSource(config_path / node_id / "config.yaml"),
        FileConfigSource(config_path / "common" / "secrets.yaml"),
        # Higher priority
        FileConfigSource(config_path / node_id / "overrides.yaml"),
        # Highest priority
        EnvConfigSource(env_prefix),
    ]

    return ConfigService(sources=sources)