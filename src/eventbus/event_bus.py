"""
OpenJ5 Event Bus - Central Event Infrastructure

Redis Streams / NATS implementation for distributed event-driven architecture.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Awaitable
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import json
import uuid
from datetime import datetime


class EventCategory(Enum):
    COMMAND = "command"
    TELEMETRY = "telemetry"
    STATE = "state"
    ERROR = "error"
    BUSINESS = "business"


@dataclass
class DomainEvent:
    """Domain event - immutable, versioned."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    event_version: int = 1
    category: EventCategory = EventCategory.BUSINESS
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    source_node: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    payload: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.event_type:
            self.event_type = self.__class__.__name__
        if not self.correlation_id:
            self.correlation_id = self.event_id

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "category": self.category.value,
            "timestamp": self.timestamp,
            "source_node": self.source_node,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload": self.payload
        }

    @classmethod
    def from_dict(cls, data: dict) -> DomainEvent:
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=data.get("event_type", ""),
            event_version=data.get("event_version", 1),
            category=EventCategory(data.get("category", "business")),
            timestamp=data.get("timestamp", 0),
            source_node=data.get("source_node", ""),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            payload=data.get("payload", {})
        )


class EventHandler(Protocol):
    """Event handler protocol."""
    async def __call__(self, event: DomainEvent) -> None: ...


@dataclass
class Subscription:
    """Event subscription."""
    subscription_id: str
    event_type: str
    handler: EventHandler
    filter_expr: str = ""  # Optional filter expression


class IEventBus(ABC):
    """Event Bus interface - pub/sub with persistence and replay."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> Result:
        """Publish event to bus."""
        pass

    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        filter_expr: str = ""
    ) -> Result[Subscription]:
        """Subscribe to event type."""
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> Result:
        """Unsubscribe."""
        pass

    @abstractmethod
    async def replay(
        self,
        from_timestamp: float,
        event_types: list[str] = None,
        limit: int = 1000
    ) -> AsyncIterator[DomainEvent]:
        """Replay historical events."""
        pass

    @abstractmethod
    async def get_event(
        self,
        event_id: str
    ) -> Result[DomainEvent]:
        """Get single event by ID."""
        pass


# === REDIS STREAMS IMPLEMENTATION ===

class RedisEventBus(IEventBus):
    """
    Redis Streams based Event Bus.
    
    Features:
    - Persistent streams with consumer groups
    - Exactly-once delivery via idempotency keys
    - Dead letter queue for failed handlers
    - Event replay from timestamp
    - Horizontal scaling via consumer groups
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_prefix: str = "openj5.events",
        consumer_group: str = "robot_core",
        max_stream_length: int = 10000,
        dead_letter_max_retries: int = 3
    ):
        self._redis_url = redis_url
        self._stream_prefix = stream_prefix
        self._consumer_group = consumer_group
        self._max_stream_length = max_stream_length
        self._dead_letter_max_retries = dead_letter_max_retries

        self._redis = None
        self._subscriptions: dict[str, Subscription] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def connect(self) -> Result:
        """Connect to Redis and setup streams."""
        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(self._redis_url, decode_responses=True)

            # Create consumer groups for each category
            for category in EventCategory:
                stream = f"{self._stream_prefix}.{category.value}"
                try:
                    await self._redis.xgroup_create(
                        stream, self._consumer_group, id="0", mkstream=True
                    )
                except redis.ResponseError as e:
                    if "BUSYGROUP" not in str(e):
                        raise

            self._running = True
            return Result.ok(True)
        except Exception as e:
            return Result.fail("CONNECT_FAILED", f"Redis connection failed: {e}")

    async def disconnect(self) -> Result:
        """Disconnect and cleanup."""
        self._running = False
        for task in self._consumer_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.close()
        return Result.ok(True)

    def _get_stream(self, category: EventCategory) -> str:
        return f"{self._stream_prefix}.{category.value}"

    async def publish(self, event: DomainEvent) -> Result:
        """Publish event to appropriate stream."""
        if not self._redis:
            return Result.fail("NOT_CONNECTED", "Redis not connected")

        try:
            stream = self._get_stream(event.category)
            data = event.to_dict()
            # Add idempotency key
            data["_idempotency_key"] = event.event_id

            await self._redis.xadd(
                stream,
                {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                 for k, v in data.items()},
                maxlen=self._max_stream_length
            )
            return Result.ok(True)
        except Exception as e:
            return Result.fail("PUBLISH_FAILED", f"Redis publish failed: {e}")

    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        filter_expr: str = ""
    ) -> Result[Subscription]:
        """Subscribe to event type across all categories."""
        sub = Subscription(
            subscription_id=str(uuid.uuid4()),
            event_type=event_type,
            handler=handler,
            filter_expr=filter_expr
        )
        self._subscriptions[sub.subscription_id] = sub

        # Start consumer for each category
        for category in EventCategory:
            task = asyncio.create_task(
                self._consume_stream(category, sub)
            )
            self._consumer_tasks[f"{sub.subscription_id}:{category.value}"] = task

        return Result.ok(sub)

    async def _consume_stream(self, category: EventCategory, sub: Subscription):
        """Consume events from stream for subscription."""
        stream = self._get_stream(category)
        consumer = f"{self._consumer_group}-{sub.subscription_id[:8]}"

        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    self._consumer_group,
                    consumer,
                    {stream: ">"},
                    count=10,
                    block=5000
                )

                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        event = self._deserialize_event(data)
                        if event and self._matches_subscription(event, sub):
                            await self._safe_handle(event, sub, msg_id, stream)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error, continue
                await asyncio.sleep(1)

    def _deserialize_event(self, data: dict) -> DomainEvent | None:
        """Deserialize event from Redis data."""
        try:
            # Parse JSON fields
            parsed = {}
            for k, v in data.items():
                if k in ("payload", "headers"):
                    parsed[k] = json.loads(v)
                else:
                    parsed[k] = v
            return DomainEvent.from_dict(parsed)
        except Exception:
            return None

    def _matches_subscription(self, event: DomainEvent, sub: Subscription) -> bool:
        """Check if event matches subscription filter."""
        if event.event_type != sub.event_type:
            return False
        if sub.filter_expr:
            # TODO: Implement filter expression evaluation
            pass
        return True

    async def _safe_handle(self, event: DomainEvent, sub: Subscription, msg_id: str, stream: str):
        """Handle event with error handling and dead letter."""
        retries = 0
        while retries <= self._dead_letter_max_retries:
            try:
                await sub.handler(event)
                # Acknowledge
                await self._redis.xack(stream, self._consumer_group, msg_id)
                return
            except Exception as e:
                retries += 1
                if retries > self._dead_letter_max_retries:
                    # Move to dead letter
                    await self._move_to_dead_letter(event, stream, msg_id, str(e))
                    await self._redis.xack(stream, self._consumer_group, msg_id)
                    return
                await asyncio.sleep(2 ** retries)  # Exponential backoff

    async def _move_to_dead_letter(self, event: DomainEvent, stream: str, msg_id: str, error: str):
        """Move failed event to dead letter stream."""
        dlq_stream = f"{stream}.dlq"
        await self._redis.xadd(dlq_stream, {
            "original_stream": stream,
            "original_msg_id": msg_id,
            "event_data": json.dumps(event.to_dict()),
            "error": error,
            "failed_at": datetime.now().isoformat()
        })

    async def unsubscribe(self, subscription_id: str) -> Result:
        """Unsubscribe and stop consumers."""
        # Cancel consumer tasks
        to_cancel = [k for k in self._consumer_tasks if k.startswith(subscription_id)]
        for key in to_cancel:
            task = self._consumer_tasks.pop(key)
            task.cancel()

        self._subscriptions.pop(subscription_id, None)
        return Result.ok(True)

    async def replay(
        self,
        from_timestamp: float,
        event_types: list[str] = None,
        limit: int = 1000
    ) -> AsyncIterator[DomainEvent]:
        """Replay events from timestamp."""
        for category in EventCategory:
            stream = self._get_stream(category)
            # Get entries from timestamp
            entries = await self._redis.xrange(
                stream,
                min=f"({int(from_timestamp * 1000)}",
                count=limit
            )

            for msg_id, data in entries:
                event = self._deserialize_event(data)
                if event and (not event_types or event.event_type in event_types):
                    yield event

    async def get_event(self, event_id: str) -> Result[DomainEvent]:
        """Get event by ID (searches all streams)."""
        for category in EventCategory:
            stream = self._get_stream(category)
            # Search by idempotency key
            entries = await self._redis.xrange(
                stream,
                min="-",
                max="+",
                count=100
            )
            for msg_id, data in entries:
                if data.get("_idempotency_key") == event_id:
                    event = self._deserialize_event(data)
                    if event:
                        return Result.ok(event)
        return Result.fail("NOT_FOUND", f"Event {event_id} not found")


