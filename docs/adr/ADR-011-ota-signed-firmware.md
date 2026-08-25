# ADR-011: OTA with Signed Firmware and Rollback

## Status
Accepted

## Context
Five ESP32 nodes are distributed on the robot (head, arms, torso, tracks), partially disassembled during maintenance. Physical reflashing via USB for every update is impractical and does not scale to a fleet. At the same time, a failed or malicious firmware update must never brick a node or compromise safety.

## Decision
Every ESP32 supports **Over-The-Air updates** with security and rollback as non-negotiable properties:

1. **Signed images**: firmware binaries signed with ECDSA P-256; signature verified **on device before flashing**.
2. **Rollback**: if the new image fails to boot 3 consecutive times, bootloader automatically reverts to the previous known-good slot.
3. **Staged rollout**: canary (single node) → fleet, orchestrated by the Robot Core OTA Manager.
4. **Delta updates** planned for bandwidth-constrained links.
5. Transport over mTLS (ADR-013); progress reporting via `openj5/vX/<node>/ota` topics.

Server side: Robot Core OTA Manager handles firmware registration, versioning, deployment campaigns, status aggregation; REST API endpoints `/ota/*`; signing keys stored in `docker/secrets/`.

```bash
openj5 ota deploy --node node2_head --firmware builds/node2_head_v1.2.3.bin --sign-key keys/ota_private.pem
```

## Alternatives Considered
1. **USB-only updates** - Rejected: operationally unacceptable for an assembled robot/fleet.
2. **Unsigned OTA with hash-only check** - Rejected: integrity ≠ authenticity; attacker-controlled LAN could flash malicious firmware.
3. **Third-party OTA services** - Rejected: cloud dependency violates local-first constraint.

## Consequences
**Positive:**
- Field updates without disassembly; fleet-wide consistency achievable.
- Bricked-node risk minimized by A/B slots + boot-count rollback.
- Audit trail of which node runs which firmware version.

**Negative:**
- Flash layout complexity (two app slots + metadata) reduces usable app space on 4MB parts.
- Key management becomes critical: losing the signing key means losing fleet updatability.

## Implementation Notes
- Server implemented in `robot_core/ota.py` (registration, ECDSA signing, staged rollout, rollback orchestration).
- ESP32 client (HTTPS download + signature verify + fallback) is **partially implemented** - tracked in ROADMAP v0.4.0.
- Signing keys generated per-installation by `docker/secrets/generate.sh`; certificates under `docker/certs/` (see git history 2026-08-13).

## Related ADRs
- ADR-013: Security (mTLS transport, key management)
- ADR-009: State Machine (node enters special OTA handling within RUNNING/READY)
- ADR-007: Plugin Architecture (plugin artifacts follow same signing pipeline)
