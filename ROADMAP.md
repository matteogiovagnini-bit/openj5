# OpenJ5 Roadmap

> **Last updated:** 2026-10-09
> **Project:** OpenJ5 - Open-Source Johnny 5-Inspired Robot Platform

---

## Release Cadence

- **Major (1.0.0):** Public launch with full robot assembly
- **Minor (0.x.0):** Feature releases every 3-4 months
- **Patch (0.0.x):** Bug fixes and hotfixes as needed

---

## v0.2.0 — Robot Core & Infrastructure ✅ (2026-07-15)

**Goal:** Fully functional Robot Core on Raspberry Pi 4 with all infrastructure services.

### Complete
- Robot Core Python package (all services)
- REST API v1 + WebSocket
- Docker Compose with 10 services
- Infrastructure configs (MQTT, DB, monitoring, logging, tracing)
- Health monitoring system
- OTA firmware management
- Plugin lifecycle management
- Digital twin / simulation bridge
- State machine orchestrator (6 nodes, +1 balance in ADR-017)
- **Deployed on real hardware:** RPi4 8GB, Pi OS Lite 64-bit (Bookworm/Trixie) on NVMe USB3, boot USB native, stack healthy, API HTTPS live (2026-08-26, ADR-016)

---

## v0.3.0 — CI/CD & Testing [Q3 2026]

**Goal:** Automated quality gates and comprehensive test coverage.

### Completed ✅
- Python lint (ruff) + doc-check (`scripts/check_docs.sh`) in CI
- Docker build gate for robot-core in CI
- Unit test suite (`tests/unit/`): **197 tests**, 100% coverage on `core.domain` (gate ≥90%)
- Firmware host tests (`scripts/test/host_firmware.sh`): **53 checks** in CI (`firmware-host-tests` job)
- Node 7 Balance firmware ESP-IDF build in CI (`firmware-node7-build` job, `espressif/idf:v5.2.2`) — green since CI #21 (2026-09-27)
- Config parity test `tests/unit/test_node7_config_sync.py` (9 tests)
- Python↔C++ firmware parity for Node 7 stepper/motion/PID (T-029, 2026-10-07): `test_stepper_parity.py` (9 tests)
- ADR-019 (2026-10-09): All nodes ESP32-S3, Pi brain-only — supersedes ADR-002 MCU table

### Planned / In Progress 🟡
- [ ] GitHub Actions CI/CD pipeline completion:
  - [ ] Python type checking (mypy)
  - [ ] C++ lint (clang-tidy)
  - [ ] Architecture validation (import checks, layer rules)
  - [ ] Doc generation and validation
  - [ ] Docker image build and push
- [ ] Integration test suite (unblocked by T-003, skipped on request 2026-09-23):
  - [ ] REST API endpoint tests
  - [ ] WebSocket connection tests
  - [ ] Event bus round-trip tests
  - [ ] Plugin lifecycle tests
  - [ ] OTA deployment simulation
  - [ ] State machine transition tests
- [ ] Simulation parity tests:
  - [ ] Same test suite runs on real robot and Gazebo
  - [ ] Joint command/telemetry loopback
  - [ ] Sensor data simulation
- [ ] Test documentation:
  - [ ] Test plan and strategy
  - [ ] Test coverage reports
  - [ ] CI badge in README
- [ ] Node 6 on-device validation (T-033): flash `firmware/node6_tracks/` on ESP32-S3, wheels off ground, verify MQTT commands, watchdog, E-stop

---

## v0.4.0 — Firmware & Assembly [Q4 2026]

**Goal:** All 7 ESP32-S3 nodes functional with firmware OTA.

### Node 7 Balance (ADR-017) ✅
- Firmware ESP-IDF complete (`firmware/node7_balance/`): 100 Hz control + 200 Hz IMU, logical commands level/tilt/stow/stop, fail-safes
- Build in CI (`firmware-node7-build`, IDF 5.2.2) and local (`pio run`, IDF 5.5) — both green
- Wiring guide `docs/hardware/BENCH_BALANCE.md`
- **Remaining:** on-device bench validation (Vref, PID ratification, first pulses)