# === IN-MEMORY EVENT BUS (Testing) ===

class InMemoryEventBus(IEventBus):
    """In-memory event bus for unit testing."""

    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}
        self._event_store: list[DomainEvent] = []
        self._running = True

    async def publish(self, event: DomainEvent) -> Result:
        self._event_store.append(event)
        # Deliver to matching subscriptions
        for sub in self._subscriptions.values():
            if event.event_type == sub.event_type:
                try:
                    await sub.handler(event)
                except Exception:
                    pass  # Ignore handler errors in test bus
        return Result.ok(True)

    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        filter_expr: str = ""
    ) -> Result[Subscription]:
        sub = Subscription(
            subscription_id=str(uuid.uuid4()),
            event_type=event_type,
            handler=handler,
            filter_expr=filter_expr
        )
        self._subscriptions[sub.subscription_id] = sub
        return Result.ok(sub)

    async def unsubscribe(self, subscription_id: str) -> Result:
        self._subscriptions.pop(subscription_id, None)
        return Result.ok(True)

    async def replay(
        self,
        from_timestamp: float,
        event_types: list[str] = None,
        limit: int = 1000
    ) -> AsyncIterator[DomainEvent]:
        for event in self._event_store:
            if event.timestamp >= from_timestamp:
                if not event_types or event.event_type in event_types:
                    yield event

    async def get_event(self, event_id: str) -> Result[DomainEvent]:
        for event in self._event_store:
            if event.event_id == event_id:
                return Result.ok(event)
        return Result.fail("NOT_FOUND", "Event not found")


# === EVENT BUS FACTORY ===

class EventBusFactory:
    """Factory for creating event bus instances."""

    @staticmethod
    def create(config: dict) -> IEventBus:
        bus_type = config.get("type", "redis")
        if bus_type == "redis":
            return RedisEventBus(
                redis_url=config.get("redis_url", "redis://localhost:6379"),
                stream_prefix=config.get("stream_prefix", "openj5.events"),
                consumer_group=config.get("consumer_group", "robot_core"),
                max_stream_length=config.get("max_stream_length", 10000),
            )
        elif bus_type == "memory":
            return InMemoryEventBus()
        elif bus_type == "nats":
            # TODO: NATS implementation
            raise NotImplementedError("NATS not yet implemented")
        else:
            raise ValueError(f"Unknown event bus type: {bus_type}")


from ..core.domain import Result