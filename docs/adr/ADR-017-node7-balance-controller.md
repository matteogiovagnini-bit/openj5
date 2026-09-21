# ADR-017: Node 7 Balance Controller (Self-Leveling Body)

## Status
Accepted

## Context
The tracked chassis (Node 6) pitches forward and backward when climbing or descending
slopes, driving over obstacles, or accelerating/braking. Without compensation, this
tilt propagates to the upper body (torso, head, arms), degrading the camera horizon,
speech/vision interaction, and cargo stability.

The requirement is to keep the **body level with respect to gravity** regardless of
track pitch: a rotary joint between the tracks and the body actuated by a NEMA17
stepper motor, sensed by an IMU mounted on the body, controlled by a local closed
loop.

Key constraints:

- No direct hardware control from Robot Core (ADR-005 HAL, ADR-006 SDK).
- Logical commands only over MQTT, never joint angles (ADR-006, ADR-015).
- Real-time control loop must live on an MCU, not on the Linux core.
- A NEMA17 is driven by a **stepper driver**, not by a servo driver (PCA9685) nor
  by an L298N H-bridge: the existing HAL has no stepper interface.

## Decision

### 1. New dedicated node: Node 7 — Balance Controller (ESP32-S3)

| Field | Value |
|-------|-------|
| Hardware | ESP32-S3 (dedicated board, WiFi, IMU on I2C) |
| Motion | 1x NEMA17 stepper + **A4988** STEP/DIR driver |
| Transmission | Belt/pulley reduction (e.g. 20T motor → 80T joint, ratio 1:4) |
| Sensing | 1x MPU6050 IMU mounted on the **body**, sample ≥ 200 Hz, Madgwick fusion |
| Loop | Local control loop @ ~100 Hz PID: body pitch (gravity reference) → joint angle |
| Commands | `level`, `tilt <deg>`, `stow`, `stop` (logical, from Robot SDK) |
| Topics | `openj5/v1/balance/{cmd,evt,telemetry,state}` |

This **extends ADR-002** from 6 to 7 nodes. ADR-002 remains valid for the original
six; its "Scalable: add nodes without changing existing ones" property is now
exercised. Existing Node 5 (Torso) keeps its decorative `torso_pitch` servo and
battery management; it is unaffected.

### 2. HAL extension: IStepperDriver

Per ADR-005 the interface set grows with the new actuator family:

```python
class IStepperDriver(ABC):
    def initialize(self) -> None: ...
    def enable(self) -> None: ...                     # energize coils (hold)
    def disable(self) -> None: ...                    # release coils (free shaft)
    def set_position_steps(self, steps: int) -> None: # absolute, ACCEL-limited
    def set_velocity_steps_s(self, steps_s: float) -> None: ...
    def get_position_steps(self) -> int: ...
    def get_velocity_steps_s(self) -> float: ...
    def home(self) -> None: ...
    def brake(self) -> None: ...                      # stop and hold
    def shutdown(self) -> None: ...
```

Python-side in `src/hardware/hal/` (bench/sim + interface contract), C++-side in
`firmware/common/include/hal/` for the real node. Selection is configuration-driven
(`config/common/hal.json` → `stepper_driver`).

### 3. Control architecture

- **IMU on the body** measures absolute body pitch (gravity reference).
- PID runs **on Node 7** (soft-hard real-time, ~100 Hz): `error = target_pitch - body_pitch`.
- NEMA17 rotates the body relative to the track chassis until `body_pitch ≈ target`.
- Robot Core only issues logical commands; the ESP32 translates them to stepper
  trajectories (acceleration-limited, no missed steps).
- Fail-safe: IMU fault or excessive pitch beyond physical limit → hold current,
  publish `BalanceStateChanged(error)`; on losing leveling reference → brake + home.

## Alternatives Considered

1. **Integrate into Node 5 (Torso, ESP32)** — Rejected: Node 5 is a single-core
   ESP32 and already handles servos, LEDs, fan, and battery telemetry; sharing a
   real-time stepper/PID loop there risks timing. The requirement also called for an
   ESP32-S3. Keeps core blade simple and independently updatable/OTA.
2. **Balance control on Robot Core (RPi)** — Rejected: Linux is not real-time
   enough for a distributed servo/stepper loop; violates ADR-014 (firmware C++).
3. **TMC2209 instead of A4988** — Viable future upgrade (silent, stall detection);
   the driver HAL (`IStepperDriver`) makes it a config/board swap with zero app code
   changes. Owner chose A4988 for the first bring-up.
4. **Direct-drive stepper** — Rejected: body mass requires more torque than a NEMA17
   provides directly; a belt/pulley reduction (1:4) increases torque and resolution.
5. **Use a servo or DC motor for the joint** — Rejected: servo range/precision and
   DC-with-encoder hold torque/power are unsuitable for a continuously-adjusted
   gravity level joint; stepper gives open-loop absolute position and strong hold.

## Consequences

**Positive:**
- Level body on slopes → stable camera/speech/vision and safer navigation.
- New node is isolated: balance failure does not affect core, arms, or tracks.
- IStepperDriver unblocks future stepper applications on other nodes.
- Local loop works independently of network latency (MQTT only for commands/telemetry).
- Digital Twin can implement the same interface (Gazebo joint) → parity tests.

**Negative:**
- 7 firmware images to build/OTA (one more node in orchestrator/health/heartbeat).
- Belt backlash must be calibrated; stepper open-loop position drifts on missed
  steps (no encoder): mitigated by IMU feedback (the body pitch closes the loop).
- Power budget: NEMA17 + A4988 draws ~1-2 A at 12 V; must be added to Node 5 BMS/inrush.
- Mechanical complexity: pivot bearing, belt tensioning, mass balance near pivot.

## Implementation Notes

- Python (bench/sim): `src/hardware/hal/stepper.py` (IStepperDriver),
  `src/hardware/drivers/a4988.py` (A4988 STEP/DIR over RPi GPIO, bench prototype),
  `src/hardware/drivers/mock_stepper.py` (in-process mock for tests/digital twin).
- Domain: `StepperConfig`, `BalanceConfig` value objects, `Stepper` entity,
  `BodyCommand`/`GetBodyTiltQuery`/`GetBalanceStateQuery`, `BodyCommandEvent`,
  `BodyTelemetryEvent`, `BalanceStateChangedEvent`; `NodeType.BALANCE`.
- Config: `config/node7_balance/node.json` (stepper + IMU + PID + motion primitives +
  safety, zero magic numbers per ADR-008), `config/bench/balance.json`,
  `config/common/hal.json` (stepper_driver), `config/common/topics.json` (node7).
- SDK: `robot.body.level() / tilt(deg) / stow() / stop() / get_tilt() / get_state()`.
- Robot Core orchestrator: `node7` added to tracked node types (STATEMACHINE).
- Firmware (next release): new ESP-IDF project `firmware/node7_balance` using
  `firmware/common` (hal/stepper_driver, imu, comms, statemachine, ota).
- CAD (next release): pivot joint + belt pulley mount, NEMA17 bracket (ADR-012).
- Test: unit + digital-twin parity (same SDK controls mock/Gazebo body).

## Related ADRs
- ADR-002: 6-Node Distributed Architecture (**extended to 7 nodes by this ADR**)
- ADR-005: Hardware Abstraction Layer (new IStepperDriver interface)
- ADR-006: Robot SDK Facade (robot.body.*)
- ADR-008: Configuration-Driven Development (driver/config JSON)
- ADR-009: State Machine per Node (Node 7 implements the standard states)
- ADR-014: Python Core + C++ Firmware
- ADR-015: MQTT as Primary Transport (balance topics)