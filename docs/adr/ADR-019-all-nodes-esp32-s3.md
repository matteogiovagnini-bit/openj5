# ADR-019: Standardize All Nodes on ESP32-S3 (the Raspberry Pi Is Brain Only)

## Status
Accepted

## Context
ADR-002 defined the distributed architecture with a mixed MCU fleet: ESP32-S3 on
the compute/actuator-heavy nodes (Node 2 Head, Node 3 Right Arm, Node 4 Left Arm)
and classic ESP32 on Node 5 (Torso) and Node 6 (Tracks). That split was a
cost/feature trade-off made at design time, not a hardware constraint.

Two facts have since changed the picture:

1. **The real hardware is all ESP32-S3.** The physical fleet is being built (and
   will be maintained for years) with a single module family. Maintaining two MCU
   targets doubles the firmware build matrix, the OTA rollout, the pin
   constraints, and the toolchain/sdkconfig surface for no functional gain.
2. **Node 7 already broke the split.** ADR-017 introduced the Balance Controller
   on an ESP32-S3 and explicitly extends ADR-002 to 7 nodes. The "classic ESP32 on
   some nodes" rule is therefore already inconsistent with the delivered design.

The owner has taken an explicit **Level C decision**: *all nodes are ESP32-S3; the
Raspberry Pi (Node 1) is only the brain; motors and actuators must be driven by
the ESP32-S3 nodes, never by the Pi.*

This matters beyond hardware selection: today the T-025 bench prototype lets the
**Pi drive the track motors directly** through `src/hardware/drivers/l298n.py` +
`scripts/demo/tracks_bench.py` + `config/bench/tracks.json` (host GPIO/L298N).
That is a bench bring-up artifact that contradicts the intended actuation
boundary and the deterministic real-time requirement (ADR-002/ADR-014), and it
must be retired in favour of the Node 6 ESP32-S3 firmware.

## Decision

### 1. One MCU family: ESP32-S3 on every node

All actuator/sensor nodes run **ESP32-S3**. The MCU column of ADR-002 is replaced
by the table below (ADR-002 remains valid elsewhere; only its MCU table is
superseded by this ADR).

| Node | MCU | Responsibility |
|------|-----|----------------|
| **Node 1** | Raspberry Pi 4 8GB | Robot Core / **brain only**: AI, vision, speech, planning, behavior, MQTT broker, config, logging, DB, REST/WS, plugin manager, Digital Twin, OTA server, scheduler (ADRs 002, 016) |
| **Node 2** | **ESP32-S3** | Head: 6 servos, LED, display, mics, IMU, ToF, temp |
| **Node 3** | **ESP32-S3** | Right arm: 6 servos |
| **Node 4** | **ESP32-S3** | Left arm: 6 servos (mirrored) |
| **Node 5** | **ESP32-S3** | Torso: 4 servos, LED strip, fan, battery monitor (INA219), temp (DS18B20), IMU, ToF, proximity |
| **Node 6** | **ESP32-S3** | Tracks: 2x DC motor, encoders, IMU, 2x ToF, collision sensors |
| **Node 7** | **ESP32-S3** | Balance Controller (ADR-017) |

### 2. Actuation boundary: Pi = brain, ESP32-S3 = actuation

- No node actuates motors/servos **from the Pi**. The Pi never touches GPIO/I2C/PWM
  for actuation; it speaks **logical commands only** over MQTT
  (`openj5/v1/...`, ADR-006/ADR-015).
- Each ESP32-S3 node translates logical commands into local trajectories/loops and
  drives its own actuators, with the hard real-time guarantees it needs
  (e.g. 1-5 ms motor/servo loop for Node 6, per ADR-002).
- The Python host motor drivers are **removed**: `src/hardware/drivers/l298n.py`,
  `scripts/demo/tracks_bench.py` and `config/bench/tracks.json` are retired with
  the T-025 bench bring-up (see Consequences).
- The Python HAL port `IMotorDriver` and the `MockMotorDriver` **stay** as the
  host/Digital-Twin abstraction and as the **Python↔C++ parity contract** against
  the ESP-IDF motor logic (ADR-005/ADR-010/ADR-018).

### 3. Approved Node 6 pin map (authoritative)

The Node 6 pin map below is approved and **valid for the ESP32-S3**. It replaces
the classic-ESP32 pin assignment currently in `config/node6_tracks/node.json`.

| Signal | GPIO | Notes |
|--------|------|-------|
| ENA (left PWM) | 4 | LEDC PWM, 1000 Hz / 10 bit |
| IN1 (left) | 5 | Direction |
| IN2 (left) | 6 | Direction |
| ENB (right PWM) | 7 | LEDC PWM, 1000 Hz / 10 bit |
| IN3 (right) | 15 | Direction |
| IN4 (right) | 16 | Direction |
| Encoder left A / B | 8 / 9 | Quadrature input |
| Encoder right A / B | 10 / 11 | Quadrature input |
| I2C SDA / SCL | 1 / 2 | Shared IMU + ToF bus |
| ToF XSHUT front / rear | 12 / 13 | VL53L0X addressing |
| Bumper front | 14, 17 | Collision input |
| Bumper rear | 18, 21 | Collision input |

PWM: **LEDC, 1000 Hz, 10-bit** resolution (ADR-008: no magic numbers; these values
live in config, not in code).

### 4. ESP32-S3 pin-safety rules (all node pin maps must satisfy)

Any node pin map must avoid the following ESP32-S3 reserved/unusable pins:

- **GPIO 22-25** - do not exist on ESP32-S3.
- **GPIO 19 / 20** - native USB D-/D+ (USB-Serial-JTAG).
- **GPIO 26-32** - SPI flash (SPI0/1).
- **GPIO 33-37** - octal PSRAM (on N8R8-class modules).
- **GPIO 43 / 44** - UART0 TX/RX (console/flash).
- **Strapping pins 0 / 3 / 45 / 46** - avoid for general use.

The Node 6 map in §3 uses only safe pins (1-18, 21). The current
`config/node6_tracks/node.json` violates these rules (e.g. GPIO 22/23, encoder
GPIO 34/35/36/39, bumper GPIO 25/26/27/33) and must be regenerated.

## Alternatives Considered
1. **Keep the mixed ESP32 / ESP32-S3 fleet (ADR-002 as written)** - Rejected: the
   physical fleet is all ESP32-S3; keeping two targets multiplies firmware builds,
   OTA images and pin-constraint matrices for no benefit, and Node 7 already broke
   the split (ADR-017).
2. **Let the Pi drive actuators for "simple" nodes (keep the L298N host driver)** -
   Rejected by the owner (Level C): Linux is not real-time, it centralizes
   actuation failure onto Node 1, and it violates the local-reflex/real-time
   design (ADR-002/ADR-014). It also contradicts the "logical commands only" rule
   (ADR-006).
3. **ESP32-P4 / STM32 per node** - Deferred: possible future per-node upgrade, and
   the HAL (ADR-005) keeps it a driver/config swap; not needed for the current
   fleet.
4. **Keep `l298n.py` as a "reference adapter" only** - Rejected: dead code on the
   actuation path; the host abstraction (port + mock) already covers testing and
   Digital Twin. Keeping a working host motor driver invites accidental use.
5. **Repurpose the Pi GPIO for actuators in simulation** - Rejected: simulation is
   the `MockMotorDriver`/Gazebo adapter, not host GPIO (ADR-010).

## Consequences
**Positive:**
- One MCU family → one firmware toolchain, one sdkconfig policy, one OTA flow, one
  pin-constraint ruleset across all nodes.
- Clean brain/actuation boundary: the Pi stays soft-real-time orchestration; all
  hard real-time actuation lives on the ESP32-S3 (ADR-002/ADR-014).
- Consistent with Node 7 (already ESP32-S3, ADR-017) and with the delivered fleet.

**Negative / work required:**
- (a) **Pin maps must be re-validated for S3** on every node (no GPIO 22-25, no
   USB 19/20, no flash 26-32, no octal-PSRAM 33-37, no UART0 43/44, no strapping
   0/3/45/46).
- (b) `config/node6_tracks/node.json` must be updated to the approved Node 6 map
   (§3) and S3-valid values throughout.
- (c) The Python Pi-side motor path is **removed**: `src/hardware/drivers/l298n.py`,
   `scripts/demo/tracks_bench.py`, `config/bench/tracks.json` (and the related
   tests and config entries). The T-025 bench approach is superseded by the Node 6
   ESP32-S3 firmware.
- (d) `IMotorDriver` + `MockMotorDriver` remain as the host/Digital-Twin
   abstraction and the Python↔C++ parity contract (ADR-018); the *real* driver is
   now the ESP-IDF firmware on Node 6.
- (e) Tasks impacted: **T-022** (Firmware Node 4/5/6) now targets ESP32-S3 and owns
   the real Node 6 motor firmware; **T-032** (C++ motor HAL parity) becomes the
   parity link between `src/hardware/hal/motor.py` and the Node 6 firmware; T-031
   (A4988 default path) is affected only insofar as the host demo path is removed.

## Implementation Notes
- Documentation to regenerate (continuous documentation, P13 / CODING_STANDARD §8):
  ADR-002 MCU table (superseded by §1 here - do not edit ADR-002, reference this
  ADR), `README.md`, `PROJECT_STATUS.md`, `docs/architecture/ARCHITECTURE.md`
  (Deployment / Component / Hardware diagrams), `docs/configuration/CONFIGURATION.md`
  (the Pi-BCM bench section, lines ~642-671), `ROADMAP.md`, `governance/VISION.md`
  ("5× ESP32" wording), `governance/CONSTRAINTS.md` (Nodi 5-6 "ESP32 classico"),
  `governance/GOALS.md` (Node 5/6 headers).
- Firmware: the Node 6 ESP-IDF project implements the real motor driver (LEDC PWM
  1000 Hz / 10 bit, encoder PID, IMU odometry) using the pin map in §3; `motor_driver.hpp`
  + `motor_logic.hpp` mirror `src/hardware/hal/motor.py` (T-032, linked to T-022).
- Config: move the approved pins into `config/node6_tracks/node.json`; keep
  `config/common/hal.json` driver selection; remove the host bench config.
- No new Python actuation code; the host motor port/mock stay for tests/parity only.

## Related ADRs
- ADR-002: 6-Node Distributed Architecture (**amended**: supersedes its MCU table, mixed ESP32/ESP32-S3)
- ADR-005: Hardware Abstraction Layer (HAL unchanged; actuators still behind ports)
- ADR-006: Robot SDK Facade (Pi sends logical commands only)
- ADR-014: Python Core + C++ Firmware (real-time actuation on firmware)
- ADR-015: MQTT as Primary Transport (`openj5/v1/...` logical commands)
- ADR-016: Raspberry Pi OS Lite Node 1 (Node 1 remains the only Pi)
- ADR-017: Node 7 Balance Controller (precedent: ESP32-S3 for actuation nodes)
- ADR-018: Motor HAL Port (host port + mock remain; real driver is now Node 6 firmware)
