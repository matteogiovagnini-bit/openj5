# ADR-018: Motor HAL Port (IMotorDriver) - Contract Shape, Placement and Python↔C++ Parity

## Status
Accepted

## Context
ADR-005 already established a Hardware Abstraction Layer for every actuator and
explicitly named `IMotorDriver` in its core interface set (ADR-005). The tracked
chassis (Node 6, ADR-002) drives two DC gear motors through an L298N dual
H-bridge, and the concrete `L298NDriver` adapter plus the HAL class diagram were
already documented in `docs/architecture/ARCHITECTURE.md`.

What was still missing was the **port itself**: a pure, importable Python
interface that the adapters implement and that the application/SDK code can
depend on. Until T-025 Fase 1 the motor contract existed only as prose in
`ARCHITECTURE.md` and as an implicit shape inside `L298NDriver`; there was no
shared module, no mock, and no unit-testable contract. This mirrors the situation
that ADR-017 resolved for steppers: a HAL port is materialized in
`src/hardware/hal/` (with a C++ counterpart under `firmware/common/include/hal/`),
so applications depend on an abstraction instead of a concrete chip driver.

This ADR is deliberately **non-decisional**: it *records* a decision already
taken by ADR-005 (the port exists) and by ADR-017 (where and how a motor-family
port is materialized). It is a Level A documentation/architecture note, not a new
architectural choice.

Key constraints already in force:

- No application code may touch L298N/GPIO directly (ADR-005, ADR-006).
- All runtime values come from configuration, zero magic numbers (ADR-008).
- Python (Robot Core) and C++ (firmware) share the same HAL contract, with a
  contract-drift risk to mitigate (ADR-014).
- Digital Twin adapters implement the same interface (ADR-010).

## Decision

### 1. Port placement

The DC motor port lives in **`src/hardware/hal/motor.py`** (pure Python: no GPIO,
no I/O, importable on any machine), consistent with the existing
`src/hardware/hal/stepper.py` (ADR-017). It is re-exported from
`src/hardware/hal/__init__.py`.

> **Reconciliation note.** ADR-005 Implementation Notes say Python interfaces are
> defined in `src/core`; the code has always placed them in `src/hardware/hal/`
> (`stepper.py` since ADR-017, now `motor.py`). ADR-005 is immutable and is **not**
> modified by this ADR: this note records the actual, agreed location for new HAL
> ports. Future ports follow `src/hardware/hal/`.

### 2. Contract shape (as implemented)

```python
class IMotorDriver(ABC):
    @property
    def motor_names(self) -> list[str]: ...
    def initialize(self) -> None: ...
    def set_velocity(self, motor_id: str, velocity: float) -> None: ...  # clamped, signed, [-1, +1]
    def get_velocity(self, motor_id: str) -> float: ...
    def stop_all(self) -> None: ...    # coast: both direction pins low, PWM 0
    def brake_all(self) -> None: ...   # brake: both direction pins high, PWM 0
    def shutdown(self) -> None: ...    # release everything, safe to call twice
```

- Velocity is **normalized and signed** in `[-1.0, +1.0]` (magnitude = PWM duty,
  sign = direction), analogous to how `IStepperDriver` exposes steps/s.
- Out-of-range velocities are **clamped** to the configured limits, not silently
  executed arbitrarily.
- `brake_all()` must be distinguishable from `stop_all()` (hold vs. coast).
- `shutdown()` is idempotent ("safe to call twice").
- Values that the firmware contract exposes as `Result` (enable/disable, PID,
  odometry per the `ARCHITECTURE.md` sketch) are **out of scope** for this port:
  velocity control here is open-loop; encoders/PID/odometry belong to a future
  `IMotorEncoder`/controller port and the Node 6 firmware.

### 3. Pure helpers (shared, unit-testable)

The value mapping is factored into pure functions in the same module, so the real
and simulated adapters share one implementation (zero duplication):

- `clamp_velocity(velocity, min_velocity, max_velocity)` - clamps; raises
  `ValueError` on inverted bounds (config error, never guessed).
- `motor_levels(velocity) -> MotorLevels(forward, reverse, duty)` - maps a signed
  velocity to the two direction GPIO levels and the PWM duty.
- `ramp_schedule(current, target, step) -> list[float]` - intermediate ramp
  values landing exactly on the target; raises `ValueError` on `step <= 0`.

These are the intended Python mirror of a future C++ `motor_logic.hpp`
(cf. `stepper_logic.hpp`).

### 4. Adapters

| Adapter | File | Backend | Role |
|---------|------|---------|------|
| `L298NDriver` | `src/hardware/drivers/l298n.py` | Raspberry Pi GPIO (gpiozero/lgpio, imported lazily) | Real bench Node 6; `channel_factory` injectable for tests |
| `MockMotorDriver` | `src/hardware/drivers/mock_motor.py` | In-process, no GPIO, no sleeps | CI/tests and the `--mock` bench demo |

