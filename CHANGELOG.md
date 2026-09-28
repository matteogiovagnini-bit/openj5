# Changelog

All notable changes to the OpenJ5 project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned (see ROADMAP.md v0.3.0)
- Integration tests, simulation parity tests, hardware-in-loop tests
  (tracked in `docs/NEXT_TASK.md` — will be listed here only once actually merged)

### Fixed
- `Command.__post_init__` was declared `@abstractmethod` on a non-ABC dataclass:
  all 9 concrete commands (`MoveHeadCommand`, `EmergencyStopCommand`, ...) were
  uninstantiable (`TypeError`), breaking ~50 SDK call sites including
  `robot.emergency_stop()`; now a concrete no-op hook
- `DomainEvent.to_dict()` only serialized base-class fields (subclass payloads
  were silently dropped) and `from_dict()` crashed on unknown keys and on wire
  strings for `category`/`event_version`/`timestamp`; serializer now emits all
  dataclass fields and deserializer filters/coerces safely
- `EVENT_CATEGORIES` lookup returned the BUSINESS category for every event type
- `KinematicsService.inverse_kinematics` damped-least-squares computed
  `J·Jᵀ` over the 3 Cartesian rows instead of `JᵀJ` over the joints: wrong
  dimensionality made IK zigzag without converging; fixed to the joint-space
  Gram matrix, plus a backtracking line search (`IK_MIN_STEP_ALPHA`) and a
  per-joint step cap (`IK_MAX_STEP_RAD`) so near-singular postures cannot
  overshoot into a limit cycle
- Triangular (short-move) branch of the rest-to-rest velocity profile
  overshot its target: unified accel/decel math into
  `_rest_to_rest_profile()` used by both joint and cartesian planners
- `RedisEventBus` rebuilt events with `DomainEvent.from_dict` (base class,
  subclass type lost): 3 sites now use `deserialize_event`
- `Robot` aggregate lacked `state`/`battery` accessors used by
  `SafetyPolicyService`: added `state`, `battery`, `errors`, `get_errors()`
- Node 7 travel limits were `±4445` jsteps everywhere (configs + CONFIGURATION.md)
  with a comment "= 35 deg": 4445 jsteps at 35.556 jsteps/° is actually **±125°**;
  corrected to `±1244` (= ±35°) in `config/node7_balance/node.json`,
  `config/bench/balance.json` and `docs/configuration/CONFIGURATION.md`
- Mosquitto ACL granted nodes 2-6 the pre-v1 paths (`openj5/nodeN/#`) that match
  no real topic (`config/common/topics.json` uses `openj5/v1/...`) and had no
  `node7` user at all: rewritten to the v1 paths, plus `system` reads and a
  `node7` section (ADR-017)
- `docker/certs/generate.sh` stopped at `node6`: no `node7` certificate/key was
  ever generated, so node7 mTLS could not have connected; now `node1..node7`
- `firmware/README.md` and the main README documented phantom files (19 missing
  sources in `common/CMakeLists.txt`, nonexistent `install_esp_idf.sh`): the
  root cause of non-buildable nodes (T-007/T-014) — rewritten to reality
- First real target build exposed four API errors in `firmware/common/` (never
  compiled for the chip — host tests only build pure logic): `std::strlcpy`
  (BSD/newlib, invisible under `-std=c++20`) → `std::snprintf`; transposed
  `i2c_config_t` members (`clk_speed` belongs to `master`, `clk_flags` is
  top-level); nonexistent `esp_timer_start` → `esp_timer_start_periodic`;
  `ESP_EVENT_ANY_ID` (int) passed where `esp_mqtt_client_register_event` takes
  `esp_mqtt_event_id_t` → `MQTT_EVENT_ANY` (IDF's examples are C, where the
  int→enum conversion is legal; C++ rejects it) — every API cross-checked on
  both target tags (v5.2.2 + v5.5) before fixing
- ADR-014 flags (`-Wall -Wextra -Wpedantic -Werror`) failed on ESP-IDF's own
  headers (`#include_next` in newlib `platform_include`, zero-length arrays in
  esp_wifi): after `project()` the shared CMakeLists demotes every `__idf_*`
  include directory (except our `main`/`common`) to SYSTEM for the two node
  targets — GCC ignores a plain `-I` for a dir also given with `-isystem`, so
  IDF headers stop tripping `-Werror` while OpenJ5 code stays fully checked,
  on both the `idf.py` (CI) and PlatformIO paths
- Kconfig `bool` symbols are absent from `sdkconfig.h` when `n` (the default),
  so `CONFIG_OPENJ5_*` read as values did not compile: now read via `#ifdef`
  into `constexpr bool`s; `CONFIG_APP_PROJECT_VER` requires
  `APP_PROJECT_VER_FROM_CONFIG=y`, so the boot log prints
  `esp_app_get_description()->version` (+ `esp_app_format` in `REQUIRES`)
