# Changelog

All notable changes to the OpenJ5 project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned (see ROADMAP.md v0.3.0)
- CI/CD pipeline, integration tests, simulation parity tests, hardware-in-loop tests
  (tracked in `docs/NEXT_TASK.md` — will be listed here only once actually merged)

### Added
- Plugin framework base contracts (`src/plugins/base.py`): IPlugin,
  IConfigurablePlugin, ILifecyclePlugin, IPluginManager, IPluginRegistry,
  PluginMetadata/State/Type/Dependency/Permission/ConfigSchema/Health and a
  unified PluginContext - breaking the circular import between interfaces.py
  and manager.py; package `src.plugins` is now importable
- Domain services: `IKinematicsService`/`KinematicsService` (DH forward
  kinematics + damped-least-squares numerical inverse kinematics) and
  `IMotionPlanner` interface implemented by `MotionPlannerService`
- Value objects: `CalibrationData`, domain-level `PluginMetadata`
- Domain handlers: `CommandHandler`, `QueryHandler` contracts for the CQRS buses
- CI pipeline (GitHub Actions `.github/workflows/ci.yml`): Python lint gate (ruff),
  documentation check gate (`scripts/check_docs.sh`), Docker build gate for robot-core
- `pyproject.toml` with ruff configuration (E4/E7/E9/F rules)
- Governance documents filled: ARCHITECTURAL_PRINCIPLES, CODING_STANDARD,
  CONSTRAINTS, NAMING_CONVENTIONS
- ADR-005 to ADR-015 formalized (HAL, Robot SDK facade, Plugin Architecture,
  Configuration-Driven, State Machine per Node, Digital Twin Native, Signed OTA,
  FreeCAD Parametric CAD, Security mTLS/JWT/Fail-Safe, Python Core + C++ Firmware,
  MQTT Primary Transport); fixed broken ADR-002 link in ADR INDEX
- Project continuity documents: PROJECT_MEMORY, NEXT_TASK, KNOWLEDGE_BASE,
  CONTINUATION_PROMPT, SESSION_REPORT

### Fixed
- `events.py`: removed `slots=True` that broke zero-arg `super()` in every event
  subclass (any instantiation would fail); `EVENT_SCHEMAS` no longer reads class
  attributes through slotted member descriptors; added missing
  `FaceRecognizedEvent`/`ObjectGraspedEvent`; export renamed to defined
  `DockingCompleteEvent`
- `entities.py`: resolved dataclass inheritance TypeError via kw_only fields;
  satisfied missing `CalibrationData`/`PluginMetadata` value objects
- `services.py`: fixed `math.time()` -> `time.time()`; added kinematics/motion
  planner contracts referenced by package exports
- Earlier lint pass: 14 missing SDK Query dataclasses added and exported; missing
  imports (`Path`, `Any`, `uuid`, `ABC`, `abstractmethod`, `Protocol`);
  star-imports replaced in robot_core API; trailing module-level imports moved

---

## [0.2.0] - 2026-07-15

### Added
- `robot_core/` Python package with all services:
  - Config service (multi-source, hot reload, JSON Schema validation)
  - Logging service (structlog JSON, correlation IDs, rotation, Loki)
  - Database manager (SQLAlchemy async, connection pooling, Alembic migrations)
  - Event bus (Redis Streams, consumer groups, DLQ, event replay)
  - Plugin manager (discovery, dependency resolution, lifecycle, hot reload)
  - OTA manager (firmware registration, ECDSA signing, staged rollout, rollback)
  - Task scheduler (APScheduler cron/interval jobs, built-in maintenance tasks)
  - State machine orchestrator (7 states, 6 node coordination, fault propagation)
  - Digital twin bridge (Gazebo, Isaac Sim, entity mapping, joint sync, time sync)
  - Health service (heartbeat, system checks, alerting, aggregation)
- REST API v1 with 25+ endpoints:
  - Robot control (command, stop, home, status)
  - Configuration (get, set, schema)
  - Node management (list, detail)
  - State machine (query, transition)
  - Plugin management (list, enable, disable, reload, unload)
  - OTA (register firmware, deploy, status)
  - Scheduler (list, create, delete jobs)
  - Health (detailed)
  - Calibration (save, list positions)
  - System (shutdown, restart, info)
  - Simulation (status, pause, resume, reset)
- WebSocket handler (real-time events, bidirectional commands, state queries)
- Docker Compose with 10 services:
  - mosquitto 2.0 (mTLS, WebSocket, ACL)
  - redis 7-alpine (AOF persistence)
  - postgres 16-alpine (migration, schema)
  - robot-core (Python, FastAPI, Uvicorn)
  - ros2-bridge (Humble, rosbridge WebSocket)
  - gazebo (harmonic, headless)
  - prometheus (30d retention, lifecycle)
  - grafana 10.2 (provisioned dashboards)
  - loki 2.9 (log aggregation)
  - otel-collector (traces, metrics, logs pipeline)
