# ADR-014: Python for Robot Core, C++ for Firmware

## Status
Accepted

## Context
Node 1 hosts AI (vision models, speech, LLM plugins), orchestration, APIs and tooling - an ecosystem where Python's libraries dominate and iteration speed matters. The five ESP32 nodes need deterministic timing, direct peripheral access and tiny footprints - territory where Python does not exist and C/C++ dominates. A single language across both worlds is not realistic without unacceptable compromises.

## Decision
Two-language split with a strict boundary:

| World | Language | Runtime | Scope |
|-------|----------|---------|-------|
| Robot Core (Node 1) | **Python 3.11+** | Ubuntu/Docker, async-first | Domain, application, SDK, gateways, event bus, plugins, OTA server, APIs |
| Firmware (Nodes 2–6) | **C++20** | ESP-IDF 5.2 + FreeRTOS | HAL interfaces/drivers, MQTT client, state machine, motion primitives, OTA client |

Boundary contract = MQTT topics (ADR-015) carrying logical commands/events; both sides share the same topic schema and state machine semantics. SDK facades exist in both languages (Python full, C++ subset) so applications can be written against either.

## Alternatives Considered
1. **MicroPython on ESP32 nodes** - Rejected: insufficient performance/memory for servo trajectory interpolation, TLS+MQTT, and OTA in parallel; ecosystem too thin.
2. **Rust everywhere** - Rejected for now: ESP-IDF integration mature but team velocity and library availability (AI ecosystem) favor Python core; revisit via new ADR if fleet-scale memory safety demands it.
3. **Raspberry Pi Pico C++ bridge for real-time servo control from Node 1** - Rejected: adds a seventh compute node and serial protocol complexity; ESP32-S3 handles local realtime adequately.

## Consequences
**Positive:**
- Each world uses its ecosystem's best tools (FastAPI/SQLAlchemy/structlog vs. ESP-IDF/FreeRTOS/mbedTLS).
- AI plugins integrate trivially (PyTorch/TFLite/llama.cpp bindings) without cross-language friction.
- Firmware stays small, deterministic and reviewable.

**Negative:**
- Two toolchains, two lint/test setups in CI (planned v0.3.0).
- Contract drift risk between Python event schemas and C++ parsers → mitigated by shared JSON Schema definitions in `config/common/topics.json`.

## Implementation Notes
- Python codebase: `src/` (platform) + `firmware/node1_robot_core/docker/src/robot_core/` (deployment package).
- Firmware skeleton: `firmware/common/` component + `firmware/node2_head/`; `-Wall -Wextra -Wpedantic -Werror` enforced.
- Shared vocabulary lives in config JSON, never duplicated as literals on either side.

## Related ADRs
- ADR-001: Hexagonal Architecture (languages live in separate layers/nodes)
- ADR-015: MQTT primary transport (the inter-language contract)
- ADR-002: Six-node architecture (hardware split justifies language split)
