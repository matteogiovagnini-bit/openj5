"""Unit tests for the non-interactive bench demo (``scripts/demo/tracks_bench.py``).

The demo lives outside ``tests/`` and outside the ``src`` package, so it is
loaded by path with ``importlib``. ``run_selftest`` must complete without a tty
(SSH-safe) and leave both motors at rest; ``--selftest`` is the scripted path.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from hardware.drivers.mock_motor import MockMotorDriver

ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = ROOT / "scripts" / "demo" / "tracks_bench.py"
TRACKS = ROOT / "config" / "bench" / "tracks.json"


@pytest.fixture(scope="module")
def demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tracks_bench", DEMO_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_demo_config_reads_the_tracks_json(demo: ModuleType):
    expected = json.loads(TRACKS.read_text(encoding="utf-8"))["demo"]
    params = demo.load_demo_config(None)
    assert params == {
        "speed": expected["speed"],
        "min_speed": expected["min_speed"],
        "max_speed": expected["max_speed"],
        "speed_step": expected["speed_step"],
    }


def test_build_driver_mock_returns_mock_driver(demo: ModuleType):
    driver = demo.build_driver(None, mock=True)
    assert isinstance(driver, MockMotorDriver)


def test_run_selftest_uses_sleep_and_finishes_at_rest(
    demo: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    driver = demo.build_driver(None, mock=True)
    sleeps: list[float] = []
    monkeypatch.setattr(demo.time, "sleep", lambda seconds: sleeps.append(seconds))

    # 7 phases, one sleep each; never touches a tty.
    demo.run_selftest(driver, seconds=0.5, speed=0.5)

    assert sleeps == [0.5] * 7
    assert driver.get_velocity("left") == 0.0
    assert driver.get_velocity("right") == 0.0

    out = capsys.readouterr().out
    assert "forward" in out
    assert "spin-left" in out
    assert "spin-right" in out
