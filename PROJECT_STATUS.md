# OpenJ5 Project Status

## Repository: `PRJ_OpenJ5`

> **Last updated:** 2026-10-09
> **Status:** 🟡 In Development (v0.2.0 → v0.3.0) — **Robot Core operativo su hardware reale dal 2026-08-26; design Node 7 Balance (ADR-017) consegnato il 2026-09-21; T-003 unit test core domain completati il 2026-09-22 (100% coverage); T-026 firmware Node 7 Balance consegnato il 2026-09-23 (ESP-IDF, build locale PlatformIO verde, CI build); T-029 parità Python↔firmware Node 7 completata il 2026-10-07; **ADR-019 (2026-10-09): tutti i nodi ESP32-S3, il Pi è solo cervello** — bring-up motori del Node 6 portato sul firmware ESP32-S3 (`firmware/node6_tracks/`), ritirato il percorso host Pi (`l298n.py`/bench); suite Python a **197 test, 100% coverage** (i 2 moduli di test del driver Pi rimossi con il codice)**

---

## Overview

OpenJ5 is an open-source Johnny 5-inspired robot platform with a 7-node distributed architecture (6 original + **Node 7 Balance Controller**, ADR-017), Hexagonal Architecture, Plugin System, and full parametric CAD/KiCad electronics. The project targets professional-grade robotics development with a 10-year lifespan.

## Status by Component