- `CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y` added to `sdkconfig.defaults` (the board
  default of 2 MB mismatched the 8 MB flash); the generated per-env
  `sdkconfig.node7` (can contain `sdkconfig.local` secrets) is now gitignored

### Added
- **T-003 unit test suite for `src/core/domain/`**: `tests/unit/conftest.py`
  + 6 test modules (value objects, events, commands, entities, services,
  repositories) — 149 tests, **100% line coverage of `core.domain`**
  (gate: `--cov-fail-under=90`)
- `pyproject.toml`: `[tool.pytest.ini_options]` (testpaths, `pythonpath=["src"]`)
  and coverage config (`source = ["core.domain"]`, show_missing)
- CI job `python-tests` (pytest + coverage gate ≥90%) in
  `.github/workflows/ci.yml`; ruff now also lints `tests/`
- **T-026 Node 7 Balance firmware (ADR-017)**:
  - wiring guide `docs/hardware/BENCH_BALANCE.md` (pin tables, A4988 bridges,
    power diagram, MPU6050 axes, Vref procedure, motion math, safety checklist,
    bring-up sequence, troubleshooting)
  - pure logic in `firmware/common/`: `stepper_logic` (slew/brake/target),
    `Madgwick`, ADR-009 state machine, balance PID (sim parity) — host-tested
    by `scripts/test/host_firmware.sh` (36 checks, g++, no ESP-IDF needed)
  - ESP glue in `firmware/common/`: `A4988Driver` (esp_timer STEP pulses,
    atomic position, dir-swap only when stopped), `Mpu6050Driver`, `WifiStation`,
    `MqttClient` (optional mTLS, ADR-013); `common/CMakeLists.txt` now lists
    only files that exist
  - full ESP-IDF project `firmware/node7_balance/`: 100 Hz control task +
    200 Hz IMU task, logical commands `level/tilt/stow/stop` on
    `openj5/v1/balance/cmd`, system E-stop subscription, deadman/watchdog/
    travel fail-safes, coils off at boot, Kconfig.projbuild synced with
    `node.json`, README with local `sdkconfig.local` + mTLS cert procedure
- Config parity test `tests/unit/test_node7_config_sync.py` (9 tests):
  Kconfig ↔ node.json ↔ balance.json ↔ wiring doc ↔ certs script ↔
  `platformio.ini`
- CI jobs `firmware-host-tests` (g++ logic tests) and `firmware-node7-build`
  (`espressif/idf:v5.2.2` container, `idf.py set-target esp32s3 && idf.py build`)
- **VSCode + PlatformIO path for the Node 7 firmware**: `platformio.ini`
  (`espressif32` 6.12.0 = ESP-IDF v5.5, board `esp32-s3-devkitc-1`,
  `src_dir = main`) reusing the same CMake/Kconfig/sdkconfig project as
  `idf.py`; the README flashing procedure split into path A (PlatformIO,
  recommended) and B (`idf.py`); the IDF-version constraint (local v5.5 vs CI
  container v5.2.2) is documented in `platformio.ini` and pinned by the new
  `test_platformio_ini_matches_project` test; legacy `driver/i2c.h` verified
  present and not deprecated on both target tags (v5.2.2 and v5.5) — no
  MPU6050 driver migration needed; path A exercised end-to-end with the first
  green local build (`pio run`: SUCCESS in 137.9 s, RAM 11.2%, 88.8% of the
  1 M factory slot)
- **WiFi hotspot for the ESP nodes** (single-radio AP+STA):
  `scripts/deploy/setup_hotspot.sh` turns the Pi's built-in WiFi into a WPA2
  AP (`ap0`) sharing the internet uplink — dnsmasq DHCP/DNS (broker hostname
  `openj5-core` → `192.168.4.1`), NAT, systemd units
  `openj5-{ap-if,hostapd,nat,channel-sync}` with a 60 s channel sync (router
  must keep a fixed 2.4 GHz channel). WiFi credentials now live in exactly
  one place (the Pi); the ESP side is the committed
  `firmware/node7_balance/sdkconfig.local.example`. Docs: DEPLOYMENT.md
  section 11, BENCH_BALANCE §6 step 0, node7 README; parity pinned by the
  new `test_hotspot_wifi_credentials_parity` (also `bash -n`s the installer)

### Changed
- **ADR-016**: Node 1 reference OS switched from Ubuntu Server to Raspberry Pi OS
  Lite 64-bit (Bookworm), primary storage NVMe on USB3 (headless-only, desktop
  variant excluded); README, ARCHITECTURE diagrams and GOALS updated accordingly

