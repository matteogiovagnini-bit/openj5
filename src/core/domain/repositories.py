"""
OpenJ5 Core Domain - Repository Interfaces (Ports)
"""
from __future__ import annotations
from abc import abstractmethod
from typing import Any, AsyncIterator, Protocol, TypeVar
from dataclasses import dataclass

from .entities import Robot, Node, Servo, Motor, Plugin, Calibration
from .value_objects import (
    NodeIdentity, NodeState, NodeHealth, CalibrationData,
    PluginMetadata
)
from .commands import Result

T = TypeVar('T')


# === BASE REPOSITORY ===

class IRepository(Protocol[T]):
    """Base repository interface."""

    @abstractmethod
    async def get_by_id(self, id: str) -> Result[T]: ...

    @abstractmethod
    async def save(self, entity: T) -> Result[T]: ...

    @abstractmethod
    async def delete(self, id: str) -> Result[bool]: ...

    @abstractmethod
    async def exists(self, id: str) -> bool: ...


# === SPECIFIC REPOSITORIES ===

class IRobotRepository(IRepository[Robot], Protocol):
    """Robot aggregate repository."""

    @abstractmethod
    async def get_current_robot(self) -> Result[Robot]: ...

    @abstractmethod
    async def get_robot_history(self, limit: int = 100) -> Result[list[Robot]]: ...


class INodeRepository(IRepository[Node], Protocol):
    """Node repository."""

    @abstractmethod
    async def get_by_identity(self, identity: NodeIdentity) -> Result[Node]: ...

    @abstractmethod
    async def get_all_nodes(self) -> Result[list[Node]]: ...

    @abstractmethod
    async def get_nodes_by_type(self, node_type: str) -> Result[list[Node]]: ...

    @abstractmethod
    async def update_state(self, node_id: str, state: NodeState) -> Result[bool]: ...

    @abstractmethod
    async def update_last_seen(self, node_id: str, timestamp: float) -> Result[bool]: ...

    @abstractmethod
    async def update_health(self, node_id: str, health: NodeHealth) -> Result[bool]: ...


class IServoRepository(IRepository[Servo], Protocol):
    """Servo repository."""

    @abstractmethod
    async def get_by_node(self, node_id: str) -> Result[list[Servo]]: ...

    @abstractmethod
    async def get_by_name(self, node_id: str, servo_name: str) -> Result[Servo]: ...

    @abstractmethod
    async def update_calibration(self, servo_id: str, calibration: CalibrationData) -> Result[bool]: ...

    @abstractmethod
    async def update_position(self, servo_id: str, position: float) -> Result[bool]: ...

    @abstractmethod
    async def update_target(self, servo_id: str, target: float) -> Result[bool]: ...


class IMotorRepository(IRepository[Motor], Protocol):
    """Motor repository."""

    @abstractmethod
    async def get_by_node(self, node_id: str) -> Result[list[Motor]]: ...

    @abstractmethod
    async def update_odometry(
        self, motor_id: str, position: float, velocity: float
    ) -> Result[bool]: ...

    @abstractmethod
    async def update_target_velocity(self, motor_id: str, velocity: float) -> Result[bool]: ...


class IPluginRepository(IRepository[Plugin], Protocol):
    """Plugin repository."""

    @abstractmethod
    async def get_enabled_plugins(self) -> Result[list[Plugin]]: ...

    @abstractmethod
    async def get_by_metadata(self, metadata: PluginMetadata) -> Result[Plugin]: ...

    @abstractmethod
    async def update_state(self, plugin_id: str, state: str) -> Result[bool]: ...

    @abstractmethod
    async def update_config(self, plugin_id: str, config: dict) -> Result[bool]: ...


class ICalibrationRepository(IRepository[Calibration], Protocol):
    """Calibration repository."""

    @abstractmethod
    async def get_by_node(self, node_id: str) -> Result[list[Calibration]]: ...

    @abstractmethod
    async def get_latest(self, node_id: str, component: str) -> Result[Calibration]: ...

    @abstractmethod
    async def get_by_component(self, node_id: str, component: str) -> Result[list[Calibration]]: ...


# === EVENT STORE (Event Sourcing) ===

class IEventStore(Protocol):
    """Event store for event sourcing."""

    @abstractmethod
    async def append(self, event: Any) -> Result[str]: ...

    @abstractmethod
    async def get_events(
        self,
        aggregate_id: str,
        from_version: int = 0
    ) -> AsyncIterator[Any]: ...

    @abstractmethod
    async def get_events_by_type(
        self,
        event_type: str,
        from_timestamp: float = 0,
        limit: int = 1000
    ) -> AsyncIterator[Any]: ...

    @abstractmethod
    async def get_events_by_correlation(
        self,
        correlation_id: str
    ) -> AsyncIterator[Any]: ...

    @abstractmethod
    async def get_events_by_node(
        self,
        node_id: str,
        from_timestamp: float = 0
    ) -> AsyncIterator[Any]: ...


# === CONFIG REPOSITORY ===

class IConfigRepository(Protocol):
    """Configuration repository - abstracts JSON/YAML/DB/Config Service."""

    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    async def set(self, key: str, value: Any, persist: bool = True) -> Result[bool]: ...

    @abstractmethod
    async def get_schema(self, config_name: str) -> dict: ...

    @abstractmethod
    async def validate(self, config_name: str, data: dict) -> Result[dict]: ...

    @abstractmethod
    async def watch(self, key: str, callback: callable) -> str: ...

    @abstractmethod
    async def unwatch(self, watch_id: str) -> Result[bool]: ...

    @abstractmethod
    async def reload(self) -> Result[bool]: ...


# === UNIT OF WORK ===

@dataclass
class UnitOfWorkConfig:
    """UoW configuration."""
    read_only: bool = False
    timeout: float = 30.0


class IUnitOfWork(Protocol):
    """Unit of Work for transactional consistency."""

    robot: IRobotRepository
    nodes: INodeRepository
    servos: IServoRepository
    motors: IMotorRepository
    plugins: IPluginRepository
    calibrations: ICalibrationRepository
    events: IEventStore
    config: IConfigRepository

    @abstractmethod
    async def __aenter__(self) -> IUnitOfWork: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    async def commit(self) -> Result[bool]: ...

    @abstractmethod
    async def rollback(self) -> Result[bool]: ...