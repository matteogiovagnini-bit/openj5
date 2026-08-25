# ADR-006: Robot SDK as Single Facade for Applications

## Status
Accepted

## Context
Applications (user behaviors, AI plugins, teleop, tests) need robot capabilities: move head, wave arm, drive tracks, speak. Without a single facade, every consumer would need knowledge of topics, servo limits, kinematics and transport - violating the platform's core promise that "the Raspberry never sends servo angles, only logical commands".

## Decision
Provide a **Robot SDK facade** as the only public entry point for controlling the robot:

```python
robot = Robot.from_config("config/robot.json")
robot.head.look_at(x=0.5, y=0.0, z=1.2)
robot.right_arm.wave()
robot.tracks.move_forward(speed=0.5)
robot.speech.say("Hello")
robot.behavior.idle()
```

Design rules:
- Subsystems lazily loaded: `HeadAPI`, `ArmAPI`, `TracksAPI`, `SpeechAPI`, `BehaviorAPI`, `VisionAPI`, `BatteryAPI`, `SystemAPI`.
- High-level semantic operations only (lookAt, nod, wave, grab, reach); no MQTT topics, no servo angles in application code.
- `RobotConfig.mode` selects real/sim/mock backend; identical API on all three.
- Async-first internally; synchronous wrappers provided for scripts.
- A C++ SDK mirrors the API for firmware-side consumers.

## Alternatives Considered
1. **Expose raw gateway/topic API to applications** - Rejected: couples apps to transport and schema.
2. **ROS 2 actions/topics as public API** - Rejected: ROS is an optional transport (ADR-003), not the architecture.
3. **Multiple small facades per use case** - Rejected: fragments learning and allows inconsistent patterns.

## Consequences
**Positive:**
- Application code stays valid across transport changes (MQTT→Zenoh→gRPC) and real/sim switches.
- Single surface to document (`docs/api/API.md`), test, and version.
- Natural enforcement point for safety policies and rate limiting.

**Negative:**
- Facade must track all subsystem capabilities; risk of becoming a god-object if not decomposed into sub-APIs.
- New hardware capability requires SDK update before it is usable by applications.

## Implementation Notes
- Implemented in `src/sdk/robot.py`; commands flow through CommandBus (CQRS) to handlers.
- Semantic operations map to motion primitives executed on ESP32 nodes (logical command → trajectories).
- Public API stability governed by SemVer from v1.0 (see NON_GOALS §6).

## Related ADRs
- ADR-001: Hexagonal Architecture (SDK sits above application layer)
- ADR-003: Communication Gateway (SDK uses gateway, never exposes it)
- ADR-004: Event-Driven Architecture (SDK emits commands as events)
- ADR-010: Digital Twin Native (same facade drives simulator)