### Added
- `pyproject.toml` with ruff configuration (E4/E7/E9/F rules)
- **First real HAL driver**: `src/hardware/drivers/l298n.py` — `L298NDriver` +
  `L298NMotor` implementing the documented `IMotorDriver` shape
  (initialize/set_velocity/get_velocity/brake/shutdown) for the Nodo 6 tracks
  bench prototype; velocity normalized (-1..+1) with ramping; GPIO mapping in
  `config/bench/tracks.json` (zero magic numbers per ADR-008)
- Interactive bench demo: `scripts/demo/tracks_bench.py` (w/s/a/d steering,
  +/- speed, x stop, q quit; brake automatic on exit)
- Bench bring-up guide `docs/hardware/BENCH_TRACKS.md`: L298N↔Pi wiring tables,
  power (LiPo 3S / 12V), safety checklist, demo usage, shutdown/restart
  procedures, troubleshooting — added to CI doc gate
- DEPLOYMENT.md §11 "Daily Power Off / On (quick reference)"
- Raspberry Pi 4 deployment path rewritten for Pi OS Lite + NVMe:
  `docs/deployment/DEPLOYMENT.md` (Imager flow onto NVMe, one-time USB bootloader
  recovery via SD, memory-cgroup cmdline patch required for compose limits,
  watchdog dtparam, TRIM check, UFW hardening, RPi troubleshooting) and
  `scripts/deploy/bootstrap_rpi4.sh` (Bookworm detection with Ubuntu guard,
  idempotent cmdline/config.txt patches, reboot hint); DEPLOYMENT in CI doc gate
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
- **ADR-017 - Node 7 Balance Controller** (`docs/adr/ADR-017-node7-balance-controller.md`):
  new dedicated ESP32-S3 node keeping the body leveled vs gravity on the tracks
  (NEMA17 + A4988 STEP/DIR + MPU6050 on body, 20T->80T belt/pulley reduction,
  PID loop ~100 Hz on-node, logical MQTT commands). Extends ADR-002 (6->7 nodes)
  and ADR-005 (new IStepperDriver HAL port). ADR INDEX updated
- **HAL stepper port**: `src/hardware/hal/stepper.py` — `IStepperDriver`
  (initialize/enable/disable/set_position_steps/set_velocity_steps_s/
  get_position_steps/get_velocity_steps_s/home/brake/shutdown),
  `StepperMove`, `StepperState`, pure `trapezoid_velocity` ramp helper
- **A4988 bench driver**: `src/hardware/drivers/a4988.py` (gpiozero/lgpio
  STEP/DIR/ENABLE, acceleration-limited moves) with `config/bench/balance.json`
  (zero magic numbers per ADR-008) and demo `scripts/demo/balance_bench.py`
- **Mock stepper (CI-safe)**: `src/hardware/drivers/mock_stepper.py` — no GPIO
  dependency, same IStepperDriver contract; drives all unit tests
- **Leveling-loop simulator**: `src/hardware/sim/leveling.py` — pure-Python PID
  loop (100 Hz, deadband, track-tilt profile) to validate gains before the C++
  firmware exists
- **Domain**: `StepperConfig`/`BalanceConfig` value objects, `BodyCommand`
  (level/tilt/stow/stop), `GetBodyTiltQuery`, `GetBalanceStateQuery`,
  `BodyCommandEvent`/`BodyTelemetryEvent`/`BalanceStateChangedEvent`,
  `Stepper` entity, `NodeType.BALANCE`; exports updated
- **SDK**: `BodyAPI` (`robot.body.level()/tilt()/stow()/stop()/
  get_tilt()/get_balance_state()`) in `src/sdk/robot.py`
- **Config**: `config/node7_balance/node.json`, `stepper_driver` entry in
  `config/common/hal.json`, node7 topics in `config/common/topics.json`
- **Orchestrator**: node7 (balance) in robot_core statemachine node_types,
  health node list, API models target_node and digital_twin body joint
- **Unit tests**: `tests/unit/test_balance_control.py` — 8 tests (step math,
  ramp helper, mock motion, leveling convergence + ramp tracking, command
  validation); `tests/conftest.py` path bootstrap
- Architecture, API, CONFIGURATION, PROJECT_MEMORY, PROJECT_STATUS, ROADMAP,
  NEXT_TASK, KNOWLEDGE_BASE and CONTINUATION_PROMPT updated for Node 7

### Fixed
- First real-hardware deployment fixes (RPi4 8GB, Pi OS Lite Trixie, NVMe USB3):
  mosquitto ACL global rules for anonymous clients + deterministic pub/sub
  healthcheck; removed Dockerfile VOLUME conflicting with containerd image
  store; PYTHONPATH=/app/src for robot-core entrypoint; EventBus=IEventBus
  alias; system metrics published as typed DomainEvent; bootstrap handles
  rsync-only checkouts and Debian 13 Trixie; Grafana admin secret uses
  correct __FILE provider (single underscore was silently ignored)
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
