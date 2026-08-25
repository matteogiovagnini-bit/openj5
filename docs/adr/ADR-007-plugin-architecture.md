# ADR-007: Plugin Architecture for All Features

## Status
Accepted

## Context
OpenJ5's core promise: the platform outlives every AI model, sensor and protocol. Vision models change yearly (YOLOv10→v11), STT/TTS engines evolve (Vosk→Whisper→…), navigation stacks differ per user. Baking any of these into the core would force rewrites and block community extension.

## Decision
Everything above core infrastructure is a **plugin** implementing versioned interfaces:

| Category | Core plugins | External examples |
|----------|-------------|-------------------|
| Vision | `CameraPlugin` | `YoloDetectionPlugin`, `FaceRecognitionPlugin` |
| Speech | `AudioInput/OutputPlugin` | `WhisperSttPlugin`, `PiperTtsPlugin`, `WakeWordPlugin` |
| AI | `InferenceEnginePlugin` | `LlmPlugin`, `BehaviorTreePlugin` |
| Navigation | `OdometryPlugin` | `SlamToolboxPlugin`, `Nav2Plugin` |
| Motion | `MotionPrimitivesPlugin` | `MoveIt2Plugin`, `IkSolverPlugin` |
| Hardware | `ServoDriverPlugin` | `DynamixelDriverPlugin` |
| Communication | `MqttGatewayPlugin` | `Ros2GatewayPlugin`, `ZenohGatewayPlugin` |

Framework components:
- `IPlugin` lifecycle: initialize(config) → start() → stop() → healthCheck().
- `PluginManager`: discovery, load/unload, dependency resolution, enable/disable, hot reload.
- `PluginRegistry`: metadata catalog with artifact storage and signature verification.
- `PluginSandbox`: permission checking before privileged operations.
- Enable/disable/implementation selection entirely via `config/plugins.json`.

Core rule: **Core = infrastructure only. AI = plugin.**

## Alternatives Considered
1. **Monolithic feature modules compiled in** - Rejected: every user carries all features; swapping a model means forking.
2. **Microservices per feature** - Rejected: operationally heavy on a single RPi4; IPC overhead.
3. **ROS 2 component/nodelet model as plugin system** - Rejected: ties platform to ROS (violates NON_GOALS §2).

## Consequences
**Positive:**
- New model/sensor/protocol = new plugin; zero touch to core.
- Community marketplace possible (registry + signatures).
- Features can be disabled to save RAM on constrained deployments.

**Negative:**
- Interface stability becomes critical (versioned contracts required).
- Dynamic loading adds failure modes (missing deps, bad metadata) requiring careful lifecycle management.

## Implementation Notes
- Implemented in `src/plugins/interfaces.py` (14 interface types) and `src/plugins/manager.py`; server-side lifecycle in `robot_core/plugins.py`.
- Open items tracked in code TODOs: cryptographic signature verification and permission-enforcing proxy are stubs - must be completed before marketplace exposure.

## Related ADRs
- ADR-006: Robot SDK (plugins consume SDK/command bus)
- ADR-008: Configuration-Driven Development (plugin enablement via config)
- ADR-011: OTA (plugin artifacts distributed like firmware, signed)
