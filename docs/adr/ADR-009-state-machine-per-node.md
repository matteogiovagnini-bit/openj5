# ADR-009: State Machine per Node (BOOT→INIT→READY→RUNNING→ERROR→RECOVERY→SHUTDOWN)

## Status
Accepted

## Context
Six distributed nodes with independent hardware must behave predictably at boot, under faults and during shutdown. Ad-hoc status flags lead to unreachable states, missed cleanup, and impossible fleet coordination. Safety requires that no node ever moves hardware outside a well-defined operating state.

## Decision
Every node (ESP32 firmware nodes and the Robot Core orchestrator) implements the same explicit state machine:

```
[*] → BOOT → INIT → READY → RUNNING ↔ READY
        │      │              │ │
        └──→ ERROR ←──────────┘ │  (fault, watchdog, comm loss)
                │→ RECOVERY → READY | ERROR | SHUTDOWN
READY/RUNNING → SHUTDOWN → [*]
```

Rules:
1. Hardware motion allowed only in `RUNNING`; entering ERROR forces fail-safe (servos → home, motors → brake).
2. INIT completes only when: config loaded+validated, communication established, calibration OK.
3. Health checks run periodically; watchdog breach or comm loss triggers ERROR.
4. RECOVERY attempts bounded re-initialization; repeated failure → SHUTDOWN.
5. Every transition is published as `NodeStateChanged` on the Event Bus (event sourcing = full audit trail).

The Robot Core hosts a **State Machine Orchestrator** coordinating all 6 nodes (fault propagation, fleet-level transitions like global STOP).

## Alternatives Considered
1. **Status flags / boolean ready bits** - Rejected: illegal state combinations, no transition audit.
2. **Behavior trees for lifecycle** - Rejected: BTs are for behaviors (plugin domain), not deterministic node lifecycle.
3. **Only-orchestrator state machine** - Rejected: ESP32 must remain safe even if network to core is lost.

## Consequences
**Positive:**
- Uniform semantics across heterogeneous nodes; trivially verifiable transitions.
- Deterministic safety envelope; graceful degradation paths are explicit.
- Fleet dashboards/automation consume a single event stream.

**Negative:**
- Every new operational mode requires extending the transition table deliberately.
- Recovery logic must be carefully bounded to avoid boot loops.

## Implementation Notes
- Python: `src/statemachine/state_machine.py` (`StateMachine`, `StateHandler` per-state enter/exit/update/event hooks, watchdog timer); orchestration in `robot_core/statemachine.py` (7 states × 6 nodes, fault propagation).
- Firmware: mirrored implementation in `firmware/common` component; identical transition table.

## Related ADRs
- ADR-004: Event-Driven Architecture (transitions published as events)
- ADR-013: Security/Fail-Safe (ERROR state enforces safe postures)
- ADR-002: Six-node architecture (orchestrator coordinates all nodes)