- Infrastructure configuration files:
  - Mosquitto mTLS + ACL configuration
  - PostgreSQL initialization schema (events, config, firmware, OTA, calibration, logs)
  - Prometheus scrape config for all services
  - Grafana datasources (Prometheus, Loki)
  - Loki storage configuration (BoltDB, filesystem, retention)
  - Promtail log scraping pipeline
  - OpenTelemetry collector pipeline
  - Gazebo world file (headless, physics, lighting)
  - ROS2 bridge parameters
  - Secrets templates (db, grafana, OTA signing key)
- Pydantic API models (Pose, JointState, RobotStatus, PluginInfo, OTAStatus, 25+ models)
- HealthService (heartbeat, system checks, alerting, aggregation)

### Changed
- Unified Robot Core entry point (`__main__.py`, removed duplicate `main.py`)
- Fixed all cross-file constructor signature mismatches
- Fixed duplicate volume definition in docker-compose.yml

### Fixed
- `plugins.py`: `__init__` typo, added `load_all_plugins()`/`start_all_plugins()`
- `statemachine.py`: `__init__` typo, added `database` param
- `digital_twin.py`: `__init__` typo, fixed `disconnect()` cleanup
- `ota.py`: added `database` param, use `initialize()` instead of `start()`
- `scheduler.py`: added `database` param
- `health.py`: `get_health_summary()` now properly async
- `__main__.py`: all service constructors pass `ConfigService` not section dict
- `api/rest.py`: 20+ method name fixes to match actual service APIs
- `requirements.txt`: added `psutil`

---

## [0.1.0] - 2026-06-30

### Added
- Repository directory structure (Hexagonal Architecture)
- Core domain Python package (`src/core/domain/`):
  - Value objects (Angle, Position3D, Quaternion, Pose3D, Twist, JointAngles, etc.)
  - Events (40+ typed domain events with registry and JSON Schema)
  - Commands (CQRS CommandBus/QueryBus with middleware)
  - Entities (Robot aggregate root, Node, Servo, Motor, Plugin, Calibration)
  - Repository interfaces (IRepository, IRobotRepository, etc.)
  - Services (KinematicsService DH-parameter, MotionPlannerService, SafetyPolicyService)
- Plugin Architecture (`src/plugins/`):
  - Interfaces (IPlugin, IVisionPlugin, ISpeechPlugin, INavigationPlugin, 14 interfaces)
  - PluginManager (load/unload/enable/disable with dependency resolution)
  - PluginRegistry (marketplace with artifact storage and signature verification)
  - PluginSandbox (permission checking)
- Robot SDK facade (`src/sdk/robot.py`):
  - Robot class with lazy-loaded subsystems (HeadAPI, ArmAPI, TracksAPI, etc.)
  - RobotConfig with mode selection (real/sim/mock)
  - Async and Sync wrappers
- Communication Gateway (`src/gateway/communication.py`):
  - ICommunicationGateway (publish, subscribe, request, service, health)
  - MqttGateway (async aiomqtt with TLS/mTLS, QoS, dead-letter)
  - MultiProtocolGateway (topic-based routing)
  - GatewayFactory
- Event Bus (`src/eventbus/`):
  - IEventBus and DomainEvent base class
  - RedisEventBus (Redis Streams, consumer groups, idempotency, DLQ, replay)
  - InMemoryEventBus (testing)
- State Machine (`src/statemachine/state_machine.py`):
  - StateMachine with valid transitions (BOOT→INIT→READY→RUNNING↔ERROR→RECOVERY→SHUTDOWN)
  - StateHandler per state (on_enter/exit/update/event)
  - Watchdog timer, transition callbacks, default handlers
- Configuration Service (`src/config/service.py`):
  - Multi-source (ENV, File, Database) with priority merging
  - JSON Schema validation, file watching, change notifications
  - Dot-notation get/set
- Node configuration files (`config/node1-6/node.json`):
  - Full servo/motor configuration with kinematics, network, safety
- Core documentation:
  - `README.md` (full project overview)
  - `ARCHITECTURE.md` (C4, sequence, state machine, deployment, HAL, plugin diagrams)
  - `CONFIGURATION.md` (priority, file structure, JSON Schema, examples)
  - `API.md` (Robot SDK reference for Python, C++, TypeScript)
- Architecture Decision Records (ADR-001 to ADR-005)
- Governance documents (Development_Constitution, VISION, MISSION, GOALS, etc.)
- Firmware C++ structure:
  - `firmware/common/` (ESP-IDF component with HAL, drivers, MQTT, OTA)
  - `firmware/node2_head/` (CMakeLists.txt, main.cpp for head controller)
- Firmware node2 Dockerfile (ESP-IDF build environment)
- Firmware development docker-compose (idf-monitor, node2)

---

## [0.0.1] - 2026-06-15

### Added
- Initial project scaffolding
- Repository structure
- MASTER_PROMPT.md with complete project brief
- Project governance documents
