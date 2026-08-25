# ADR-010: Digital Twin Native (Gazebo / Isaac Sim)

## Status
Accepted

## Context
Hardware is scarce and slow to iterate on; CI cannot own physical robots. AI researchers need reproducible experiments. Therefore simulation must be a first-class citizen, not an afterthought - the same software stack must drive both the physical robot and its simulated twin.

## Decision
Make the **Digital Twin native**: the Robot SDK + HAL + Event Bus used on real hardware are reused unchanged in simulation. The backend switch is one configuration line:

```json
{ "mode": "real" }   // HAL drivers talk to PCA9685/L298N over I2C/GPIO
{ "mode": "sim" }    // GazeboServoDriver, GazeboMotorDriver, GazeboCameraDriver...
```

Components:
- **Digital Twin Bridge** (`robot_core/digital_twin.py`): entity mapping robot↔sim, joint state sync, time sync; supports Gazebo (primary) and Isaac Sim (secondary).
- Simulator adapters implement the same HAL interfaces as hardware drivers (ADR-005).
- Simulation parity tests: the same test suite passes against real robot and Gazebo.
- Gazebo Harmonic runs headless inside Docker Compose for CI.

## Alternatives Considered
1. **Separate sim-only codebase** - Rejected: divergence guaranteed; parity tests impossible.
2. **Simulation via ROS only** - Rejected: couples core to ROS (ADR-003 keeps ROS optional).
3. **Webots/MuJoCo primary** - Deferred: supported later through the same HAL adapter pattern; Gazebo chosen for ROS ecosystem fit and headless CI support.

## Consequences
**Positive:**
- Full development and most testing without hardware; faster iteration loops.
- Deterministic, reproducible scenarios for debugging (replay events into twin).
- CI pipeline can validate behavior end-to-end on every PR.

**Negative:**
- Sim-to-real gap remains (physics fidelity, sensor noise): parity tests mitigate but do not eliminate.
- Extra infrastructure services (Gazebo container) increase resource footprint on RPi4 when enabled.

## Implementation Notes
- World file: `docker/config/gazebo/worlds/openj5.world` (headless, physics, lighting); official OCI gazebo image with arm64 support selected after portability issues (see git history 2026-08-13).
- URDF/XACRO originates from FreeCAD export (ADR-012), never hand-written.
- REST API exposes simulation control endpoints (/simulation/status|pause|resume|reset).

## Related ADRs
- ADR-005: HAL (simulator implements same driver interfaces)
- ADR-006: Robot SDK (same facade for real and sim)
- ADR-012: FreeCAD parametric CAD (single source of truth for model geometry)
