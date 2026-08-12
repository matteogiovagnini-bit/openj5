# ADR-001: Hexagonal Architecture for Core Domain

## Status
Accepted

## Context
OpenJ5 needs an architecture that:
- Survives 10+ years without architectural rewrites
- Allows swapping any component (MCU, protocol, sensor, actuator, AI framework)
- Enables unit testing without hardware
- Supports Digital Twin (simulator uses same API as real robot)
- Follows SOLID, Clean Architecture, DDD principles

## Decision
Adopt **Hexagonal Architecture (Ports & Adapters)** for the Robot Core (Node 1) and all application-level code:

```
┌─────────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER (Pure)                      │
│  Entities, Value Objects, Domain Events, Repository Interfaces, │
│  Domain Services, Policies - ZERO external dependencies      │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Implements
                              │
┌─────────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                           │
│  Use Cases, Commands, Queries, Event Handlers,               │
│  Command/Query Bus - Depends ONLY on Domain                  │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Uses
                              │
┌─────────────────────────────────────────────────────────────┐
│              INFRASTRUCTURE LAYER (Adapters)                │
│  MQTT Gateway, ROS2 Gateway, WebSocket Gateway,             │
│  Redis Event Bus, SQLite/PostgreSQL Repositories,           │
│  PCA9685 Driver, L298N Driver, File Config, OTA Manager,    │
│  Plugin Loader - Implements Domain/Application interfaces    │
└─────────────────────────────────────────────────────────────┘
```

**Key Rules:**
- Domain layer: **Zero external dependencies** (no paho-mqtt, no rclpy, no sqlalchemy, no hardware libs)
- Application layer: Depends **only** on Domain layer
- Infrastructure layer: Implements interfaces defined in Domain/Application
- Dependency Injection at Composition Root only
- All communication through interfaces (Ports)

## Alternatives Considered
1. **Layered Architecture** - Rejected: creates dependency inversion violations, hard to test
2. **Clean Architecture (Concentric)** - Similar but less explicit about adapters
3. **Microservices** - Rejected for Node 1: overkill, latency, operational complexity
4. **Monolithic with Modules** - Rejected: no clear boundary enforcement

## Consequences
**Positive:**
- Domain logic testable in isolation (unit tests fast, no mocks for external systems)
- Swap MQTT → ROS2 → Zenoh → gRPC by changing adapter only
- Swap SQLite → PostgreSQL → etcd by changing repository adapter
- Swap PCA9685 → ESP32 LEDC → STM32 PWM by changing driver adapter
- Simulator implements same HAL interfaces as real hardware
- Clear separation enables team scaling (domain vs infrastructure teams)

**Negative:**
- More boilerplate (interfaces, adapters, DI setup)
- Requires discipline to not leak infrastructure into domain
- Initial setup cost higher

## Implementation Notes
- Python: Use `abc.ABC` for interfaces, `dataclasses` for value objects, `pydantic` for config
- C++ (Firmware): Use pure virtual classes for interfaces, template-based DI
- Composition Root: `src/core/infrastructure/composition_root.py`
- Architecture tests: Use `importlinter` / custom scripts to enforce layer boundaries

## Related ADRs
- ADR-003: Communication Gateway Pattern (Multi-Protocol)
- ADR-005: Hardware Abstraction Layer (HAL) for All Drivers
- ADR-006: Robot SDK as Single Facade for Applications