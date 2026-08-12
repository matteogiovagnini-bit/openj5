"""
OpenJ5 Communication Gateway - Interface & Implementations

Abstracts all communication protocols. Applications use ICommunicationGateway only.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Protocol
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import uuid


class QoS(Enum):
    AT_MOST_ONCE = 0
    AT_LEAST_ONCE = 1
    EXACTLY_ONCE = 2


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class Message:
    """Normalized message across all protocols."""
    topic: str
    payload: dict
    qos: QoS = QoS.AT_LEAST_ONCE
    retain: bool = False
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    timestamp: float = 0.0
    headers: dict = field(default_factory=dict)


@dataclass
class Subscription:
    """Active subscription handle."""
    topic: str
    handler: Callable[[Message], Awaitable[None]]
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    qos: QoS = QoS.AT_LEAST_ONCE


@dataclass
class ServiceCall:
    """Service request."""
    service: str
    request: dict
    timeout: float = 30.0
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ServiceResponse:
    """Service response."""
    success: bool
    data: dict = None
    error_code: str = ""
    error_message: str = ""


class ICommunicationGateway(ABC):
    """
    Abstract communication gateway - single interface for all protocols.
    
    Supported protocols (via implementations):
    - MQTT (Mosquitto/EMQX) - primary
    - ROS 2 (Fast DDS/Cyclone) - ecosystem
    - WebSocket - web UI, teleop
    - Serial - debug, bootstrap
    - BLE - provisioning, mobile
    - CAN - real-time, automotive
    - Zenoh - edge, low latency
    - gRPC - service-to-service
    """

    @property
    @abstractmethod
    def protocol(self) -> str:
        """Protocol identifier: 'mqtt', 'ros2', 'websocket', etc."""
        pass

    @property
    @abstractmethod
    def state(self) -> ConnectionState:
        """Current connection state."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Quick connection check."""
        pass

    # === LIFECYCLE ===

    @abstractmethod
    async def connect(self, config: dict) -> Result:
        """Establish connection with config."""
        pass

    @abstractmethod
    async def disconnect(self) -> Result:
        """Graceful disconnect."""
        pass

    @abstractmethod
    async def reconnect(self) -> Result:
        """Force reconnection."""
        pass

    # === PUB/SUB ===

    @abstractmethod
    async def publish(self, topic: str, payload: dict, qos: QoS = QoS.AT_LEAST_ONCE, retain: bool = False) -> Result:
        """Publish message to topic."""
        pass

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], Awaitable[None]],
        qos: QoS = QoS.AT_LEAST_ONCE
    ) -> Result[Subscription]:
        """Subscribe to topic with async handler."""
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> Result:
        """Unsubscribe by subscription ID."""
        pass

    @abstractmethod
    async def unsubscribe_topic(self, topic: str) -> Result:
        """Unsubscribe all handlers for topic."""
        pass

    # === REQUEST/REPLY ===

    @abstractmethod
    async def request(self, topic: str, payload: dict, timeout: float = 30.0) -> Result[dict]:
        """Request-reply pattern (uses correlation IDs)."""
        pass

    @abstractmethod
    async def register_service(self, service: str, handler: Callable[[dict], Awaitable[dict]]) -> Result:
        """Register request handler for service."""
        pass

    @abstractmethod
    async def call_service(self, service: str, request: dict, timeout: float = 30.0) -> Result[dict]:
        """Call registered service."""
        pass

    # === HEALTH/MONITORING ===

    @abstractmethod
    async def health_check(self) -> Result[dict]:
        """Return gateway health metrics."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict:
        """Return connection statistics."""
        pass


# === MQTT IMPLEMENTATION ===

class MqttGateway(ICommunicationGateway):
    """MQTT implementation using paho-mqtt / aiomqtt."""

    def __init__(self):
        self._client = None
        self._config = {}
        self._subscriptions: dict[str, Subscription] = {}
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._services: dict[str, Callable] = {}
        self._state = ConnectionState.DISCONNECTED
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "reconnects": 0,
        }

    @property
    def protocol(self) -> str:
        return "mqtt"

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    async def connect(self, config: dict) -> Result:
        """Connect to MQTT broker."""
        try:
            import aiomqtt
            self._config = config

            self._state = ConnectionState.CONNECTING

            # Build client config
            client_config = {
                "hostname": config.get("host", "localhost"),
                "port": config.get("port", 8883),
                "username": config.get("username"),
                "password": config.get("password"),
                "keepalive": config.get("keepalive", 60),
                "clean_session": config.get("clean_session", True),
            }

            # TLS
            if config.get("tls", True):
                import ssl
                tls_config = {
                    "ca_certs": config.get("ca_cert"),
                    "certfile": config.get("client_cert"),
                    "keyfile": config.get("client_key"),
                    "cert_reqs": ssl.CERT_REQUIRED,
                    "tls_version": ssl.PROTOCOL_TLS_CLIENT,
                }
                client_config["tls_context"] = ssl.create_default_context(**tls_config)

            # Client ID
            client_config["client_id"] = config.get("client_id", f"openj5-{uuid.uuid4().hex[:8]}")

            # Connect
            self._client = aiomqtt.Client(**client_config)
            await self._client.__aenter__()

            # Start message loop
            asyncio.create_task(self._message_loop())

            self._state = ConnectionState.CONNECTED
            return Result.ok(True)

        except Exception as e:
            self._state = ConnectionState.FAILED
            return Result.fail("CONNECT_FAILED", f"MQTT connect failed: {e}")

    async def _message_loop(self):
        """Process incoming messages."""
        try:
            async for message in self._client.messages:
                await self._handle_message(message)
        except Exception as e:
            self._state = ConnectionState.FAILED
            # TODO: Auto-reconnect
            if self._logger:
                self._logger.error(f"MQTT message loop error: {e}")

    async def _handle_message(self, message):
        """Route incoming message to handler."""
        topic = message.topic.value
        payload = message.payload.decode() if isinstance(message.payload, bytes) else message.payload

        import json
        try:
            payload_dict = json.loads(payload) if isinstance(payload, str) else payload
        except json.JSONDecodeError:
            payload_dict = {"raw": payload}

        msg = Message(topic=topic, payload=payload_dict)

        # Check for service response
        corr_id = payload_dict.get("correlation_id")
        if corr_id and corr_id in self._pending_requests:
            future = self._pending_requests.pop(corr_id)
            future.set_result(payload_dict)
            return

        # Check for service request
        if topic.endswith("/srv/request"):
            service = topic.replace("/srv/request", "")
            if service in self._services:
                try:
                    response = await self._services[service](payload_dict)
                    await self.publish(f"{service}/srv/response", {
                        "correlation_id": corr_id,
                        "success": True,
                        "data": response
                    })
                except Exception as e:
                    await self.publish(f"{service}/srv/response", {
                        "correlation_id": corr_id,
                        "success": False,
                        "error_code": "SERVICE_ERROR",
                        "error_message": str(e)
                    })
            return

        # Route to subscription handler
        for sub in self._subscriptions.values():
            if self._topic_matches(sub.topic, topic):
                try:
                    await sub.handler(msg)
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"Handler error for {topic}: {e}")

        self._stats["messages_received"] += 1

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """MQTT topic matching with wildcards."""
        import fnmatch
        return fnmatch.fnmatch(topic, pattern.replace("+", "*").replace("#", "**"))

    async def disconnect(self) -> Result:
        """Disconnect from broker."""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None
        self._state = ConnectionState.DISCONNECTED
        return Result.ok(True)

    async def reconnect(self) -> Result:
        """Reconnect to broker."""
        await self.disconnect()
        self._stats["reconnects"] += 1
        return await self.connect(self._config)

    async def publish(self, topic: str, payload: dict, qos: QoS = QoS.AT_LEAST_ONCE, retain: bool = False) -> Result:
        if not self._client or self._state != ConnectionState.CONNECTED:
            return Result.fail("NOT_CONNECTED", "MQTT not connected")

        try:
            import json
            await self._client.publish(
                topic,
                json.dumps(payload),
                qos=qos.value,
                retain=retain
            )
            self._stats["messages_sent"] += 1
            return Result.ok(True)
        except Exception as e:
            self._stats["errors"] += 1
            return Result.fail("PUBLISH_FAILED", f"MQTT publish failed: {e}")

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], Awaitable[None]],
        qos: QoS = QoS.AT_LEAST_ONCE
    ) -> Result[Subscription]:
        if not self._client or self._state != ConnectionState.CONNECTED:
            return Result.fail("NOT_CONNECTED", "MQTT not connected")

        try:
            await self._client.subscribe(topic, qos=qos.value)
            sub = Subscription(topic=topic, handler=handler, qos=qos)
            self._subscriptions[sub.subscription_id] = sub
            return Result.ok(sub)
        except Exception as e:
            return Result.fail("SUBSCRIBE_FAILED", f"MQTT subscribe failed: {e}")

    async def unsubscribe(self, subscription_id: str) -> Result:
        sub = self._subscriptions.pop(subscription_id, None)
        if sub:
            await self._client.unsubscribe(sub.topic)
            return Result.ok(True)
        return Result.fail("NOT_FOUND", "Subscription not found")

    async def unsubscribe_topic(self, topic: str) -> Result:
        to_remove = [sid for sid, sub in self._subscriptions.items() if sub.topic == topic]
        for sid in to_remove:
            await self.unsubscribe(sid)
        return Result.ok(True)

    async def request(self, topic: str, payload: dict, timeout: float = 30.0) -> Result[dict]:
        corr_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[corr_id] = future

        request_payload = {**payload, "correlation_id": corr_id}
        await self.publish(f"{topic}/req", request_payload)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return Result.ok(response)
        except asyncio.TimeoutError:
            self._pending_requests.pop(corr_id, None)
            return Result.fail("TIMEOUT", f"Request to {topic} timed out")
        except Exception as e:
            self._pending_requests.pop(corr_id, None)
            return Result.fail("REQUEST_FAILED", str(e))

    async def register_service(self, service: str, handler: Callable[[dict], Awaitable[dict]]) -> Result:
        self._services[service] = handler
        await self.subscribe(f"{service}/srv/request", self._handle_service_request)
        return Result.ok(True)

    async def _handle_service_request(self, message: Message):
        """Handle incoming service request."""
        service = message.topic.replace("/srv/request", "")
        if service in self._services:
            try:
                result = await self._services[service](message.payload)
                await self.publish(f"{service}/srv/response", {
                    "correlation_id": message.correlation_id,
                    "success": True,
                    "data": result
                })
            except Exception as e:
                await self.publish(f"{service}/srv/response", {
                    "correlation_id": message.correlation_id,
                    "success": False,
                    "error_code": "SERVICE_ERROR",
                    "error_message": str(e)
                })

    async def call_service(self, service: str, request: dict, timeout: float = 30.0) -> Result[dict]:
        return await self.request(f"{service}/srv", request, timeout)

    async def health_check(self) -> Result[dict]:
        return Result.ok({
            "protocol": self.protocol,
            "state": self.state.value,
            "connected": self.is_connected,
            **self._stats
        })

    async def get_stats(self) -> dict:
        return self._stats.copy()


# === GATEWAY FACTORY ===

class GatewayFactory:
    """Factory for creating communication gateway instances."""

    _implementations: dict[str, type[ICommunicationGateway]] = {
        "mqtt": MqttGateway,
        # "ros2": Ros2Gateway,
        # "websocket": WebSocketGateway,
        # "serial": SerialGateway,
        # "ble": BleGateway,
        # "can": CanGateway,
        # "zenoh": ZenohGateway,
        # "grpc": GrpcGateway,
    }

    @classmethod
    def register(cls, protocol: str, impl: type[ICommunicationGateway]):
        cls._implementations[protocol] = impl

    @classmethod
    def create(cls, protocol: str) -> ICommunicationGateway:
        impl = cls._implementations.get(protocol)
        if not impl:
            raise ValueError(f"Unknown protocol: {protocol}")
        return impl()

    @classmethod
    def available_protocols(cls) -> list[str]:
        return list(cls._implementations.keys())


# === MULTI-PROTOCOL GATEWAY (Router) ===

class MultiProtocolGateway(ICommunicationGateway):
    """
    Router that manages multiple protocol gateways.
    Routes messages based on topic prefix or explicit routing config.
    """

    def __init__(self):
        self._gateways: dict[str, ICommunicationGateway] = {}
        self._default_protocol = "mqtt"
        self._topic_routes: dict[str, str] = {}  # topic_prefix -> protocol

    def add_gateway(self, protocol: str, gateway: ICommunicationGateway):
        self._gateways[protocol] = gateway

    def set_default(self, protocol: str):
        self._default_protocol = protocol

    def route_topic(self, topic_prefix: str, protocol: str):
        self._topic_routes[topic_prefix] = protocol

    def _get_gateway(self, topic: str) -> ICommunicationGateway:
        # Check explicit routes
        for prefix, protocol in self._topic_routes.items():
            if topic.startswith(prefix):
                return self._gateways.get(protocol)

        # Default
        return self._gateways.get(self._default_protocol)

    @property
    def protocol(self) -> str:
        return "multi"

    @property
    def state(self) -> ConnectionState:
        # Return worst state
        for gw in self._gateways.values():
            if gw.state == ConnectionState.FAILED:
                return ConnectionState.FAILED
        for gw in self._gateways.values():
            if gw.state == ConnectionState.CONNECTING:
                return ConnectionState.CONNECTING
        return ConnectionState.CONNECTED

    @property
    def is_connected(self) -> bool:
        return any(gw.is_connected for gw in self._gateways.values())

    async def connect(self, config: dict) -> Result:
        results = []
        for protocol, gw_config in config.items():
            if protocol in self._gateways:
                result = await self._gateways[protocol].connect(gw_config)
                results.append(result)

        if all(r.success for r in results):
            return Result.ok(True)
        return Result.fail("PARTIAL_CONNECT", "Some gateways failed to connect")

    async def disconnect(self) -> Result:
        for gw in self._gateways.values():
            await gw.disconnect()
        return Result.ok(True)

    async def reconnect(self) -> Result:
        for gw in self._gateways.values():
            await gw.reconnect()
        return Result.ok(True)

    async def publish(self, topic: str, payload: dict, qos: QoS = QoS.AT_LEAST_ONCE, retain: bool = False) -> Result:
        gw = self._get_gateway(topic)
        if not gw:
            return Result.fail("NO_GATEWAY", f"No gateway for topic {topic}")
        return await gw.publish(topic, payload, qos, retain)

    async def subscribe(self, topic: str, handler, qos: QoS = QoS.AT_LEAST_ONCE) -> Result[Subscription]:
        gw = self._get_gateway(topic)
        if not gw:
            return Result.fail("NO_GATEWAY", f"No gateway for topic {topic}")
        return await gw.subscribe(topic, handler, qos)

    async def unsubscribe(self, subscription_id: str) -> Result:
        for gw in self._gateways.values():
            result = await gw.unsubscribe(subscription_id)
            if result.success:
                return result
        return Result.fail("NOT_FOUND", "Subscription not found")

    async def unsubscribe_topic(self, topic: str) -> Result:
        for gw in self._gateways.values():
            await gw.unsubscribe_topic(topic)
        return Result.ok(True)

    async def request(self, topic: str, payload: dict, timeout: float = 30.0) -> Result[dict]:
        gw = self._get_gateway(topic)
        if not gw:
            return Result.fail("NO_GATEWAY", f"No gateway for topic {topic}")
        return await gw.request(topic, payload, timeout)

    async def register_service(self, service: str, handler) -> Result:
        for gw in self._gateways.values():
            await gw.register_service(service, handler)
        return Result.ok(True)

    async def call_service(self, service: str, request: dict, timeout: float = 30.0) -> Result[dict]:
        for gw in self._gateways.values():
            result = await gw.call_service(service, request, timeout)
            if result.success or result.error_code != "NOT_FOUND":
                return result
        return Result.fail("SERVICE_NOT_FOUND", f"Service {service} not found on any gateway")

    async def health_check(self) -> Result[dict]:
        health = {"protocols": {}}
        for proto, gw in self._gateways.items():
            health["protocols"][proto] = (await gw.health_check()).data
        return Result.ok(health)

    async def get_stats(self) -> dict:
        return {proto: await gw.get_stats() for proto, gw in self._gateways.items()}


# Result import
from ..core.domain import Result