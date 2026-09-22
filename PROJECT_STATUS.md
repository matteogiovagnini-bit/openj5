# OpenJ5 Project Status

## Repository: `PRJ_OpenJ5`

> **Last updated:** 2026-09-22
> **Status:** 🟡 In Development (v0.2.0 → v0.3.0) — **Robot Core operativo su hardware reale dal 2026-08-26; design Node 7 Balance (ADR-017) consegnato il 2026-09-21; T-003 unit test core domain completati il 2026-09-22 (149 test, 100% coverage)**

---

## Overview

OpenJ5 is an open-source Johnny 5-inspired robot platform with a 7-node distributed architecture (6 original + **Node 7 Balance Controller**, ADR-017), Hexagonal Architecture, Plugin System, and full parametric CAD/KiCad electronics. The project targets professional-grade robotics development with a 10-year lifespan.

## Status by Component

### 🟢 Software Architecture
| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| Domain Model (value objects, events, commands, entities, services) | ✅ Done | 100% | All value objects, events, CQRS bus, entities, repositories, kinematics service — **verified by `tests/unit/` (149 tests, T-003)** |
| Unit test suite (`tests/unit/`, core.domain) | ✅ Done | 100% | pytest + pytest-cov; 6 modules + conftest; CI gate ≥90% (`python-tests` job) |
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
| Deploy reale RPi4 8GB (T-018) | ✅ Done | 100% | Pi OS Lite Trixie su NVMe USB3, boot USB nativo, stack healthy, API live, cgroup v2 attivi (2026-08-26). **ros2-bridge/gazebo: primo avvio reale da confermare** |
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
| Node 7 (Balance) Firmware | ⬜ Designed | 15% | ADR-017 + Python HAL/driver/sim tested; ESP-IDF pending (T-026) |
| OTA Update Client | 🟡 Partial | 40% | Protocol defined, download logic pending |

### 🟢 Architettura Decisioni
| ADR | Status | Notes |
|-----|--------|-------|
| ADR-001: Hexagonal Architecture | ✅ Accepted | Core domain zero external deps |
| ADR-002: 7-Node Distributed Architecture | ✅ Accepted | RPi4 + 6× ESP32-S3/ESP32 (ADR-017 adds Node 7 Balance) |
| ADR-003: Communication Gateway Pattern | ✅ Accepted | Single ICommunicationGateway interface |
| ADR-004: Event-Driven Architecture | ✅ Accepted | Redis Streams central event bus |
| ADR-005: HAL for All Drivers | ✅ Accepted | Hardware Abstraction Layer |
| ADR-006 .. ADR-016 | ✅ Accepted | 11 ADR aggiuntivi (SDK, plugin, config, state machine, digital twin, OTA, FreeCAD, security, Python/C++, MQTT, Pi OS Lite+NVMe) — vedi docs/adr/INDEX.md |
| ADR-017 (New) | ✅ Accepted | Node 7 Balance Controller: NEMA17 + A4988 + MPU6050, body leveled vs gravity |

### 🟡 Prototipo Nodo 6 (banco)
| Component | Status | Notes |
|-----------|--------|-------|
| Driver HAL `L298NDriver` | ✅ Done | `src/hardware/drivers/l298n.py`, interfaccia IMotorDriver prototipale, gpiozero/lgpio |
| Demo motori | ✅ Done | `scripts/demo/tracks_bench.py` (w/s/a/d/x/q) |
| Config pin | ✅ Done | `config/bench/tracks.json` |
| Guida cablaggio | ✅ Done | `docs/hardware/BENCH_TRACKS.md` |
| Primo movimento fisico | 🔴 To do | T-025 — cablaggio pronto, demo da lanciare sul Pi |