### Node 6 Tracks (ADR-019) 🟡
- Bring-up firmware delivered (`firmware/node6_tracks/`, env `node6`): L298N LEDC 1000 Hz/10 bit, MQTT commands, 1000 ms watchdog → short-brake, E-stop
- C++ Motor HAL in `firmware/common/` (`motor_driver.hpp`, `motor_logic.hpp`, `drivers/l298n_driver.cpp`) — mirrors `src/hardware/hal/motor.py`
- Wiring guides: `docs/hardware/NODE6_ESP32_WIRING.md` + `docs/hardware/BENCH_TRACKS.md`
- **Remaining (T-022 / T-033):**
  - Encoder quadrature (GPIO 8/9, 10/11), PID velocity, odometry
  - IMU (MPU6050, I2C 1/2), ToF (VL53L0X ×2, XSHUT 12/13)
  - Bumper sensors (GPIO 14/17, 18/21)
  - Motion primitives (move_forward, rotate, arc, dock)
  - On-device validation (T-033)

### Planned
- [ ] Complete firmware for Node 2 (Head): 6 servos (PCA9685), LED, display, mics, sensors — **blocked by T-014** (skeleton not compilable: missing `head_controller.hpp`)
- [ ] Complete firmware for Node 3 (Right Arm): 6 servos, trajectory interpolation, gripper, collision detection
- [ ] Complete firmware for Node 4 (Left Arm): Mirrored Node 3
- [ ] Complete firmware for Node 5 (Torso): 4 servos, INA219/DS18B20, LED, fan, sensors
- [ ] OTA client implementation (all nodes): HTTPS download, signature verification, rollback, progress reporting
- [ ] mTLS certificate management: CA setup, cert generation for all 7 nodes, automatic renewal
- [ ] CAD/mechanics for body pitch joint (ADR-012/ADR-017): Belt/pulley 20T→80T, tilt ±35°
- [ ] Hardware assembly documentation: BOM, assembly instructions, wiring diagrams, calibration procedures

---

## v0.5.0 — Vision & Interaction [Q1 2027]

**Goal:** Basic computer vision and speech interaction.

### Planned
- [ ] Camera module integration: Raspberry Pi Camera Module 3 / USB camera
- [ ] Vision Plugin: face detection/tracking, object recognition (TensorFlow Lite), color tracking, motion detection
- [ ] Speech Plugin: TTS (eSpeak-NG/Piper), STT (Vosk/Whisper), voice commands, emotion detection — *voice front-end already realized as an external satellite: Note 10 + Home Assistant + Wyoming Piper/faster-whisper, ADR-020 (`voice_satellite/`); the robot-side plugin (T-024) and the voice→MQTT command contract (T-034) remain*
- [ ] Face tracking behavior: head follows face, eye contact, smooth prediction
- [ ] Basic conversation AI: intent recognition, context management, personality framework

---

## v0.6.0 — Navigation & Autonomy [Q2 2027]

**Goal:** Semi-autonomous navigation and environment mapping.

### Planned
- [ ] LIDAR integration: RPLIDAR A1/A2 or YDLIDAR, 360° obstacle detection, point cloud processing
- [ ] SLAM: Cartographer/OpenSlam, occupancy grid, localization (AMCL)
- [ ] Path planning: A*/Dijkstra global, DWA/TEB local, dynamic obstacle avoidance
- [ ] Person following: face/body tracking, safe distance, voice-guided
- [ ] Auto-exploration: frontier-based, room detection, semantic mapping

---

## v1.0.0 — Full Robot Platform [Q3 2027]

**Goal:** Complete, assembly-ready robot platform with all features.

### Planned
- [ ] Full 7-DOF arms (upgrade from 6-DOF): additional wrist DOF, higher torque servos, improved IK
- [ ] Object manipulation: grasp planning, pick and place, object handover
- [ ] Auto-docking and recharging: dock detection (visual + IR), precision maneuver, auto charging, battery monitoring
- [ ] Multi-sensor fusion: Kalman filter pose estimation, sensor calibration pipeline, redundant sensing
- [ ] Production-ready documentation: assembly guide, STL files, PCB Gerbers, calibration tools, user manual
- [ ] ROS2 integration: full ROS2 node, ros2_control hardware interface, nav stack, manipulation stack
- [ ] Web dashboard: real-time visualization, joint teleoperation, camera feed, log viewer, system config UI

---

## v1.1.0+ — Advanced Features [2028+]

**Long-term vision items.**
- Multi-robot coordination
- Swarm behaviors
- Advanced AI (LLM integration, task planning)
- Cloud connectivity and remote operation
- Skill learning and adaptation
- Developer SDK and marketplace
- Community plugins and extensions

---

## Legend

| Icon | Meaning |
|------|---------|
| ✅ | Completed |
| 🟡 | In Progress |
| 🔴 | Blocked |
| ⬜ | Not Started |