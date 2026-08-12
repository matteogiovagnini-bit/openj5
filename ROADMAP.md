# OpenJ5 Roadmap

> **Last updated:** 2026-07-15
> **Project:** OpenJ5 - Open-Source Johnny 5-Inspired Robot Platform

---

## Release Cadence

- **Major (1.0.0):** Public launch with full robot assembly
- **Minor (0.x.0):** Feature releases every 3-4 months
- **Patch (0.0.x):** Bug fixes and hotfixes as needed

---

## v0.2.0 — Robot Core & Infrastructure ✅ ([2026-07-15])

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
- State machine orchestrator (6 nodes)

---

## v0.3.0 — CI/CD & Testing [Q3 2026]

**Goal:** Automated quality gates and comprehensive test coverage.

### Planned
- [ ] GitHub Actions CI/CD pipeline:
  - Python lint (ruff, mypy)
  - C++ lint (clang-tidy)
  - Unit tests (pytest, 90%+ coverage on core)
  - Architecture validation (import checks, layer rules)
  - Doc generation and validation
  - Docker image build and push
  - Firmware build (ESP-IDF)
- [ ] Integration test suite:
  - REST API endpoint tests
  - WebSocket connection tests
  - Event bus round-trip tests
  - Plugin lifecycle tests
  - OTA deployment simulation
  - State machine transition tests
- [ ] Simulation parity tests:
  - Same test suite runs on real robot and Gazebo
  - Joint command/telemetry loopback
  - Sensor data simulation
- [ ] Test documentation:
  - Test plan and strategy
  - Test coverage reports
  - CI badge in README

---

## v0.4.0 — Firmware & Assembly [Q4 2026]

**Goal:** All 5 ESP32-S3 nodes functional with firmware OTA.

### Planned
- [ ] Complete firmware for Node 3 (Right Arm):
  - 6-DOF servo control with trajectory interpolation
  - Gripper servos (open/close, rotation)
  - Force sensing via current monitoring
  - Collision detection
- [ ] Complete firmware for Node 4 (Left Arm):
  - Same as Node 3 (mirrored kinematics)
- [ ] Complete firmware for Node 5 (Torso):
  - Rotation servo with absolute encoder
  - Tilt mechanism
  - Battery management system (INA219 + DS18B20)
  - LED matrix controller (WS2812)
- [ ] Complete firmware for Node 6 (Tracks):
  - Differential drive with L298N
  - Odometry calculation
  - IMU-based heading correction (MPU6050/ICM20948)
  - Speed PID control
- [ ] OTA client implementation (all nodes):
  - HTTPS firmware download
  - Signature verification
  - Fallback/rollback mechanism
  - Progress reporting
- [ ] mTLS certificate management:
  - CA setup script
  - Certificate generation for all nodes
  - Automatic renewal
- [ ] Hardware assembly documentation:
  - Bill of Materials (BOM)
  - Assembly instructions
  - Wiring diagrams
  - Calibration procedures

---

## v0.5.0 — Vision & Interaction [Q1 2027]

**Goal:** Basic computer vision and speech interaction.

### Planned
- [ ] Camera module integration:
  - Raspberry Pi Camera Module 3 (or USB camera)
  - OpenCV-based face detection
  - Object detection (TensorFlow Lite)
- [ ] Vision Plugin:
  - Face detection and tracking
  - Object recognition
  - Color tracking
  - Motion detection
- [ ] Speech Plugin:
  - Text-to-Speech (eSpeak-NG or Piper TTS)
  - Speech-to-Text (Vosk or Whisper)
  - Voice command recognition
  - Emotion detection in voice
- [ ] Face tracking behavior:
  - Head follows detected face
  - Eyes maintain eye contact
  - Smooth tracking with prediction
- [ ] Basic conversation AI:
  - Intent recognition
  - Context management
  - Personality framework

---

## v0.6.0 — Navigation & Autonomy [Q2 2027]

**Goal:** Semi-autonomous navigation and environment mapping.

### Planned
- [ ] LIDAR integration:
  - RPLIDAR A1/A2 or YDLIDAR
  - 360° obstacle detection
  - Point cloud processing
- [ ] SLAM implementation:
  - Cartographer or OpenSlam
  - Occupancy grid mapping
  - Localization (AMCL)
- [ ] Path planning:
  - A* / Dijkstra global planner
  - DWA / TEB local planner
  - Dynamic obstacle avoidance
- [ ] Person following:
  - Face/body tracking + following
  - Safe distance maintenance
  - Voice-guided following
- [ ] Auto-exploration:
  - Frontier-based exploration
  - Room detection
  - Semantic mapping

---

## v1.0.0 — Full Robot Platform [Q3 2027]

**Goal:** Complete, assembly-ready robot platform with all features.

### Planned
- [ ] Full 7-DOF arms (upgrade from 6-DOF):
  - Additional wrist DOF for dexterity
  - Higher torque servos
  - Improved kinematics solver
- [ ] Object manipulation:
  - Grasp planning
  - Pick and place
  - Object handover
- [ ] Auto-docking and recharging:
  - Dock detection (visual + IR)
  - Precision docking maneuver
  - Automatic charging circuit
  - Battery state monitoring
- [ ] Multi-sensor fusion:
  - Kalman filter for pose estimation
  - Sensor calibration pipeline
  - Redundant sensing for safety
- [ ] Production-ready documentation:
  - Complete assembly guide
  - 3D-printable STL files
  - PCB Gerber files
  - Calibration tools
  - User manual
- [ ] ROS2 integration:
  - Full ROS2 node for OpenJ5
  - ROS2 control hardware interface
  - ROS2 navigation stack
  - ROS2 manipulation stack
- [ ] Web dashboard:
  - Real-time robot visualization
  - Joint teleoperation
  - Camera feed
  - Log viewer
  - System configuration UI

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