### 🟢 Software Architecture
| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| Domain Model (value objects, events, commands, entities, services) | ✅ Done | 100% | All value objects, events, CQRS bus, entities, repositories, kinematics service — **verified by `tests/unit/` (141 test raccolti nei 6 moduli domain, T-003)** |
| Unit test suite (`tests/unit/`, core.domain) | ✅ Done | 100% | pytest + pytest-cov; 11 moduli + conftest; **197 test totali** (141 domain + 11 balance + 9 config-sync + 9 stepper parity + 27 motori T-025, dal 2026-10-09; i test del driver L298N host sono stati rimossi con il codice, ADR-019); CI gate ≥90% (`python-tests` job) |
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
| Common ESP-IDF Component | 🟢 Functional | 70% | Real component: `motor_logic` (clamp/mapping/ramp), stepper logic, Madgwick, ADR-009 FSM, balance PID (host-tested, **53 checks**), L298N/A4988/MPU6050/WiFi/MQTT glue; CMakeLists lists only existing files |
| Node 2 (Head) - CMakeLists | 🟡 Partial | 70% | Project structure only — not buildable (T-014) |
| Node 2 (Head) - main.cpp | 🟡 Partial | 10% | `firmware/node2_head/src/main.cpp` esiste (113 righe) ma include `head_controller.hpp`, che non esiste → non buildable (T-014) |
| Node 3-5 Firmware | 🔴 Not Started | 0% | Structure defined, no implementation |
| Node 6 (Tracks) - Firmware | 🟡 Partial | 60% | Bring-up motori ESP32-S3 (ADR-019, T-022): `firmware/node6_tracks/` (project ESP-IDF/PlatformIO env `node6`), `L298NDriver` ESP32-S3 (LEDC 1000 Hz/10 bit), comandi MQTT `forward/backward/spin_left/spin_right/stop`, watchdog 1000 ms → short-brake, E-stop, telemetria/state; `motor_logic.hpp` (parità con `motor.py`, T-032). **Restano**: encoder/PID/odometria/IMU/ToF/bumper e motion primitives (T-022); validazione on-device da fare |
| Node 7 (Balance) - Firmware | 🟢 Done | 80% | Full ESP-IDF project `node7_balance/` (T-026): control 100 Hz, IMU 200 Hz, logical commands, fail-safes; first local build green (`pio run`, IDF 5.5: SUCCESS 137.9 s, RAM 11.2%); CI (`firmware-node7-build`, IDF 5.2.2) green on first run (CI #21, 2026-09-27); flashing: VSCode+PlatformIO (`platformio.ini`, IDF 5.5) or `idf.py`; **on-device validation pending (bench)** |
| CI firmware jobs | ✅ Done | 100% | `firmware-host-tests` (g++) + `firmware-node7-build` (ESP-IDF v5.2.2 container) |
| OTA Update Client | 🟡 Partial | 40% | Protocol defined, download logic pending |

### 🟢 Architettura Decisioni
| ADR | Status | Notes |
|-----|--------|-------|
| ADR-001: Hexagonal Architecture | ✅ Accepted | Core domain zero external deps |
| ADR-002: 7-Node Distributed Architecture | ✅ Accepted | RPi4 + 6× ESP32-S3 (ADR-017 adds Node 7 Balance) — **MCU table superseded by ADR-019 (all nodes ESP32-S3)** |
| ADR-003: Communication Gateway Pattern | ✅ Accepted | Single ICommunicationGateway interface |
| ADR-004: Event-Driven Architecture | ✅ Accepted | Redis Streams central event bus |
| ADR-005: HAL for All Drivers | ✅ Accepted | Hardware Abstraction Layer |
| ADR-006 .. ADR-016 | ✅ Accepted | 11 ADR aggiuntivi (SDK, plugin, config, state machine, digital twin, OTA, FreeCAD, security, Python/C++, MQTT, Pi OS Lite+NVMe) — vedi docs/adr/INDEX.md |
| ADR-017 | ✅ Accepted | Node 7 Balance Controller: NEMA17 + A4988 + MPU6050, body leveled vs gravity |
| ADR-018 (New) | ✅ Accepted | Motor HAL Port (`IMotorDriver`): contract shape, placement in `src/hardware/hal/`, Python↔C++ parity target (2026-10-09) |
| ADR-019 (New) | ✅ Accepted | **All nodes ESP32-S3; the Raspberry Pi is brain only** — supersedes ADR-002 MCU table; retires the host Pi motor path; Node 6 actuation on the ESP32-S3 (2026-10-09) |

### 🟡 Node 6 (Tracks) — ESP32-S3 + firmware bring-up motori (ADR-019)
| Component | Status | Notes |
|-----------|--------|-------|
| Pi brain-only / attuazione su ESP32-S3 | ✅ Done | **ADR-019** (Accepted 2026-10-09): tutti i nodi ESP32-S3; il Pi non tocca mai GPIO/PWM, invia solo comandi logici via MQTT |
| Firmware Node 6 (bring-up motori) | ✅ Done | `firmware/node6_tracks/` (ESP-IDF/PlatformIO env `node6`, board `esp32-s3-devkitc-1`): `app_main`, `track_controller`, `command_handler`, Kconfig; comandi `forward/backward/spin_left/spin_right/stop`, watchdog 1000 ms → short-brake, E-stop, telemetria 1 Hz/state |
| Driver L298N ESP32-S3 (C++) | ✅ Done | `firmware/common/drivers/l298n_driver.{hpp,cpp}` (LEDC 1000 Hz/10 bit, rampa nel task di controllo) |
| Motor HAL C++ + parità | ✅ Done (parita) | `firmware/common/include/hal/motor_driver.hpp` + `motor_logic.hpp` (`clamp_velocity`/`motor_levels`/`ramp_schedule`), specchio di `src/hardware/hal/motor.py` (T-032); host test in `host_test.cpp` (53 checks) |
| Port HAL `IMotorDriver` (host) | ✅ Done | `src/hardware/hal/motor.py` (ADR-018) — resta come astrazione host/Digital Twin e contratto di parità |
| Mock CI-safe (host) | ✅ Done | `src/hardware/drivers/mock_motor.py` (`MockMotorDriver`, Digital Twin) |
| Config pin + PWM/rampa | ✅ Done | `config/node6_tracks/node.json` (pin S3 approvati, `pwm_frequency_hz` 1000, `ramp_step`/`ramp_seconds`) ↔ `main/Kconfig.projbuild` |
| Test motori host | ✅ Done | `tests/unit/test_motor_hal.py`, `test_mock_motor.py` (27 test); il firmware C++ è coperto da `host_test.cpp` |
| Guida cablaggio | ✅ Done | `docs/hardware/NODE6_ESP32_WIRING.md` (ESP32-S3↔L298N) + `docs/hardware/BENCH_TRACKS.md` (banco) |
| Percorso Pi rimosso | ✅ Done | `src/hardware/drivers/l298n.py`, `scripts/demo/tracks_bench.py`, `config/bench/tracks.json` e i 2 moduli di test del driver Pi **eliminati** (ADR-019) |
| Encoder/PID/odometria/IMU/ToF/bumper | ⬜ Da fare | **T-022** (pin già in config/Kconfig, non ancora usati dal firmware) |
| Primo movimento fisico su ESP32-S3 | 🟡 Parziale | Bring-up motori pronto (codice+config+parità); **resta la validazione on-device** (ruote sollevate) — T-033 |

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
| Test | ✅ Done | `tests/unit/test_balance_control.py` — 11 test verdi (Python 3.11, ruff clean) |
| Test di parità firmware | ✅ Done | `tests/unit/test_stepper_parity.py` — 9 test Python↔`host_test.cpp` (T-029, 2026-10-07) |
| Firmware ESP-IDF | ✅ Done | T-026 (2026-09-23) — `firmware/node7_balance/` completo, logica host-testata (suite host: 53 check), build in CI; validazione su hardware = prossimo step bench |
| Guida cablaggio | ✅ Done | `docs/hardware/BENCH_BALANCE.md` (pin, alimentazione, Vref, safety, bring-up) |
| Config parity test | ✅ Done | `tests/unit/test_node7_config_sync.py` — Kconfig ↔ node.json ↔ docs |
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
| ADR Index (completo) | ✅ Done | ADR-001 to ADR-019 — vedi docs/adr/INDEX.md |
| BENCH_TRACKS (hardware) | ✅ Done | Guida banco Nodo 6 su ESP32-S3: cablaggio motori, power, safety (ADR-019) |
| NODE6_ESP32_WIRING (hardware) | ✅ Done | Schema ESP32-S3↔L298N: tabella pin, diagramma Mermaid, note elettriche, encoder/I2C/ToF/bumper (T-022), bring-up |
| BENCH_BALANCE (hardware) | ✅ Done | Guida banco Nodo 7: pin NEMA17/A4988/MPU6050, alimentazione, Vref, math, safety |
| Development Constitution | ✅ Done | Level A/B/C governance |
| VISION / MISSION / GOALS / NON_GOALS | ✅ Done | Project governance |
| CODING_STANDARD / NAMING_CONVENTIONS | ✅ Done | Code quality rules |

### 🔴 Not Started (Next Releases)
| Component | Priority | Target Release |
|-----------|----------|----------------|
| CI/CD Pipeline (GitHub Actions) | High | v0.3.0 — 🟡 lint + unit tests (cov ≥90%) + doc-check + docker build + firmware host tests + node7 build attivi; mancano mypy/clang-tidy |
| Integration Tests (T-004/T-005) | High | v0.3.0 — sbloccati da T-003 (saltati su richiesta 2026-09-23) |
| Simulation Test Suite (T-006) | High | v0.3.0 |
| Firmware Nodes 3-5 | High | v0.4.0 (Node 7 done; Node 6 bring-up motori done, sensors/PID = T-022; Node 2 blocked by T-014) |
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
| Unit tests (core.domain) | ≥90% coverage | **197 tests, 100% coverage** (141 domain + 11 balance + 9 config-sync + 9 stepper parity + 27 motors T-025) |
| Firmware C++ files | - | 31 (15 .cpp + 16 .hpp: `firmware/common` + `node2_head` skeleton + `node6_tracks` + `node7_balance`) |
| Config files (JSON/YAML) | - | 12 |
| Docker services | - | 10 |
| Plugins framework | - | 14 interface types |
| ADRs | - | 19 |
| Documentation files | - | 26+ |

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
- Unit test suite for the core domain (T-003, evoluto): **197 unit tests** (141 in `core.domain` + balance/config/parity + 27 motor HAL/mock), 100% line coverage, CI coverage gate ≥90%
- Node 7 Balance Controller design (ADR-017): HAL IStepperDriver, A4988 bench driver + mock, leveling-loop simulator, BodyAPI SDK, configs + topics, unit tests
- Node 7 Balance firmware (T-026): wiring guide `BENCH_BALANCE.md`, pure logic in `firmware/common/` (host-tested, 53 checks), complete ESP-IDF project `firmware/node7_balance/` with CI build (`firmware-host-tests` + `firmware-node7-build`), config parity test Kconfig↔node.json, flashing via VSCode+PlatformIO (`platformio.ini`) or `idf.py`
- Python↔firmware motion parity (T-029, 2026-10-07): `slew`/`brake_bound`/`position_velocity_target` mirrored in `src/hardware/hal/stepper.py`, stateful `trapezoid_velocity` (caller-owned `v_now`), no-D-kick leveling PID + ±1600 clamp, `tests/unit/test_stepper_parity.py` (9 tests)
- **ADR-019 (2026-10-09) — all nodes ESP32-S3, the Pi is brain-only**: supersedes the ADR-002 MCU table; the Pi never actuates. Host Pi motor path removed (`src/hardware/drivers/l298n.py`, `scripts/demo/tracks_bench.py`, `config/bench/tracks.json`, related tests)
- **Node 6 Tracks firmware bring-up (ADR-019, T-022)**: `firmware/node6_tracks/` (ESP-IDF/PlatformIO env `node6`) with MQTT logical commands (`forward/backward/spin_left/spin_right/stop`), ESP32-S3 `L298NDriver` (LEDC 1000 Hz/10 bit), command watchdog 1000 ms → short-brake, system E-stop, telemetry/state; wiring guide `NODE6_ESP32_WIRING.md` + `BENCH_TRACKS.md`; C++ motor HAL (`motor_driver.hpp`/`motor_logic.hpp`, T-032) mirroring `src/hardware/hal/motor.py`; 27 new host tests (`test_motor_hal.py`, `test_mock_motor.py`)

### What's Next (v0.3.0)
- Integration tests (REST/WS, event bus + state machine)
- Simulation parity tests
- Hardware-in-loop tests
- Node 6 on-device validation + encoders/PID/odometry/IMU/ToF/bumpers (T-022 / T-033)

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
