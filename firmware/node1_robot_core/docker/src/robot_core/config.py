"""
OpenJ5 Robot Core - Configuration Service

Multi-source configuration with hot reload.
Priority: ENV > Database > YAML > JSON > Defaults
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Callable, Awaitable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import yaml
from jsonschema import validate, ValidationError

from robot_core.logging import get_logger

logger = get_logger(__name__)


class ConfigSource:
    """Base configuration source."""
    
    async def load(self) -> dict:
        raise NotImplementedError
    
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        raise NotImplementedError
    
    async def unwatch(self, watch_id: str) -> None:
        raise NotImplementedError


class EnvConfigSource(ConfigSource):
    """Environment variable configuration source (highest priority)."""
    
    def __init__(self, prefix: str = "OPENJ5_"):
        self.prefix = prefix
    
    async def load(self) -> dict:
        config = {}
        for key, value in os.environ.items():
            if key.startswith(self.prefix):
                # OPENJ5_NODE2_SERVOS_NECK_YAW_MAX_ANGLE_DEG -> node2.servos.neck_yaw.max_angle_deg
                path = key[len(self.prefix):].lower().split("_")
                self._set_nested(config, path, self._parse_value(value))
        return config
    
    def _set_nested(self, d: dict, path: list[str], value: Any) -> None:
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = value
    
    def _parse_value(self, value: str) -> Any:
        # Try JSON first
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        # Boolean
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        # Number
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            return value
    
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        # Env vars don't change at runtime typically
        return "env-watch"
    
    async def unwatch(self, watch_id: str) -> None:
        pass


class FileConfigSource(ConfigSource):
    """JSON/YAML file configuration source."""
    
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.observer: Observer | None = None
        self.callbacks: dict[str, Callable[[], Awaitable[None]]] = {}
    
    async def load(self) -> dict:
        if not self.file_path.exists():
            return {}
        
        content = self.file_path.read_text()
        if self.file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        elif self.file_path.suffix == ".json":
            return json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {self.file_path.suffix}")
    
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        watch_id = str(id(callback))
        self.callbacks[watch_id] = callback
        
        if self.observer is None:
            self.observer = Observer()
            self.observer.schedule(
                _FileChangeHandler(self),
                str(self.file_path.parent),
                recursive=False
            )
            self.observer.start()
        
        return watch_id
    
    async def unwatch(self, watch_id: str) -> None:
        self.callbacks.pop(watch_id, None)
        if not self.callbacks and self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
    
    async def _notify(self) -> None:
        for callback in self.callbacks.values():
            try:
                await callback()
            except Exception as e:
                logger.error(f"Config watch callback failed: {e}")


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(self, source: FileConfigSource):
        self.source = source
    
    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path) == self.source.file_path:
            asyncio.create_task(self.source._notify())


class DatabaseConfigSource(ConfigSource):
    """Database configuration source (PostgreSQL/SQLite)."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    async def load(self) -> dict:
        # Implementation depends on schema
        # SELECT key, value FROM config WHERE node_id = ? OR node_id IS NULL
        return {}
    
    async def watch(self, callback: Callable[[], Awaitable[None]]) -> str:
        # Could use PostgreSQL LISTEN/NOTIFY
        return "db-watch"
    
    async def unwatch(self, watch_id: str) -> None:
        pass


