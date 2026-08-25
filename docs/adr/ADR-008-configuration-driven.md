# ADR-008: Configuration-Driven Development (JSON/YAML Only)

## Status
Accepted

## Context
A parametric, 10-year platform cannot contain magic numbers. Servo limits, PID gains, topic names, network addresses, GPIO pins, safety thresholds and hardware selections must be tunable per robot instance, per node, at runtime where possible - without code changes or rebuilds.

## Decision
All runtime values come from external configuration. Sources with priority merge:

```
ENV (secrets/overrides) > Database > YAML > JSON files
```

Rules:
1. Zero hardcoded values: `speed = config.get("servo.neck_yaw.speed")`, never `speed = 120`.
2. Every config file validated against JSON Schema (Pydantic models at the boundary).
3. ConfigService supports dot-notation get/set, file watching, hot reload and change notifications.
4. Per-node directories (`config/nodeX_*/node.json`) plus shared `config/common/` (hal.json, topics.json, safety.json, communication.json).
5. Constants allowed in code only for mathematics (π, 180, 360) and structural literals (0, 1).

Verification target: `grep -r "= [0-9]" src/` returns only mathematical constants.

## Alternatives Considered
1. **Compile-time constants / #defines** - Rejected: requires reflashing to retune; kills parametric goal.
2. **Environment variables only** - Rejected: unsuitable for structured, nested hardware config.
3. **Database-only configuration** - Rejected: chicken-and-egg on first boot; files needed as bootstrap.

## Consequences
**Positive:**
- One codebase serves every robot variant (head/arm/torso/tracks nodes differ only by config).
- Calibration and tuning without recompilation; hot reload shortens iteration loops.
- Config files double as documentation of each robot's actual setup.

**Negative:**
- Schema drift risk between code expectations and config files → mitigated by validation at startup and CI checks.
- More moving parts at boot (source merging, priority rules).

## Implementation Notes
- Python: `src/config/service.py` (multi-source, watch, validate) reused by `robot_core/config.py` in the Docker deployment.
- Firmware: JSON parsed at boot into typed structs; NVS stores overrides.
- TODO tracked: persist runtime set() changes back to file/database.

## Related ADRs
- ADR-005: HAL (driver selection is config)
- ADR-007: Plugin Architecture (plugin enable/implementations are config)
- ADR-009: State Machine (INIT validates config before READY)
