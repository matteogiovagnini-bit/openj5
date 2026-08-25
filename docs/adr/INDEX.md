# Architecture Decision Records (ADR) Index

## Overview

This directory contains Architecture Decision Records (ADRs) for the OpenJ5 project. Each ADR documents a significant architectural decision, its context, alternatives considered, and consequences.

## ADR Template

All ADRs follow this template:

```markdown
# ADR-XXX: Title

## Status
[Proposed | Accepted | Rejected | Superseded by ADR-YYY]

## Context
What is the issue that we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing and/or doing?

## Alternatives Considered
What other options did we consider?

## Consequences
What becomes easier or more difficult to do because of this change?

## Implementation Notes
Any specific implementation details, migration paths, or follow-up tasks.

## Related ADRs
- ADR-XXX: Related decision
```

## ADR List

| ID | Title | Status | Date |
|----|-------|--------|------|
| [ADR-001](ADR-001-hexagonal-architecture.md) | Hexagonal Architecture for Core Domain | Accepted | 2026-07-15 |
| [ADR-002](ADR-002-six-node-distributed-architecture.md) | 6-Node Distributed Architecture | Accepted | 2026-07-15 |
| [ADR-003](ADR-003-communication-gateway-pattern.md) | Communication Gateway Pattern (Multi-Protocol) | Accepted | 2026-07-15 |
| [ADR-004](ADR-004-event-driven-architecture.md) | Event-Driven Architecture with Central Event Bus | Accepted | 2026-07-15 |
| [ADR-005](ADR-005-hardware-abstraction-layer.md) | Hardware Abstraction Layer (HAL) for All Drivers | Accepted | 2026-07-15 |
| [ADR-006](ADR-006-robot-sdk-facade.md) | Robot SDK as Single Facade for Applications | Accepted | 2026-07-15 |
| [ADR-007](ADR-007-plugin-architecture.md) | Plugin Architecture for All Features | Accepted | 2026-07-15 |
| [ADR-008](ADR-008-configuration-driven.md) | Configuration-Driven Development (JSON/YAML Only) | Accepted | 2026-07-15 |
| [ADR-009](ADR-009-state-machine-per-node.md) | State Machine per Node (BOOT→INIT→READY→RUNNING→ERROR→RECOVERY→SHUTDOWN) | Accepted | 2026-07-15 |
| [ADR-010](ADR-010-digital-twin-native.md) | Digital Twin Native (Gazebo/Isaac Sim) | Accepted | 2026-07-15 |
| [ADR-011](ADR-011-ota-signed-firmware.md) | OTA with Signed Firmware and Rollback | Accepted | 2026-07-15 |
| [ADR-012](ADR-012-freecad-parametric-cad.md) | FreeCAD Parametric CAD with Spreadsheet Configuration | Accepted | 2026-07-15 |
| [ADR-013](ADR-013-security-mtls-jwt-signed-ota.md) | Security: mTLS, JWT, Signed OTA, Fail-Safe | Accepted | 2026-07-15 |
| [ADR-014](ADR-014-python-core-cpp-firmware.md) | Python for Robot Core, C++ for Firmware | Accepted | 2026-07-15 |
| [ADR-015](ADR-015-mqtt-primary-transport.md) | MQTT as Primary Transport Protocol | Accepted | 2026-07-15 |
| [ADR-016](ADR-016-pios-lite-nvme-node1.md) | Raspberry Pi OS Lite 64-bit (Bookworm) as Node 1 Reference OS, NVMe-over-USB3 Storage | Accepted | 2026-08-25 |

## Governance

- **Design Authority**: Reviews and approves ADRs with architectural impact (Level C decisions)
- **Component Owners**: Can propose ADRs for their domain
- **All ADRs are immutable** - once accepted, never modified. Superseded by new ADRs.
- **ADR required for**: Architecture changes, protocol changes, hardware changes, feature removal (Level C decisions per Development Constitution)

## Creating New ADRs

1. Copy `TEMPLATE.md` to `ADR-XXX-title.md` (next sequential number)
2. Fill in all sections
3. Submit PR for review by Design Authority
4. Once accepted, update this INDEX.md