class ConfigService:
    """
    Configuration service with multi-source loading, validation, and hot reload.
    
    Sources (priority order - last wins):
    1. Defaults (lowest)
    2. JSON files (config/json/)
    3. YAML files (config/yaml/)
    4. Database
    4. Environment variables (highest)
    """
    
    def __init__(self, config_root: Path = Path("/etc/openj5")):
        self.config_root = config_root
        self.sources: list[tuple[int, ConfigSource]] = []  # (priority, source)
        self.config: dict = {}
        self.schemas: dict[str, dict] = {}
        self.watchers: dict[str, list[Callable[[str, Any], Awaitable[None]]]] = {}
        self._lock = asyncio.Lock()
    
    def add_source(self, source: ConfigSource, priority: int = 0) -> None:
        """Add configuration source. Higher priority = loaded later (overrides)."""
        self.sources.append((priority, source))
        self.sources.sort(key=lambda x: x[0])
    
    def register_schema(self, name: str, schema: dict) -> None:
        """Register JSON schema for validation."""
        self.schemas[name] = schema
    
    async def load(self) -> dict:
        """Load and merge all configuration sources."""
        merged = {}
        
        for _, source in self.sources:
            source_config = await source.load()
            merged = self._deep_merge(merged, source_config)
        
        # Validate against schemas
        for name, schema in self.schemas.items():
            if name in merged:
                try:
                    validate(instance=merged[name], schema=schema)
                except ValidationError as e:
                    logger.error(f"Config validation failed for {name}: {e}")
                    # Don't fail - log and continue with previous config
        
        old_config = self.config
        self.config = merged
        
        # Notify watchers of changes
        await self._notify_changes(old_config, merged)
        
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
    
    async def _notify_changes(self, old: dict, new: dict) -> None:
        """Notify watchers of specific key changes."""
        changes = self._diff(old, new)
        for path, value in changes.items():
            await self._notify_watchers(path, value)
    
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
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_section(self, section: str) -> dict:
        """Get entire config section."""
        return self.config.get(section, {})
    
    def set(self, key: str, value: Any, persist: bool = False) -> bool:
        """Set config value at runtime (not persisted unless persist=True)."""
        keys = key.split(".")
        target = self.config
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value
        
        if persist:
            # TODO: Persist to file/database
            pass
        
        asyncio.create_task(self._notify_watchers(key, value))
        return True
    
    def watch(self, key: str, callback: Callable[[str, Any], Awaitable[None]]) -> str:
        """Watch config key for changes."""
        if key not in self.watchers:
            self.watchers[key] = []
        self.watchers[key].append(callback)
        return key
    
    def unwatch(self, key: str, callback: Callable = None) -> bool:
        """Stop watching config key."""
        if key in self.watchers:
            if callback:
                self.watchers[key].remove(callback)
            else:
                self.watchers[key].clear()
            return True
        return False
    
    async def _notify_watchers(self, key: str, value: Any) -> None:
        """Notify all watchers of a key change."""
        # Exact match
        for callback in self.watchers.get(key, []):
            try:
                await callback(key, value)
            except Exception as e:
                logger.error(f"Config watcher callback failed for {key}: {e}")
        
        # Prefix match (e.g., watch "node2" gets notified for "node2.servos.neck_yaw")
        for watch_key, callbacks in self.watchers.items():
            if key.startswith(watch_key + ".") or watch_key.startswith(key + "."):
                for callback in callbacks:
                    try:
                        await callback(key, value)
                    except Exception as e:
                        logger.error(f"Config watcher callback failed: {e}")
    
    def export(self) -> dict:
        """Export full configuration."""
        return self.config.copy()


# Global config service instance
_config_service: ConfigService | None = None


async def get_config_service(config_root: Path = Path("/etc/openj5")) -> ConfigService:
    """Get or create global config service."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService(config_root)
        
        # Add default sources in priority order
        _config_service.add_source(EnvConfigSource(), priority=100)
        
        # Database (if configured)
        # _config_service.add_source(DatabaseConfigSource(db_pool), priority=50)
        
        # YAML files
        yaml_dir = config_root / "yaml"
        if yaml_dir.exists():
            for yaml_file in yaml_dir.glob("*.yaml"):
                _config_service.add_source(FileConfigSource(yaml_file), priority=20)
        
        # JSON files
        json_dir = config_root / "json"
        if json_dir.exists():
            for json_file in json_dir.glob("*.json"):
                _config_service.add_source(FileConfigSource(json_file), priority=10)
        
        # Load initial configuration
        await _config_service.load()
    
    return _config_service