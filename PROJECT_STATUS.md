# OpenJ5 Project Status

## Repository: `PRJ_OpenJ5`

> **Last updated:** 2026-07-15
> **Status:** 🟡 In Development (v0.2.0 → v0.3.0) — **Robot Core operativo su hardware reale dal 2026-08-26**

---

## Overview

OpenJ5 is an open-source Johnny 5-inspired robot platform with a 6-node distributed architecture, Hexagonal Architecture, Plugin System, and full parametric CAD/KiCad electronics. The project targets professional-grade robotics development with a 10-year lifespan.

## Status by Component

### 🟢 Software Architecture
| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| Domain Model (value objects, events, commands, entities, services) | ✅ Done | 95% | All value objects, events, CQRS bus, entities, repositories, kinematics service |
| Plugin Architecture | ✅ Done | 90% | PluginManager, PluginRegistry, Sandbox, dependency resolution |
| Communication Gateway | ✅ Done | 85% | MQTT, MultiProtocol, mTLS |
| Event Bus (Redis Streams) | ✅ Done | 85% | Streams, consumer groups, DLQ, replay |
| State Machine | ✅ Done | 90% | 7 states, transitions, node orchestration |
| Configuration Service | ✅ Done | 80% | Multi-source, hot reload, validation |
| Robot SDK Facade | ✅ Done | 85% | Robot class, HeadAPI, ArmAPI, TracksAPI, SpeechAPI, BehaviorAPI, VisionAPI, BatteryAPI, SystemAPI |

### 🟢 Robot Core (Node 1 - Raspberry Pi 4)
| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| Docker Compose (10 services) | ✅ Done | 100% | mosquitto, redis, postgres, robot-core, ros2-bridge, gazebo, prometheus, grafana, loki, otel-collector |
| Dockerfile (multi-stage) | ✅ Done | 100% | ARM64 optimized |
| Robot Core Python Package | ✅ Done | 90% | config, logging, database, eventbus, plugins, ota, scheduler, statemachine, digital_twin, health |
| REST API (25+ endpoints) | ✅ Done | 90% | robot control, config, nodes, plugins, OTA, scheduler, calibration, simulation, system |
| WebSocket Handler | ✅ Done | 85% | Real-time events, bidirectional commands, state queries |
| Health Service | ✅ Done | 80% | Heartbeat monitoring, system checks, alerting |
| Infrastructure Config | ✅ Done | 95% | Mosquitto, PostgreSQL init, Prometheus, Grafana, Loki, OTEL, secrets, certs |
| API Models (Pydantic) | ✅ Done | 90% | Request/response schemas for all endpoints |

### 🟡 Firmware (ESP32-S3 Nodes)
| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| Common ESP-IDF Component | 🟡 Partial | 60% | CMakeLists.txt structured, HAL interfaces defined |
| Node 2 (Head) - CMakeLists | 🟡 Partial | 70% | Project structure, driver configs |
| Node 2 (Head) - main.cpp | 🟡 Partial | 60% | Core loop, servo management, motion primitives |
| Node 3-6 Firmware | 🔴 Not Started | 0% | Structure defined, no implementation |
| OTA Update Client | 🟡 Partial | 40% | Protocol defined, download logic pending |

### 🟢 Architecture Decisions
| ADR | Status | Notes |
|-----|--------|-------|
| ADR-001: Hexagonal Architecture | ✅ Accepted | Core domain zero external deps |
| ADR-002: 6-Node Distributed Architecture | ✅ Accepted | RPi4 + 5× ESP32-S3 |
| ADR-003: Communication Gateway Pattern | ✅ Accepted | Single ICommunicationGateway interface |
| ADR-004: Event-Driven Architecture | ✅ Accepted | Redis Streams central event bus |
| ADR-005: HAL for All Drivers | ✅ Accepted | Hardware Abstraction Layer |

### 🟡 Documentation
| Document | Status | Notes |
|----------|--------|-------|
| README.md | ✅ Done | Full project overview |
| ARCHITECTURE.md | ✅ Done | C4, sequence, state machine, deployment diagrams |
| CONFIGURATION.md | ✅ Done | Per-node examples, priority, JSON Schema |
| API.md | ✅ Done | Robot SDK reference (Python, C++, TypeScript) |
| PROJECT_STATUS.md | ✅ Done | This document |
| CHANGELOG.md | ✅ Done | Version history |
| ROADMAP.md | ✅ Done | Development roadmap |
| ADR Index + 5 ADRs | ✅ Done | ADR-001 to ADR-005 |
| Development Constitution | ✅ Done | Level A/B/C governance |
| VISION / MISSION / GOALS / NON_GOALS | ✅ Done | Project governance |
| CODING_STANDARD / NAMING_CONVENTIONS | ✅ Done | Code quality rules |

### 🔴 Not Started (Next Releases)
| Component | Priority | Target Release |
|-----------|----------|----------------|
| CI/CD Pipeline (GitHub Actions) | High | v0.3.0 — 🟡 base shipped (lint, doc-check, docker build); tests pending |
| Integration Tests | High | v0.3.0 |
| Simulation Test Suite | High | v0.3.0 |
| Firmware Nodes 3-6 | High | v0.4.0 |
| Facial Recognition Plugin | Medium | v0.5.0 |
| Person Following | Medium | v0.5.0 |
| LIDAR Integration | Medium | v0.6.0 |
| SLAM Navigation | Medium | v0.6.0 |
| Full 7-DOF Arms | Low | v1.0.0 |
| Object Manipulation | Low | v1.0.0 |
| Auto-Docking/Recharge | Low | v1.1.0 |

---

## Key Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Python files | - | 30+ |
| Firmware C++ files | - | 5 |
| Config files (JSON/YAML) | - | 10+ |
| Docker services | - | 10 |
| Plugins framework | - | 14 interface types |
| ADRs | - | 5 |
| Documentation files | - | 20+ |

## Current Release: v0.2.0 (In Development)

### What's Included
- Complete software architecture (Hexagonal, CQRS, Event-Driven)
- Robot Core Python package with all services
- Docker Compose with 10 services for RPi4
- REST API v1 with 25+ endpoints
- WebSocket real-time event streaming
- Plugin architecture with dependency resolution
- OTA firmware management with signature verification
- Redis Streams event bus with DLQ and replay
- State machine orchestrator for 6 nodes
- Digital twin bridge (Gazebo/Isaac Sim)
- Complete infrastructure configs (MQTT, Prometheus, Grafana, Loki, OTEL)
- PostgreSQL schema with migrations
- Full documentation suite

### What's Next (v0.3.0)
- CI/CD Pipeline (GitHub Actions)
- Integration tests
- Simulation parity tests
- Hardware-in-loop tests

---

## Blocking Issues

**None.** No known blockers at this stage.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ESP32 RAM insufficient for complex drivers | Medium | High | Use PSRAM, driver modularization |
| MQTT latency with 6 nodes + ROS2 bridge | Low | Medium | QoS levels, topic optimization |
| Redis Streams memory growth | Low | Medium | Stream length limits, retention policy |
| Python performance on RPi4 | Medium | Medium | Async everywhere, C extensions for critical paths |
