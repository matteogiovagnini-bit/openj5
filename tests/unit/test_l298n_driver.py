"""Unit tests for the real L298N driver logic, without gpiozero (T-025 Fase 1).

``L298NDriver`` imports ``gpiozero`` lazily inside the default channel factory,
so the driver logic is exercised here with an injected ``channel_factory`` that
builds a fake channel recording every call. ``time.sleep`` is monkeypatched: the
tests assert the ramp values the driver commands, never wall-clock delays.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hardware.drivers import l298n
from hardware.drivers.l298n import L298NDriver
from hardware.hal.motor import IMotorDriver

ROOT = Path(__file__).resolve().parents[2]
TRACKS = ROOT / "config" / "bench" / "tracks.json"


def _tracks() -> dict:
    return json.loads(TRACKS.read_text(encoding="utf-8"))


class FakeChannel:
    """Records the driver commands; duck-types ``MotorChannel``."""

    def __init__(
        self,
        *,
        name: str,
        enable_gpio: int,
        in_a_gpio: int,
        in_b_gpio: int,
        pwm_frequency_hz: float,
    ) -> None:
        self.name = name
        self.enable_gpio = enable_gpio
        self.in_a_gpio = in_a_gpio
        self.in_b_gpio = in_b_gpio
        self.pwm_frequency_hz = pwm_frequency_hz
        self.velocity_calls: list[float] = []
        self.brake_calls = 0
        self.close_calls = 0
        self._velocity = 0.0

    def set_velocity(self, velocity: float) -> None:
        self.velocity_calls.append(velocity)
        self._velocity = velocity

    def get_velocity(self) -> float:
        return self._velocity

    def brake(self) -> None:
        self.brake_calls += 1
        self._velocity = 0.0

    def close(self) -> None:
        self.close_calls += 1


class FakeChannelFactory:
    def __init__(self) -> None:
        self.created: dict[str, FakeChannel] = {}

    def __call__(self, **kwargs) -> FakeChannel:
        channel = FakeChannel(**kwargs)
        self.created[channel.name] = channel
        return channel


class StrictChannel(FakeChannel):
    """Mirrors gpiozero: any command after ``close()`` raises ``DeviceClosed``."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.closed = False

    def set_velocity(self, velocity: float) -> None:
        if self.closed:
            raise RuntimeError("set_velocity() called after close()")
        super().set_velocity(velocity)

    def brake(self) -> None:
        if self.closed:
            raise RuntimeError("brake() called after close()")
        super().brake()

    def close(self) -> None:
        if self.closed:
            raise RuntimeError("close() called after close()")
        super().close()
        self.closed = True


class StrictChannelFactory(FakeChannelFactory):
    def __call__(self, **kwargs) -> StrictChannel:
        channel = StrictChannel(**kwargs)
        self.created[channel.name] = channel
        return channel


