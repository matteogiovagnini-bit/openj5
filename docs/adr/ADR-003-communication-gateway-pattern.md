# ADR-003: Communication Gateway Pattern (Multi-Protocol)

## Status
Accepted

## Context
OpenJ5 must support multiple communication protocols:
- **MQTT** (primary, low overhead, pub/sub, QoS, retained messages)
- **ROS 2** (ecosystem integration, DDS, real-time)
- **WebSocket** (web UI, teleop, browser clients)
- **Serial** (debug, bootstrap, wired fallback)
- **BLE** (provisioning, mobile app)
- **CAN** (automotive, real-time, safety-critical future)
- **Zenoh** (edge computing, low latency, pub/sub/query)
- **gRPC** (service-to-service, streaming, contract-first)

**Requirement**: Application code MUST NOT know or depend on any protocol. Protocol must be swappable without changing application logic.

## Decision
Implement **Communication Gateway Pattern** (Port/Adapter):

```python
# Domain/Port - Application uses ONLY this
class ICommunicationGateway(ABC):
    @abstractmethod
    async def publish(self, topic: str, payload: dict, qos: int = 1) -> Result: ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable[[dict], None]) -> Subscription: ...

    @abstractmethod
    async def request(self, topic: str, payload: dict, timeout: float) -> Result: ...

    @abstractmethod
    async def advertise_service(self, service: str, handler: Callable) -> Result: ...

    @abstractmethod
    async def call_service(self, service: str, payload: dict, timeout: float) -> Result: ...
```

**Infrastructure/Adapters** (implement the port):
- `MqttGateway` - Uses paho-mqtt / EMQX client
- `Ros2Gateway` - Uses rclpy + rosbridge
- `WebSocketGateway` - Uses aiohttp/websockets
- `SerialGateway` - Uses pyserial
- `BleGateway` - Uses bleak
- `CanGateway` - Uses python-can
- `ZenohGateway` - Uses zenoh-python
- `GrpcGateway` - Uses grpcio

**Configuration-driven selection:**
```yaml
# config/common/communication.yaml
gateway:
  default: "mqtt"
  implementations:
    mqtt:
      enabled: true
      host: "localhost"
      port: 8883
      tls: true
    ros2:
      enabled: false
      domain_id: 42
    websocket:
      enabled: true
      port: 8081
```

**Topic Schema (Versioned):**
```
openj5/v1/head/cmd        # Commands TO head
openj5/v1/head/evt        # Events FROM head
openj5/v1/head/telemetry  # Periodic telemetry
openj5/v1/head/state      # State machine transitions
openj5/v1/right_arm/cmd   # ...
```

## Alternatives Considered
1. **Direct protocol usage** - Rejected: Violates ADR-001, locks into protocol
2. **ROS 2 as backbone** - Rejected: Not all nodes run ROS 2, overhead on ESP32
3. **Custom protocol** - Rejected: Reinventing wheel, no ecosystem
4. **Message broker abstraction only** - Rejected: Need request/reply, services, not just pub/sub

## Consequences
**Positive:**
- Protocol swap = config change + adapter implementation (zero app code changes)
- Test with mock gateway (in-memory) for unit tests
- Multiple protocols simultaneously (MQTT for ESP32, WebSocket for UI, ROS2 for Nav2)
- Gateway handles protocol-specific concerns (reconnection, QoS, serialization)
- Security (mTLS, JWT) implemented once in gateway

**Negative:**
- Additional abstraction layer (slight latency)
- Must map all protocol features to common interface (least common denominator)
- Adapter maintenance burden

## Implementation Notes
- **Serialization**: JSON for MQTT/WebSocket/Serial, ROS 2 messages for ROS2, Protobuf for gRPC
- **Correlation IDs**: All requests/responses carry `correlation_id` for tracing
- **Circuit Breaker**: Built into gateway (resilience4j / custom)
- **Rate Limiting**: Per-topic/client in gateway
- **Topic Versioning**: `v1`, `v2` in topic path, dual-publish during migration

## Related ADRs
- ADR-001: Hexagonal Architecture (Gateway is an Adapter)
- ADR-004: Event-Driven Architecture (Gateway transports events)
- ADR-015: MQTT as Primary Transport (Default gateway)
- ADR-006: Robot SDK (Uses Gateway via Command/Event Bus)