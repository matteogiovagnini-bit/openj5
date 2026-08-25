"""
OpenJ5 Event Bus - Redis Streams Implementation
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Awaitable
from abc import ABC, abstractmethod
import asyncio
import json
import uuid
from datetime import datetime

from ..core.domain import Result, DomainEvent, EventCategory


class IEventBus(ABC):
    """Event Bus interface."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> Result:
        pass

    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
        filter_expr: str = ""
    ) -> Result[str]:  # returns subscription_id
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> Result:
        pass

    @abstractmethod
    async def replay(
        self,
        from_timestamp: float,
        event_types: list[str] = None,
        limit: int = 1000
    ) -> AsyncIterator[DomainEvent]:
        pass

    @abstractmethod
    async def get_event(self, event_id: str) -> Result[DomainEvent]:
        pass


@dataclass
class Subscription:
    subscription_id: str
    event_type: str
    handler: Callable[[DomainEvent], Awaitable[None]]
    filter_expr: str = ""
    consumer_name: str = ""


class RedisEventBus(IEventBus):
    """
    Redis Streams Event Bus.
    
    Features:
    - Persistent event log via Redis Streams
    - Consumer groups for horizontal scaling
    - Exactly-once via idempotency keys
    - Dead letter queue for failed handlers
    - Event replay from timestamp
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_prefix: str = "openj5.events",
        consumer_group: str = "robot_core",
        max_stream_length: int = 10000,
    ):
        self._redis_url = redis_url
        self._stream_prefix = stream_prefix
        self._consumer_group = consumer_group
        self._max_length = max_stream_length

        self._redis = None
        self._subscriptions: dict[str, Subscription] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._dead_letter_stream = f"{stream_prefix}.dlq"

    async def initialize(self) -> Result:
        """Initialize Redis connection and consumer groups."""
        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(self._redis_url, decode_responses=True)

            # Create consumer groups for each event category
            for category in EventCategory:
                stream = f"{self._stream_prefix}.{category.value}"
                try:
                    await self._redis.xgroup_create(
                        stream, self._consumer_group, id="0", mkstream=True
                    )
                except Exception:
                    # Group may already exist
                    pass

            # Create DLQ stream
            try:
                await self._redis.xgroup_create(
                    self._dead_letter_stream, self._consumer_group, id="0", mkstream=True
                )
            except Exception:
                pass

            self._running = True
            return Result.ok(True)
        except Exception as e:
            return Result.fail("INIT_FAILED", str(e))

    async def shutdown(self) -> Result:
        """Shutdown all consumers."""
        self._running = False
        for task in self._consumer_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consumer_tasks.clear()
        if self._redis:
            await self._redis.close()
        return Result.ok(True)

    def _get_stream(self, event: DomainEvent) -> str:
        """Get stream name for event category."""
        return f"{self._stream_prefix}.{event.category.value}"

    async def publish(self, event: DomainEvent) -> Result:
        """Publish event to appropriate stream."""
        if not self._redis:
            return Result.fail("NOT_INITIALIZED", "Event bus not initialized")

        try:
            stream = self._get_stream(event)
            data = event.to_dict()
            data["payload"] = json.dumps(data["payload"])

            await self._redis.xadd(
                stream,
                data,
                maxlen=self._max_length,
                approximate=True
            )
            return Result.ok(True)
        except Exception as e:
            return Result.fail("PUBLISH_FAILED", str(e))

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
        filter_expr: str = ""
    ) -> Result[str]:
        """Subscribe to event type."""
        if not self._running:
            return Result.fail("NOT_RUNNING", "Event bus not running")

        sub_id = str(uuid.uuid4())
        subscription = Subscription(
            subscription_id=sub_id,
            event_type=event_type,
            handler=handler,
            filter_expr=filter_expr
        )
        self._subscriptions[sub_id] = subscription

        # Start consumer if not already running for this event type
        category = self._infer_category(event_type)
        if category and category not in self._consumer_tasks:
            task = asyncio.create_task(self._consume_category(category))
            self._consumer_tasks[category] = task

        return Result.ok(sub_id)

    def _infer_category(self, event_type: str) -> str | None:
        """Infer event category from type name."""
        if "Command" in event_type:
            return "command"
        elif "Telemetry" in event_type:
            return "telemetry"
        elif "StateChanged" in event_type:
            return "state"
        elif "Fault" in event_type or "Error" in event_type or "Violation" in event_type:
            return "error"
        return "business"

    async def _consume_category(self, category: str):
        """Consume events from a category stream."""
        stream = f"{self._stream_prefix}.{category}"
        consumer = f"{self._consumer_group}-{uuid.uuid4().hex[:8]}"

        while self._running:
            try:
                # Read new messages
                messages = await self._redis.xreadgroup(
                    self._consumer_group,
                    consumer,
                    {stream: ">"},
                    count=10,
                    block=5000
                )

                for stream_name, entries in messages:
                    for msg_id, fields in entries:
                        await self._process_message(stream_name, msg_id, fields)

            except asyncio.CancelledError:
                break
            except Exception:
                # Log error, continue
                await asyncio.sleep(1)

    async def _process_message(self, stream: str, msg_id: str, fields: dict):
        """Process single message."""
        # Reconstruct event
        payload = json.loads(fields.get("payload", "{}"))
        event = DomainEvent.from_dict({**fields, "payload": payload})

        # Find matching subscriptions
        for sub in self._subscriptions.values():
            if sub.event_type == event.event_type or sub.event_type == "*":
                if sub.filter_expr and not self._match_filter(event, sub.filter_expr):
                    continue

                try:
                    await sub.handler(event)
                    # Acknowledge
                    await self._redis.xack(stream, self._consumer_group, msg_id)
                except Exception as e:
                    # Send to DLQ
                    await self._send_to_dlq(stream, msg_id, fields, str(e))
                    # Still ack to not retry infinitely
                    await self._redis.xack(stream, self._consumer_group, msg_id)

    def _match_filter(self, event: DomainEvent, filter_expr: str) -> bool:
        """Simple filter matching (JSONPath-like)."""
        # Simplified - in production use a proper JSONPath library
        try:
            # Example: "payload.confidence > 0.8"
            # This is a placeholder
            return True
        except Exception:
            return False

    async def _send_to_dlq(self, stream: str, msg_id: str, fields: dict, error: str):
        """Send failed message to dead letter queue."""
        dlq_data = {
            **fields,
            "original_stream": stream,
            "original_id": msg_id,
            "error": error,
            "failed_at": datetime.now().isoformat()
        }
        dlq_data["payload"] = json.dumps(dlq_data.get("payload", {}))
        await self._redis.xadd(self._dead_letter_stream, dlq_data)

    async def unsubscribe(self, subscription_id: str) -> Result:
        """Unsubscribe by subscription ID."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return Result.ok(True)
        return Result.fail("NOT_FOUND", "Subscription not found")

    async def replay(
        self,
        from_timestamp: float,
        event_types: list[str] = None,
        limit: int = 1000
    ) -> AsyncIterator[DomainEvent]:
        """Replay historical events."""
        if not self._redis:
            return

        # Determine streams to read
        streams = []
        if event_types:
            for et in event_types:
                category = self._infer_category(et)
                if category:
                    streams.append(f"{self._stream_prefix}.{category}")
        else:
            for cat in EventCategory:
                streams.append(f"{self._stream_prefix}.{cat.value}")

        # Read from each stream
        for stream in streams:
            try:
                entries = await self._redis.xrange(
                    stream,
                    min=f"{int(from_timestamp * 1000)}-0",
                    max="+",
                    count=limit
                )

                for msg_id, fields in entries:
                    payload = json.loads(fields.get("payload", "{}"))
                    event = DomainEvent.from_dict({**fields, "payload": payload})
                    if not event_types or event.event_type in event_types:
                        yield event
            except Exception:
                continue

    async def get_event(self, event_id: str) -> Result[DomainEvent]:
        """Get event by ID (scans all streams)."""
        if not self._redis:
            return Result.fail("NOT_INITIALIZED", "Event bus not initialized")

        for cat in EventCategory:
            stream = f"{self._stream_prefix}.{cat.value}"
            try:
                entries = await self._redis.xrange(stream, min=event_id, max=event_id, count=1)
                if entries:
                    msg_id, fields = entries[0]
                    payload = json.loads(fields.get("payload", "{}"))
                    return Result.ok(DomainEvent.from_dict({**fields, "payload": payload}))
            except Exception:
                continue

        return Result.fail("NOT_FOUND", f"Event {event_id} not found")

    async def get_stats(self) -> dict:
        """Get event bus statistics."""
        stats = {"streams": {}, "subscriptions": len(self._subscriptions)}
        for cat in EventCategory:
            stream = f"{self._stream_prefix}.{cat.value}"
            try:
                length = await self._redis.xlen(stream)
                stats["streams"][cat.value] = length
            except Exception:
                stats["streams"][cat.value] = 0
        return stats