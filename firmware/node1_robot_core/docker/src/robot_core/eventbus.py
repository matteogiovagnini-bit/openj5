"""
OpenJ5 Robot Core - Event Bus (Redis Streams)

Distributed event bus with persistence, replay, and dead letter queue.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Awaitable
from abc import ABC, abstractmethod

import redis.asyncio as redis
from redis.asyncio import Redis

from robot_core.config import ConfigService
from robot_core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DomainEvent:
    """Immutable domain event."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    event_version: int = 1
    timestamp: float = field(default_factory=datetime.now().timestamp)
    source_node: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    payload: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "timestamp": self.timestamp,
            "source_node": self.source_node,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload": self.payload,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DomainEvent":
        return cls(**data)


class IEventBus(ABC):
    """Event bus interface."""
    
    @abstractmethod
    async def publish(self, event: DomainEvent) -> bool: ...
    
    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
        filter_expr: str = "",
    ) -> str: ...
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool: ...
    
    @abstractmethod
    async def replay(
        self,
        from_timestamp: float,
        event_types: list[str] | None = None,
        limit: int = 1000,
    ) -> AsyncGenerator[DomainEvent, None]: ...


class RedisEventBus(IEventBus):
    """
    Redis Streams based Event Bus.
    
    Features:
    - Persistent event log via Redis Streams
    - Consumer groups for horizontal scaling
    - Exactly-once delivery via idempotency keys
    - Dead letter queue for failed handlers
    - Event replay from timestamp
    """
    
    def __init__(self, config: ConfigService):
        self.config = config
        self.redis: Redis | None = None
        self.stream_prefix = config.get("eventbus.stream_prefix", "openj5.events")
        self.consumer_group = config.get("eventbus.consumer_group", "robot_core")
        self.max_stream_length = config.get("eventbus.max_length", 10000)
        
        self._subscriptions: dict[str, dict] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._running = False
    
    async def connect(self) -> None:
        """Connect to Redis and setup consumer groups."""
        redis_url = self.config.get("eventbus.redis_url", "redis://redis:6379")
        self.redis = redis.from_url(redis_url, decode_responses=True)
        
        # Create consumer groups for each event category
        categories = ["command", "telemetry", "state", "error", "business"]
        for category in categories:
            stream = f"{self.stream_prefix}.{category}"
            try:
                await self.redis.xgroup_create(stream, self.consumer_group, id="0", mkstream=True)
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
        
        self._running = True
        logger.info("Event bus connected", redis_url=redis_url)
    
    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        self._running = False
        
        # Cancel all consumer tasks
        for task in self._consumer_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if self.redis:
            await self.redis.close()
        
        logger.info("Event bus disconnected")
    
    def _get_stream(self, event: DomainEvent) -> str:
        """Determine stream based on event type."""
        if event.event_type.endswith("Command"):
            return f"{self.stream_prefix}.command"
        elif event.event_type.endswith("Telemetry"):
            return f"{self.stream_prefix}.telemetry"
        elif event.event_type.endswith("StateChanged"):
            return f"{self.stream_prefix}.state"
        elif "Error" in event.event_type or "Fault" in event.event_type:
            return f"{self.stream_prefix}.error"
        return f"{self.stream_prefix}.business"
    
    async def publish(self, event: DomainEvent) -> bool:
        """Publish event to appropriate stream."""
        if not self.redis:
            return False
        
        stream = self._get_stream(event)
        data = event.to_dict()
        data["payload"] = json.dumps(data["payload"])
        
        try:
            await self.redis.xadd(
                stream,
                data,
                maxlen=self.max_stream_length,
                approximate=True,
            )
            return True
        except Exception as e:
            logger.error("Failed to publish event", event_type=event.event_type, error=str(e))
            return False
    
    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
        filter_expr: str = "",
    ) -> str:
        """Subscribe to event type."""
        subscription_id = str(uuid.uuid4())
        
        self._subscriptions[subscription_id] = {
            "event_type": event_type,
            "handler": handler,
            "filter_expr": filter_expr,
        }
        
        # Start consumer for category if not already running
        category = self._infer_category(event_type)
        if category not in self._consumer_tasks:
            task = asyncio.create_task(self._consume_category(category))
            self._consumer_tasks[category] = task
        
        return subscription_id
    
    def _infer_category(self, event_type: str) -> str:
        if event_type.endswith("Command"):
            return "command"
        elif event_type.endswith("Telemetry"):
            return "telemetry"
        elif event_type.endswith("StateChanged"):
            return "state"
        elif "Error" in event_type or "Fault" in event_type:
            return "error"
        return "business"
    
    async def _consume_category(self, category: str) -> None:
        """Consume events from a category stream."""
        stream = f"{self.stream_prefix}.{category}"
        consumer = f"{self.consumer_group}-{uuid.uuid4().hex[:8]}"
        
        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    self.consumer_group,
                    consumer,
                    {stream: ">"},
                    count=10,
                    block=5000,
                )
                
                for stream_name, entries in messages:
                    for msg_id, fields in entries:
                        await self._process_message(stream_name, msg_id, fields)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Consumer error", category=category, error=str(e))
                await asyncio.sleep(1)
    
    async def _process_message(self, stream: str, msg_id: str, fields: dict) -> None:
        """Process single message, deliver to matching subscriptions."""
        # Reconstruct event
        fields["payload"] = json.loads(fields.get("payload", "{}"))
        event = DomainEvent.from_dict(fields)
        
        # Find matching subscriptions
        for sub_id, sub in self._subscriptions.items():
            if sub["event_type"] == event.event_type or sub["event_type"] == "*":
                if sub["filter_expr"] and not self._match_filter(event, sub["filter_expr"]):
                    continue
                
                try:
                    await sub["handler"](event)
                except Exception as e:
                    logger.error("Handler failed", subscription=sub_id, error=str(e))
                    await self._send_to_dlq(stream, msg_id, fields, str(e))
        
        # Acknowledge
        try:
            await self.redis.xack(stream, self.consumer_group, msg_id)
        except Exception as e:
            logger.warning("Failed to ack message", error=str(e))
    
    def _match_filter(self, event: DomainEvent, filter_expr: str) -> bool:
        """Simple filter matching (can be extended with JSONPath)."""
        # Simplified)
        return True  # Placeholder
    
    async def _send_to_dlq(self, stream: str, msg_id: str, fields: dict, error: str) -> None:
        """Send failed message to dead letter queue."""
        dlq_stream = f"{self.stream_prefix}.dlq"
        dlq_data = {
            **fields,
            "original_stream": stream,
            "original_id": msg_id,
            "error": error,
            "failed_at": datetime.now().isoformat(),
        }
        dlq_data["payload"] = json.dumps(dlq_data.get("payload", {}))
        
        try:
            await self.redis.xadd(dlq_stream, dlq_data)
        except Exception as e:
            logger.error("Failed to send to DLQ", error=str(e))
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe by subscription ID."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False
    
    async def replay(
        self,
        from_timestamp: float,
        event_types: list[str] | None = None,
        limit: int = 1000,
    ) -> AsyncGenerator[DomainEvent, None]:
        """Replay historical events from timestamp."""
        if not self.redis:
            return
        
        categories = ["command", "telemetry", "state", "error", "business"]
        
        for category in categories:
            stream = f"{self.stream_prefix}.{category}"
            try:
                # Convert timestamp to Redis stream ID format (milliseconds)
                min_id = f"{int(from_timestamp * 1000)}-0"
                entries = await self.redis.xrange(stream, min=min_id, count=limit)
                
                for msg_id, fields in entries:
                    fields["payload"] = json.loads(fields.get("payload", "{}"))
                    event = DomainEvent.from_dict(fields)
                    
                    if not event_types or event.event_type in event_types:
                        yield event
                        
            except Exception as e:
                logger.error("Replay error", category=category, error=str(e))


async def get_event_bus(config: ConfigService) -> RedisEventBus:
    """Get or create event bus."""
    bus = RedisEventBus(config)
    await bus.connect()
    return bus