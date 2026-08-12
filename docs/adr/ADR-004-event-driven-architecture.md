# ADR-004: Event-Driven Architecture with Central Event Bus

## Status
Accepted

## Context
OpenJ5 components must communicate without direct coupling:
- Camera detects face → Behavior Engine decides reaction → Motion Planner plans trajectory → Head Controller executes
- Battery low → Torso reports → Robot Core triggers docking behavior → Tracks navigate to charger
- Collision detected → Tracks emergency stop → All nodes enter RECOVERY state

Direct calls create tight coupling, make testing hard, prevent substitution.

## Decision
Implement **Central Event Bus** with **Typed Domain Events**:

```python
# Domain Events (immutable, versioned)
@dataclass(frozen=True)
class DomainEvent:
    event_id: str          # UUID
    event_type: str        # "FaceDetected", "BatteryLow", "NodeStateChanged"
    timestamp: float       # Unix timestamp
    source_node: str       # "node1", "node2", etc.
    correlation_id: str    # For tracing command→event chains
    payload: dict          # Typed payload per event type

# Event Bus Interface
class IEventBus(ABC):
    @abstractmethod
    async def publish(self, event: DomainEvent) -> Result: ...

    @abstractmethod
    async def subscribe(self, event_type: str, handler: EventHandler) -> Subscription: ...

    @abstractmethod
    async def replay(self, from_timestamp: float, event_types: List[str]) -> AsyncIterator[DomainEvent]: ...
```

**Infrastructure: Redis Streams** (primary) / NATS (alternative)
- Consumer groups for scaling handlers
- Persistent streams with retention (7 days)
- Dead letter queue for failed handlers
- Exactly-once semantics via idempotency keys

**Event Flow Example:**
```
Camera Plugin (Node 1)
    │
    ▼ publishes FaceDetected {face_id, bbox, confidence, timestamp}
Event Bus (Redis Streams)
    │
    ├─▶ Behavior Engine Plugin: decides "follow_person"
    │       │
    │       ▼ publishes FollowPersonCommand {person_id, distance}
    │   
    ▼ Motion Planner Plugin: computes head+tracks trajectory
    │       │
    │       ▼ publishes MoveHeadCommand, MoveTracksCommand
    │
    ▼ Head Controller (Node 2): executes look_at
    ▼ Track Controller (Node 6): executes move_forward
```

**Event Categories:**
| Category | Examples | Retention |
|----------|----------|-----------|
| **Command** | `MoveHeadCommand`, `SayTextCommand`, `DeployOTACommand` | 1 day |
| **Telemetry** | `ServoPosition`, `MotorVelocity`, `BatteryVoltage`, `ImuData` | 7 days |
| **State** | `NodeStateChanged`, `RobotStateChanged`, `PluginStateChanged` | 30 days |
| **Error** | `HardwareFault`, `CommunicationLost`, `SafetyViolation` | 90 days |
| **Business** | `FaceDetected`, `ObjectGrasped`, `DockingComplete`, `PersonFollowed` | 30 days |

## Alternatives Considered
1. **Direct MQTT pub/sub** - Rejected: No persistence, no replay, no dead letter, coupling to MQTT
2. **ROS 2 Topics/Services** - Rejected: Not all nodes run ROS, ADR-003 abstracts transport
3. **Custom in-process bus** - Rejected: Doesn't work across distributed nodes
4. **Kafka** - Rejected: Overkill, heavy, not on ESP32

## Consequences
**Positive:**
- Zero direct coupling between components
- Easy to add new consumers (plugins) without modifying producers
- Full audit trail via event store (event sourcing for critical state)
- Replay for debugging, simulation, ML training
- Horizontal scaling of handlers via consumer groups
- Cross-node communication transparent

**Negative:**
- Eventual consistency (not ACID)
- Event schema evolution complexity (versioning required)
- Debugging distributed flows harder (need correlation IDs, distributed tracing)
- Infrastructure dependency (Redis/NATS)

## Implementation Notes
- **Schema Registry**: JSON Schema per event type, stored in Config DB, validated on publish
- **Idempotency**: All handlers must be idempotent (use `event_id` deduplication)
- **Ordering**: Per-source ordering guaranteed by Redis Streams; cross-source not guaranteed
- **Monitoring**: Prometheus metrics on event lag, handler latency, error rates
- **Testing**: In-memory `TestEventBus` for unit tests, Testcontainers Redis for integration

## Related ADRs
- ADR-001: Hexagonal Architecture (Event Bus is Infrastructure Adapter)
- ADR-003: Communication Gateway (Gateway transports events to/from ESP32)
- ADR-006: Robot SDK (SDK publishes commands as events)
- ADR-009: State Machine (State transitions published as events)