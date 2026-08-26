"""
OpenJ5 L298N Motor Driver - first real IMotorDriver implementation (bench bring-up).

Drives two DC motors via an L298N dual H-bridge from Raspberry Pi GPIO.
Velocity is normalized (-1.0 .. +1.0) and mapped to PWM duty on the ENA/ENB pins;
direction via IN1..IN4 pairs.

This is the bench prototype of Nodo 6 (tracks). It implements the Python-side
shape documented in docs/architecture/ARCHITECTURE.md (IMotorDriver):
    initialize(), set_velocity(), stop(), brake(), shutdown()
The same interface will be implemented by the ESP-IDF C++ driver for the real node.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gpiozero import DigitalOutputDevice, PWMOutputDevice, Device
from gpiozero.pins.lgpio import LGPIOFactory

Device.pin_factory = LGPIOFactory()


class L298NMotor:
    """Single motor channel: one PWM enable + two direction GPIOs."""

    def __init__(self, name: str, enable_gpio: int, in_a_gpio: int, in_b_gpio: int):
        self.name = name
        self._enable = PWMOutputDevice(enable_gpio, initial_value=0.0)
        self._in_a = DigitalOutputDevice(in_a_gpio, initial_value=False)
        self._in_b = DigitalOutputDevice(in_b_gpio, initial_value=False)
        self._velocity = 0.0

    def set_velocity(self, velocity: float) -> None:
        velocity = max(-1.0, min(1.0, velocity))
        if velocity > 0:
            self._in_a.on()
            self._in_b.off()
        elif velocity < 0:
            self._in_a.off()
            self._in_b.on()
        else:
            self._in_a.off()
            self._in_b.off()
        self._enable.value = abs(velocity)
        self._velocity = velocity

    def get_velocity(self) -> float:
        return self._velocity

    def brake(self) -> None:
        self._in_a.on()
        self._in_b.on()
        self._enable.value = 0.0
        self._velocity = 0.0

    def close(self) -> None:
        self.set_velocity(0.0)
        self._enable.close()
        self._in_a.close()
        self._in_b.close()


class L298NDriver:
    """Two-channel driver configured from JSON (zero magic numbers)."""

    def __init__(self, config_path: str | Path):
        cfg = json.loads(Path(config_path).read_text())
        if cfg.get("driver") != "l298n":
            raise ValueError(f"expected l298n config, got: {cfg.get('driver')}")
        limits = cfg["limits"]
        self.min_velocity = float(limits["min_velocity"])
        self.max_velocity = float(limits["max_velocity"])
        self.ramp_seconds = float(cfg.get("ramp_seconds", 0.05))
        self.motors: dict[str, L298NMotor] = {}
        self._config_path = Path(config_path)

    def initialize(self) -> None:
        cfg = json.loads(self._config_path.read_text())
        for name, pins in cfg["motors"].items():
            self.motors[name] = L298NMotor(
                name=name,
                enable_gpio=int(pins["enable_gpio"]),
                in_a_gpio=int(pins["in_a_gpio"]),
                in_b_gpio=int(pins["in_b_gpio"]),
            )

    @property
    def motor_names(self) -> list[str]:
        return list(self.motors)

    def set_velocity(self, motor_id: str, velocity: float) -> None:
        velocity = max(self.min_velocity, min(self.max_velocity, velocity))
        steps = max(1, int(abs(velocity - self.motors[motor_id].get_velocity()) / 0.1) or 1)
        current = self.motors[motor_id].get_velocity()
        for i in range(1, steps + 1):
            step_value = current + (velocity - current) * i / steps
            self.motors[motor_id].set_velocity(step_value)
            time.sleep(self.ramp_seconds / steps)

    def get_velocity(self, motor_id: str) -> float:
        return self.motors[motor_id].get_velocity()

    def stop_all(self) -> None:
        for motor in self.motors.values():
            motor.set_velocity(0.0)

    def brake_all(self) -> None:
        for motor in self.motors.values():
            motor.brake()

    def shutdown(self) -> None:
        self.stop_all()
        for motor in self.motors.values():
            motor.close()


def load_driver(config_path: str | Path | None = None) -> L298NDriver:
    default = Path(__file__).resolve().parents[2] / "config" / "bench" / "tracks.json"
    driver = L298NDriver(config_path or default)
    driver.initialize()
    return driver


if __name__ == "__main__":
    d = load_driver()
    print("motors:", d.motor_names)
    d.shutdown()
