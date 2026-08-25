"""
OpenJ5 Configuration Service

Hot-reloadable, multi-source configuration with JSON Schema validation.
Priority: ENV > Database > YAML > JSON > Defaults
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Awaitable
from abc import ABC, abstractmethod
from pathlib import Path
import asyncio
import json
import os
import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
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
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            if value.lower() in ("true", "false"):
                return value.lower() == "true"
            try:
                return float(value) if "." in value else int(value)
            except ValueError:
                return value

    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
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
        # Placeholder - implementation depends on database driver
        return {}

    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        return "db-watch"

    async def unwatch(self, watch_id: str) -> None:
        pass


@dataclass
class ConfigSchema:
    """JSON Schema for config validation."""
    schema: dict
    version: str = "1.0"

    def validate(self, data: dict) -> tuple[bool, list[str]]:
        try:
            validate(instance=data, schema=self.schema)
            return True, []
        except ValidationError as e:
            return False, [str(e)]


class ConfigService:
    """
    Configuration Service with hot reload.
    
    Features:
    - Multi-source with priority (ENV > DB > YAML > JSON > Defaults)
    - JSON Schema validation
    - Hot reload via file watching
    - Change notifications
    - Type-safe access via Pydantic models
    """

    def __init__(self, config_root: Path = Path("/etc/openj5")):
        self._config_root = config_root
        self._sources: list[tuple[int, ConfigSource]] = []  # (priority, source)
        self._config: dict = {}
        self._schemas: dict[str, ConfigSchema] = {}
        self._watchers: dict[str, list[Callable[[], Awaitable[None]]]] = {}
        self._watch_id = 0

    def add_source(self, source: ConfigSource, priority: int = 0):
        """Add config source. Higher priority = loaded last (overrides)."""
        self._sources.append((priority, source))
        self._sources.sort(key=lambda x: x[0])

    def register_schema(self, name: str, schema: ConfigSchema):
        """Register JSON schema for validation."""
        self._schemas[name] = schema

    async def load(self) -> dict:
        """Load and merge all configuration sources."""
        merged = {}
        for _, source in self._sources:
            data = await source.load()
            merged = self._deep_merge(merged, data)

        # Validate against schemas
        for name, schema in self._schemas.items():
            if name in merged:
                valid, errors = schema.validate(merged[name])
                if not valid:
                    raise ValueError(f"Config validation failed for {name}: {errors}")

        self._config = merged
        return merged

    async def reload(self) -> dict:
        """Force reload configuration."""
        return await self.load()

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge override into base."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key (e.g., 'node2.servos.neck_yaw.max_angle_deg')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_section(self, section: str) -> dict:
        """Get entire config section."""
        return self._config.get(section, {})

    def set(self, key: str, value: Any, persist: bool = False) -> bool:
        """Set config value (runtime only unless persist=True)."""
        keys = key.split(".")
        target = self._config
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value

        if persist:
            # TODO: Persist to file/database
            pass
        return True

    def watch(self, key: str, callback: Callable[[], Awaitable[None]]) -> str:
        """Watch for config changes on key prefix."""
        watch_id = f"watch_{self._watch_id}"
        self._watch_id += 1

        if key not in self._watchers:
            self._watchers[key] = []
        self._watchers[key].append(callback)

        # Also register with file sources
        for _, source in self._sources:
            if isinstance(source, FileConfigSource):
                source.watch(callback)

        return watch_id

    def unwatch(self, watch_id: str) -> bool:
        """Stop watching."""
        for key, callbacks in self._watchers.items():
            for cb in callbacks:
                if id(cb) == int(watch_id.split("_")[-1]):
                    callbacks.remove(cb)
                    return True
        return False

    def notify(self, key: str):
        """Notify watchers of key change."""
        for watch_key, callbacks in self._watchers.items():
            if key.startswith(watch_key) or watch_key.startswith(key):
                for callback in callbacks:
                    try:
                        asyncio.create_task(callback())
                    except Exception:
                        pass

    async def validate(self, section: str, data: dict) -> tuple[bool, list[str]]:
        """Validate config section against schema."""
        if section in self._schemas:
            return self._schemas[section].validate(data)
        return True, []


# Global config service instance
_config_service: ConfigService | None = None


def get_config_service(config_root: Path = Path("/etc/openj5")) -> ConfigService:
    """Get global config service instance."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService(config_root)
    return _config_service


async def setup_default_config(config_root: Path = Path("/etc/openj5")) -> ConfigService:
    """Setup default configuration sources."""
    service = ConfigService(config_root)

    # 1. Defaults (lowest priority)
    # 2. JSON files
    json_dir = config_root / "json"
    if json_dir.exists():
        for json_file in json_dir.glob("*.json"):
            service.add_source(FileConfigSource(json_file), priority=10)

    # 3. YAML files
    yaml_dir = config_root / "yaml"
    if yaml_dir.exists():
        for yaml_file in yaml_dir.glob("*.yaml"):
            service.add_source(FileConfigSource(yaml_file), priority=20)

    # 4. Database (if configured)
    # db_url = os.getenv("OPENJ5_DB_URL")
    # if db_url:
    #     service.add_source(DatabaseConfigSource(db_url), priority=30)

    # 5. Environment variables (highest priority)
    service.add_source(EnvConfigSource(), priority=100)

    await service.load()
    return service