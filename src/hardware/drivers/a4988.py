"""
OpenJ5 A4988 Stepper Driver - bench prototype for Node 7 (Balance Controller).

Drives a NEMA17 stepper via an A4988 (or driver-register compatible) STEP/DIR
board from Raspberry Pi GPIO. This is the bench/sim bring-up of the actuator
family introduced by ADR-017; the production driver is the ESP-IDF C++
implementation in firmware/common.

A4988 wiring (config-driven, config/bench/balance.json):
    - STEP      -> GPIO (pulse = one microstep, dir decided by DIR)
    - DIR       -> GPIO (LEVEL selects direction)
    - ENABLE    -> GPIO active LOW (HIGH releases the coils, LOW holds)
    - VMOT      -> external 12 V supply (never from the Pi), GND common

Position is tracked by integrating the commanded velocity (open loop, PWM pulse
train): precise per-step counting belongs to the ESP32 firmware that generates
the pulses itself. On the bench this is an estimate sufficient for bring-up of
the loop; the body-pitch IMU closes the loop in the real control algorithm.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from gpiozero import DigitalOutputDevice, PWMOutputDevice, Device
from gpiozero.pins.lgpio import LGPIOFactory

from ..hal.stepper import IStepperDriver, trapezoid_velocity

Device.pin_factory = LGPIOFactory()


class A4988Axis:
    """One stepper axis on an A4988: STEP pulse train + DIR + ENABLE."""

    def __init__(self, name: str, step_gpio: int, dir_gpio: int, enable_gpio: int):
        self.name = name
        self._step = PWMOutputDevice(step_gpio, frequency=1, initial_value=0.0)
        self._dir = DigitalOutputDevice(dir_gpio, initial_value=False)
        self._enable = DigitalOutputDevice(enable_gpio, initial_value=True)  # HIGH = off
        self._velocity_steps_s = 0.0
        self._enabled = False

    def set_velocity(self, steps_s: float) -> None:
        """Set signed velocity in steps/s. 0 -> stop but keep holding."""
        steps_s = float(steps_s)
        if steps_s != 0.0:
            self._dir.value = steps_s > 0.0
            self._step.frequency = abs(steps_s)
            self._step.value = 0.5
        else:
            self._step.value = 0.0
        self._velocity_steps_s = steps_s

    def enable(self) -> None:
        self._enable.value = False  # A4988 ENABLE is active low
        self._enabled = True

    def disable(self) -> None:
        self._step.value = 0.0
        self._enable.value = True
        self._enabled = False
        self._velocity_steps_s = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def velocity_steps_s(self) -> float:
        return self._velocity_steps_s

    def close(self) -> None:
        self.disable()
        self._step.close()
        self._dir.close()
        self._enable.close()


class A4988StepperDriver(IStepperDriver):
    """Single-axis A4988 driver configured from JSON (zero magic numbers).

    Implements the IStepperDriver HAL port for the bench (ADR-005/ADR-017).
    """

    def __init__(self, config_path: str | Path):
        cfg = json.loads(Path(config_path).read_text())
        if cfg.get("driver") != "a4988":
            raise ValueError(f"expected a4988 config, got: {cfg.get('driver')}")
        limits = cfg["limits"]
        self.max_speed_steps_s = float(limits["max_velocity_steps_s"])
        self.max_accel_steps_s2 = float(limits["max_acceleration_steps_s2"])
        pins = cfg["stepper"]["pins"]
        self._axis = A4988Axis(
            name="balance_joint",
            step_gpio=int(pins["step_gpio"]),
            dir_gpio=int(pins["dir_gpio"]),
            enable_gpio=int(pins["enable_gpio"]),
        )
        self._position_steps = 0.0
        self._control_dt = float(cfg.get("control_dt_s", 0.02))

    def initialize(self) -> None:
        self._position_steps = 0.0
        self._axis.enable()

    def enable(self) -> None:
        self._axis.enable()

    def disable(self) -> None:
        self._axis.disable()

    def set_position_steps(self, steps: int) -> None:
        """Trapezoidal move to absolute position (foreground ramp, bench-paced)."""
        target = int(steps)
        if not self._axis.enabled:
            self._axis.enable()
        while abs(target - self._position_steps) > 0:
            remaining = target - self._position_steps
            v = trapezoid_velocity(
                remaining, self.max_speed_steps_s, self.max_accel_steps_s2, self._control_dt
            )
            self._axis.set_velocity(v)
            self._position_steps += v * self._control_dt
            time.sleep(self._control_dt)
        self._axis.set_velocity(0.0)
        self._position_steps = float(target)

    def set_velocity_steps_s(self, steps_s: float) -> None:
        steps_s = max(-self.max_speed_steps_s, min(self.max_speed_steps_s, steps_s))
        if not self._axis.enabled and steps_s != 0.0:
            self._axis.enable()
        self._axis.set_velocity(steps_s)

    def get_position_steps(self) -> int:
        return int(round(self._position_steps))

    def get_velocity_steps_s(self) -> float:
        return self._axis.velocity_steps_s

    def home(self) -> None:
        self.set_position_steps(0)

    def brake(self) -> None:
        self._axis.set_velocity(0.0)
        self._axis.enable()  # hold torque

    def shutdown(self) -> None:
        self._axis.disable()


def load_driver(config_path: str | Path | None = None) -> A4988StepperDriver:
    default = Path(__file__).resolve().parents[2] / "config" / "bench" / "balance.json"
    driver = A4988StepperDriver(config_path or default)
    driver.initialize()
    return driver


if __name__ == "__main__":
    d = load_driver()
    print("pos:", d.get_position_steps())
    d.set_position_steps(800)   # e.g. +45 deg at 16x/200S/4:1
    print("pos:", d.get_position_steps())
    d.shutdown()