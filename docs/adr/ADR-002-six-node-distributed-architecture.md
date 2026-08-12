# ADR-002: 6-Node Distributed Architecture

## Status
Accepted

## Context
OpenJ5 robot requires controlling:
- AI/Vision/Speech/Planning (heavy compute)
- Head: 6 servos + LED + Display + 2 Mics + Sensors
- Right Arm: 6 servos
- Left Arm: 6 servos (mirrored)
- Torso: 4 servos + LED + Fan + Battery Monitor + Sensors
- Tracks: 2 DC motors + encoders + IMU + ToF + collision sensors

Single SBC (Raspberry Pi) cannot handle all real-time servo control + AI + communication reliably.

## Decision
Distribute across **6 specialized nodes** communicating via **Message Bus (MQTT)**:

| Node | Hardware | Responsibility | Real-time Requirements |
|------|----------|----------------|------------------------|
| **Node 1** | Raspberry Pi 4 8GB | Robot Core: AI, Vision, Speech, Planning, Behavior, MQTT Broker, Config, Logging, DB, REST API, WebSocket, Plugin Manager, Digital Twin, OTA, Scheduler | Soft real-time (100ms) |
| **Node 2** | ESP32-S3 | Head Controller: 6 servos (Neck Y/P/R, Eyes H/V, Eyelids), LED, Display, 2x I2S Mic, IMU, ToF, Temp | Hard real-time (1-5ms servo loop) |
| **Node 3** | ESP32-S3 | Right Arm Controller: 6 servos (Shoulder P/R/Rot, Elbow, Wrist, Gripper) | Hard real-time (1-5ms) |
| **Node 4** | ESP32-S3 | Left Arm Controller: Mirrored Right Arm | Hard real-time (1-5ms) |
| **Node 5** | ESP32 | Torso Controller: 4 servos (Torso Rot, Pitch, Battery Door, Expansion), LED Strip, Fan, Battery Monitor (INA219), Temp (DS18B20), IMU, ToF, Proximity | Soft real-time (10-50ms) |
| **Node 6** | ESP32 | Track Controller: 2x DC Motor (L298N→TB6612/BTS7960/ODrive), Encoders, IMU, 2x ToF, Collision Sensors | Hard real-time (1-5ms motor loop) |

**Communication:**
- All nodes ↔ Node 1 via MQTT over TLS/mTLS
- **Logical commands only** (e.g., `look_at`, `wave`, `move_forward`) - **NO servo angles**
- Each ESP32 translates logical commands → servo/motor trajectories locally
- Event Bus for async events (FaceDetected, BatteryLow, CollisionDetected)

## Alternatives Considered
1. **Single Pi + I2C/PWM HATs** - Rejected: Pi Linux not real-time, servo jitter, single point of failure
2. **Pi + Microcontroller (1 ESP32 for all servos)** - Rejected: 22+ servos exceed single ESP32 PWM/I2C capacity, wiring nightmare
3. **ROS 2 on all nodes** - Rejected: ESP32 ROS 2 (micro-ROS) immature, overhead high, not all nodes need ROS
4. **CAN Bus** - Rejected: Wiring complexity, overkill for servo control, MQTT over WiFi sufficient

## Consequences
**Positive:**
- Real-time servo/motor control on dedicated MCUs (FreeRTOS + ESP-IDF)
- Fault isolation: Head failure ≠ Arm failure ≠ Track failure
- Scalable: Add nodes without changing existing ones
- Hardware replacement: Swap ESP32-S3 → ESP32-P4 / STM32H7 per node independently
- Parallel development: Teams can work on different nodes independently

**Negative:**
- Distributed system complexity (clock sync, network partitions, eventual consistency)
- More firmware images to build/deploy/OTA
- Network latency for cross-node coordination (mitigated: local reflexes on ESP32)
- Configuration management across 6 nodes

## Implementation Notes
- **Node 1**: Ubuntu Server 24.04 LTS, Docker Compose, Python 3.11+, ROS 2 Humble/Iron
- **Nodes 2-6**: ESP-IDF v5.2+, FreeRTOS, C++20, MQTT (ESP-MQTT), OTA (ESP HTTPS OTA)
- **Time Sync**: NTP on Pi → MQTT time sync to ESP32s (periodic)
- **State Machine**: All nodes implement identical BOOT→INIT→READY→RUNNING→ERROR→RECOVERY→SHUTDOWN

## Related ADRs
- ADR-003: Communication Gateway Pattern
- ADR-009: State Machine per Node
- ADR-011: OTA with Signed Firmware
- ADR-015: MQTT as Primary Transport