Both read `config/bench/tracks.json` (`pwm_frequency_hz`, `ramp_step`,
`ramp_seconds`, `limits`, `demo`) and implement the same port, so application code
is backend-agnostic (ADR-010).

## Alternatives Considered
1. **Leave the contract implicit in `L298NDriver`** - Rejected: no shared port to
   depend on, no mock, no unit-testable contract; a second motor driver would
   duplicate the shape. ADR-005 already required the interface.
2. **Place the port in `src/core`** (literal reading of ADR-005:43) - Rejected:
   `src/core` is the domain core and must not depend on/own hardware ports; the
   established location for HAL ports is `src/hardware/hal/` (ADR-017 precedent).
3. **Expose raw PWM duty instead of normalized signed velocity** - Rejected:
   normalized velocity keeps application code driver-agnostic (a TB6612/BTS7960
   adapter has different duty semantics) and matches the `ARCHITECTURE.md` intent
   (`robot.tracks.move_forward(speed=0.5)`).
4. **Include PID/enable/disable/odometry in this port now** - Rejected (YAGNI):
   unused on the bench, breaching interface segregation; deferred to the Node 6
   firmware and a dedicated encoder/controller port.
5. **Introduce a new actuator family / new ADR** - Not applicable: `IMotorDriver`
   is not new; it is already named by ADR-005. This ADR only records its
   materialization.

## Consequences
**Positive:**
- Applications/SDK and tests depend on `IMotorDriver`, not on L298N/gpiozero.
- The mock and the real driver share one ramp/level implementation → no drift and
  CI can validate motor logic without hardware.
- A future TB6612/BTS7960/ODrive/Gazebo adapter is a new class + a config line,
  zero application changes (ADR-005).
- The pure helpers give a clear Python↔C++ parity target.

**Negative:**
- The HAL class diagram in `docs/architecture/ARCHITECTURE.md` (HAL section) is
  now **stale** and must be regenerated to match the implemented shape
  (`motor_names`, `stop_all`, `brake_all`, `MockMotorDriver`).
- ADR-005:43 (`src/core`) and the actual location (`src/hardware/hal/`) remain
  textually inconsistent; ADR-005 is immutable, so the reconciliation lives in
  this ADR's note (see Decision §1).
- The Python port currently **has no C++ counterpart** (`firmware/common/include/hal/`
  ships only `stepper_driver.hpp` / `stepper_logic.hpp`): the `motor.py` docstring
  must not claim otherwise until the header exists.

## Implementation Notes
- Delivered (T-025 Fase 1): `src/hardware/hal/motor.py`, export in
  `src/hardware/hal/__init__.py`, real `L298NDriver` (lazy gpiozero,
  config-driven, injectable `channel_factory`, idempotent `shutdown()`) and
  `MockMotorDriver`, `config/bench/tracks.json` (`pwm_frequency_hz`, `ramp_step`,
  `demo`), `scripts/demo/tracks_bench.py` (`--mock`, `--selftest`), and unit tests
  `tests/unit/test_motor_hal.py`, `test_l298n_driver.py`, `test_mock_motor.py`,
  `test_tracks_demo.py`.
- Documentation follow-ups (continuous documentation, CODING_STANDARD §8):
  regenerate the HAL class diagram in `docs/architecture/ARCHITECTURE.md`; add
  `IMotorDriver` to `docs/api/API.md`; update `CHANGELOG.md`, `PROJECT_STATUS.md`,
  `docs/NEXT_TASK.md`, `docs/hardware/BENCH_TRACKS.md`, `docs/PROJECT_MEMORY.md`.
- Firmware follow-up **to be tracked as a task**: port `motor_driver.hpp` +
  `motor_logic.hpp` (mirroring `motor_levels`/`ramp_schedule`/`clamp_velocity`)
  when the Node 6 ESP-IDF firmware starts, plus a Python↔C++ parity test - the
  same approach used for Node 7 in T-026/T-029. Until then, correct the
  `motor.py` docstring so it does not assert a C++ contract that does not exist.
- Config: the mock is registered in `config/common/hal.json` →
  `motor_driver.implementations` (`"mock": "MockMotorDriver"`), matching the
  `stepper_driver` entry, so real↔sim selection is config-driven (ADR-010).
- Supersedes nothing; ADR-005 stays Accepted and unmodified.

## Related ADRs
- ADR-002: 6-Node Distributed Architecture (Node 6 tracks, 2x DC motor)
- ADR-005: Hardware Abstraction Layer (names `IMotorDriver`; this ADR records its materialization)
- ADR-006: Robot SDK Facade (applications use `robot.tracks.*`, never the driver)
- ADR-008: Configuration-Driven Development (pins/frequency/ramp from JSON)
- ADR-010: Digital Twin Native (mock implements the same port)
- ADR-014: Python Core + C++ Firmware (Python↔C++ parity target)
- ADR-017: Node 7 Balance Controller (precedent: HAL port in `src/hardware/hal/` + C++ counterpart)