### 🟡 Prototipo Nodo 7 (design, ADR-017)
| Component | Status | Notes |
|-----------|--------|-------|
| ADR-017 | ✅ Done | Node 7 Balance Controller (ESP32-S3 + NEMA17/A4988 + MPU6050) |
| HAL `IStepperDriver` | ✅ Done | `src/hardware/hal/stepper.py` (port puro, accelerazione limitata) |
| Driver bench A4988 | ✅ Done | `src/hardware/drivers/a4988.py` + `config/bench/balance.json` |
| Mock stepper (CI-safe) | ✅ Done | `src/hardware/drivers/mock_stepper.py`, nessuna dipendenza GPIO |
| Simulatore livellamento | ✅ Done | `src/hardware/sim/leveling.py` (loop PID 100 Hz, deadband, ramp track) |
| Domain | ✅ Done | StepperConfig/BalanceConfig, BodyCommand(+Query), 3 eventi, entità Stepper |
| Config Node 7 | ✅ Done | `config/node7_balance/node.json`, entry stepper_driver in hal.json, topics node7 |
| SDK | ✅ Done | `BodyAPI` + `robot.body.level()/tilt()/stow()/stop()` |
| Orchestratore | ✅ Done | node7 in statemachine/health/digital_twin/models |
| Test | ✅ Done | `tests/unit/test_balance_control.py` — 8 test verdi (Python 3.11, ruff clean) |
| Firmware ESP-IDF | To do | T-026 — follow-up |
| CAD/meccanica (cinghia/pulegge) | To do | T-027 — follow-up |

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
| ADR Index (completo) | ✅ Done | ADR-001 to ADR-016 — vedi docs/adr/INDEX.md |
| BENCH_TRACKS (hardware) | ✅ Done | Guida banco Nodo 6: cablaggio motori, power, safety |
| Development Constitution | ✅ Done | Level A/B/C governance |
| VISION / MISSION / GOALS / NON_GOALS | ✅ Done | Project governance |
| CODING_STANDARD / NAMING_CONVENTIONS | ✅ Done | Code quality rules |

### 🔴 Not Started (Next Releases)
| Component | Priority | Target Release |
|-----------|----------|----------------|
| CI/CD Pipeline (GitHub Actions) | High | v0.3.0 — 🟡 lint + unit tests (cov ≥90%) + doc-check + docker build attivi; mancano mypy/clang-tidy |
| Integration Tests (T-004/T-005) | High | v0.3.0 — sbloccati da T-003 |
| Simulation Test Suite (T-006) | High | v0.3.0 |
| Firmware Nodes 3-7 | High | v0.4.0 |
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
| Python files | - | 35+ |
| Unit tests (core.domain) | ≥90% coverage | 149 tests, **100% coverage** |
| Firmware C++ files | - | 5 |
| Config files (JSON/YAML) | - | 12+ |
| Docker services | - | 10 |
| Plugins framework | - | 14 interface types |
| ADRs | - | 17 |
| Documentation files | - | 25+ |

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
- State machine orchestrator for 7 nodes
- Digital twin bridge (Gazebo/Isaac Sim)
- Complete infrastructure configs (MQTT, Prometheus, Grafana, Loki, OTEL)
- PostgreSQL schema with migrations
- Full documentation suite
- Unit test suite for the core domain (T-003): 149 tests, 100% line coverage, CI coverage gate ≥90%
- Node 7 Balance Controller design (ADR-017): HAL IStepperDriver, A4988 bench driver + mock, leveling-loop simulator, BodyAPI SDK, configs + topics, unit tests

### What's Next (v0.3.0)
- Integration tests (REST/WS, event bus + state machine)
- Simulation parity tests
- Hardware-in-loop tests

---

## Blocking Issues

**None.** No known blockers at this stage.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ESP32 RAM insufficient for complex drivers | Medium | High | Use PSRAM, driver modularization |
| MQTT latency with 7 nodes + ROS2 bridge | Low | Medium | QoS levels, topic optimization |
| Redis Streams memory growth | Low | Medium | Stream length limits, retention policy |
| Python performance on RPi4 | Medium | Medium | Async everywhere, C extensions for critical paths |