@pytest.fixture
def sleep_calls(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    calls: list[float] = []
    monkeypatch.setattr(l298n.time, "sleep", lambda seconds: calls.append(seconds))
    return calls


@pytest.fixture
def factory() -> FakeChannelFactory:
    return FakeChannelFactory()


@pytest.fixture
def driver(factory: FakeChannelFactory) -> L298NDriver:
    instance = L298NDriver(TRACKS, channel_factory=factory)
    instance.initialize()
    return instance


def _expected_schedule(start: float, target: float, step: float) -> list[float]:
    """Independent ramp expectation (does not call the helper under test)."""
    delta = target - start
    direction = 1.0 if delta > 0 else -1.0
    count = math.ceil(abs(delta) / step)
    return [start + direction * min(k * step, abs(delta)) for k in range(1, count + 1)]


def test_driver_is_an_imotor_driver():
    assert isinstance(L298NDriver(TRACKS, channel_factory=FakeChannelFactory()), IMotorDriver)


def test_initialize_creates_channels_from_config(factory: FakeChannelFactory):
    cfg = _tracks()
    instance = L298NDriver(TRACKS, channel_factory=factory)
    instance.initialize()

    assert instance.motor_names == list(cfg["motors"])
    for name, pins in cfg["motors"].items():
        channel = factory.created[name]
        assert channel.enable_gpio == pins["enable_gpio"]
        assert channel.in_a_gpio == pins["in_a_gpio"]
        assert channel.in_b_gpio == pins["in_b_gpio"]
        assert channel.pwm_frequency_hz == cfg["pwm_frequency_hz"]


def test_set_velocity_applies_the_configured_ramp(
    driver: L298NDriver, factory: FakeChannelFactory, sleep_calls: list[float]
):
    cfg = _tracks()
    target = 0.5
    driver.set_velocity("left", target)

    expected = _expected_schedule(0.0, target, cfg["ramp_step"])
    assert factory.created["left"].velocity_calls == pytest.approx(expected)
    assert factory.created["left"].velocity_calls[-1] == target
    assert driver.get_velocity("left") == target
    # One sleep per ramp step, each a fraction of ramp_seconds.
    assert sleep_calls == pytest.approx([cfg["ramp_seconds"] / len(expected)] * len(expected))


def test_set_velocity_clamps_to_the_config_limits(
    driver: L298NDriver, factory: FakeChannelFactory, sleep_calls: list[float]
):
    cfg = _tracks()
    max_velocity = cfg["limits"]["max_velocity"]
    driver.set_velocity("left", 5.0)

    calls = factory.created["left"].velocity_calls
    assert calls[-1] == max_velocity
    assert driver.get_velocity("left") == max_velocity
    # Never commands beyond the configured limit.
    assert all(abs(v) <= max_velocity for v in calls)


def test_set_velocity_negative_ramps_toward_the_target(
    driver: L298NDriver, factory: FakeChannelFactory, sleep_calls: list[float]
):
    cfg = _tracks()
    target = -0.5
    driver.set_velocity("right", target)

    assert factory.created["right"].velocity_calls == pytest.approx(
        _expected_schedule(0.0, target, cfg["ramp_step"])
    )
    assert driver.get_velocity("right") == target


def test_set_velocity_same_target_is_a_noop(
    driver: L298NDriver, factory: FakeChannelFactory, sleep_calls: list[float]
):
    driver.set_velocity("left", 0.5)
    factory.created["left"].velocity_calls.clear()
    sleep_calls.clear()

    driver.set_velocity("left", 0.5)

    assert factory.created["left"].velocity_calls == []
    assert sleep_calls == []


def test_stop_all_coasts_every_motor(driver: L298NDriver, factory: FakeChannelFactory):
    driver.set_velocity("left", 0.5)
    driver.set_velocity("right", -0.5)
    driver.stop_all()

    for name in driver.motor_names:
        assert factory.created[name].velocity_calls[-1] == 0.0
        assert driver.get_velocity(name) == 0.0


def test_brake_all_brakes_every_motor(driver: L298NDriver, factory: FakeChannelFactory):
    driver.brake_all()

    for name in driver.motor_names:
        assert factory.created[name].brake_calls == 1
        assert driver.get_velocity(name) == 0.0


def test_shutdown_closes_every_channel(driver: L298NDriver, factory: FakeChannelFactory):
    driver.shutdown()

    for name in driver.motor_names:
        assert factory.created[name].close_calls == 1
        assert driver.get_velocity(name) == 0.0


def test_shutdown_is_idempotent(
    driver: L298NDriver, factory: FakeChannelFactory
):
    """The IMotorDriver contract promises ``shutdown()`` is safe to call twice."""
    driver.shutdown()
    driver.shutdown()  # must not raise

    for name in driver.motor_names:
        assert factory.created[name].close_calls == 1  # closed exactly once


def test_second_shutdown_does_not_touch_closed_channels():
    """Regression: the redundant shutdown must not reach ``stop_all()``.

    ``stop_all()`` calls ``set_velocity()``; on a real closed gpiozero device
    that raises ``DeviceClosed``. The strict channel raises in the same way, so
    this test fails if the ``_closed`` guard is removed.
    """
    factory = StrictChannelFactory()
    instance = L298NDriver(TRACKS, channel_factory=factory)
    instance.initialize()
    instance.shutdown()

    instance.shutdown()  # without the guard -> set_velocity on a closed channel

    for name in instance.motor_names:
        channel = factory.created[name]
        assert channel.close_calls == 1
        assert channel.closed is True


def test_initialize_after_shutdown_rearms_the_driver(
    factory: FakeChannelFactory,
):
    instance = L298NDriver(TRACKS, channel_factory=factory)
    instance.initialize()
    instance.shutdown()
    closed_channels = dict(factory.created)

    instance.initialize()  # re-arm: brand new channels, driver usable again

    for name in instance.motor_names:
        assert factory.created[name] is not closed_channels[name]
        assert factory.created[name].close_calls == 0

    instance.shutdown()
    for name in instance.motor_names:
        assert factory.created[name].close_calls == 1
        assert instance.get_velocity(name) == 0.0


def test_wrong_driver_config_raises_value_error(tmp_path: Path):
    bad = tmp_path / "not_l298n.json"
    bad.write_text(json.dumps({"driver": "a4988"}), encoding="utf-8")
    with pytest.raises(ValueError, match="expected l298n config"):
        L298NDriver(bad, channel_factory=FakeChannelFactory())


def test_module_imports_without_gpio():
    """Regression: importing the driver must not pull in gpiozero/lgpio."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import hardware.drivers.l298n as m; assert m.L298NDriver",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
