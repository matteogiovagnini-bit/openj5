# ADR-005: Hardware Abstraction Layer (HAL) for All Drivers

## Status
Accepted

## Context
OpenJ5 must survive hardware evolution over 10+ years: PCA9685 may be replaced by soft-PWM/LEDC, L298N by TB6612/BTS7960/ODrive, VL53L0X by other ToF sensors, MPU6050 by ICM20948, and real hardware by simulator drivers (Gazebo). Application code written directly against chips would make any substitution a rewrite.

## Decision
All hardware access goes through pure interfaces (HAL), both in Python (Robot Core / simulation adapters) and C++ (ESP-IDF firmware):

```python
class IServoDriver(ABC):
    @abstractmethod
    def set_position(self, channel: int, angle: float, speed: float) -> Result: ...
    @abstractmethod
    def home(self, channel: int) -> Result: ...
    # enable, disable, calibrate, shutdown ...
```

Core interface set:
`IServoDriver`, `IMotorDriver`, `IDistanceSensor`, `IIMU`, `ICameraDriver`, `IAudioInput`, `IDisplay`, `ILedStrip`.

Concrete drivers (`PCA9685Driver`, `L298NDriver`, `VL53L0XDriver`, `MPU6050Driver`, `GazeboServoDriver`, ...) implement these interfaces and live exclusively in the Infrastructure layer.

## Alternatives Considered
1. **Direct register/I2C access in application code** - Rejected: maximum coupling, untestable without hardware.
2. **ROS 2 hardware_interface as the abstraction** - Rejected: ties core to ROS ecosystem, violates ADR-003.
3. **Per-node bespoke code** - Rejected: duplicates logic across 6 nodes.

## Consequences
**Positive:**
- Chip swap = new driver class, zero application changes.
- Simulator implements same interfaces → Digital Twin parity (ADR-010).
- Unit testing with mock/fake drivers, no hardware needed.
- Clear ownership boundary for embedded vs. software teams.

**Negative:**
- One indirection layer; risk of interface bloat if not kept minimal.
- Driver-specific features need extension points (capabilities pattern).

## Implementation Notes
- Interfaces defined once per language: `src/core` (Python) and `firmware/common/include/hal/` (C++).
- Driver selection is configuration-driven (`config/common/hal.json`), resolved at composition root.
- No driver may leak chip-specific types into domain code.

## Related ADRs
- ADR-001: Hexagonal Architecture (drivers are Infrastructure adapters)
- ADR-008: Configuration-Driven Development (driver selection via config)
- ADR-010: Digital Twin Native (Gazebo drivers implement same HAL)
