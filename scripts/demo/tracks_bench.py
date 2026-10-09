#!/usr/bin/env python3
"""
OpenJ5 bench demo - Nodo 6 tracks bring-up on L298N + 2x DC gear motors.

Interactive console:
    w = forward   s = backward   a = spin left   d = spin right
    x = stop      q = quit
    + / - = speed up / down

Safety: run with wheels OFF the ground. Ctrl-C always brakes the motors.

Offline / SSH scripted use (non-interactive, no tty, works with --mock on Mac):
    python3 scripts/demo/tracks_bench.py --selftest --mock
    python3 scripts/demo/tracks_bench.py --selftest            # on the Pi (real GPIO)

All demo parameters come from the config (``config/bench/tracks.json``, ``demo``
section); ``--speed``/``--seconds`` override them on the command line.
Usage:  python3 scripts/demo/tracks_bench.py [--config PATH] [--mock] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

DEFAULT_CONFIG = REPO_ROOT / "config" / "bench" / "tracks.json"


def read_key() -> str:
    # termios/tty are only needed on the interactive path: import them here so
    # --selftest works over SSH without a tty (and never touches the terminal).
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def load_demo_config(config_path: str | None) -> dict[str, float]:
    """Read the demo parameters from the tracks config (no inline constants)."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    cfg = json.loads(path.read_text())
    demo = cfg["demo"]
    return {
        "speed": float(demo["speed"]),
        "min_speed": float(demo["min_speed"]),
        "max_speed": float(demo["max_speed"]),
        "speed_step": float(demo["speed_step"]),
    }


def build_driver(config_path: str | None, mock: bool):
    """Build the real L298N driver, or the CI-safe mock when ``--mock`` is set."""
    if mock:
        from hardware.drivers.mock_motor import load_driver as load_mock

        return load_mock(config_path)
    from hardware.drivers.l298n import load_driver as load_l298n

    return load_l298n(config_path)


def run_selftest(driver, seconds: float, speed: float) -> None:
    """Non-interactive scripted sequence (safe over SSH without a tty)."""
    phases = (
        ("forward", speed, speed),
        ("stop", 0.0, 0.0),
        ("backward", -speed, -speed),
        ("stop", 0.0, 0.0),
        ("spin-left", -speed, speed),
        ("spin-right", speed, -speed),
        ("stop", 0.0, 0.0),
    )
    print(
        f"selftest motors: {driver.motor_names} | speed: {speed:+.2f} "
        f"| phase: {seconds:.2f}s"
    )
    for name, left, right in phases:
        driver.set_velocity("left", left)
        driver.set_velocity("right", right)
        print(
            f"  {name:<10} left={driver.get_velocity('left'):+.2f} "
            f"right={driver.get_velocity('right'):+.2f}"
        )
        time.sleep(seconds)


def run_interactive(driver, demo: dict[str, float]) -> None:
    """Keyboard-driven console (needs a tty)."""
    speed = demo["speed"]
    step = demo["speed_step"]
    print(f"motors: {driver.motor_names} | speed: {speed:.2f}")
    print("w=forward s=back a=left-spin d=right-spin +=faster -=slower x=stop q=quit")
    while True:
        key = read_key()
        if key in ("w", "s"):
            velocity = speed if key == "w" else -speed
            driver.set_velocity("left", velocity)
            driver.set_velocity("right", velocity)
        elif key == "a":
            driver.set_velocity("left", -speed)
            driver.set_velocity("right", speed)
        elif key == "d":
            driver.set_velocity("left", speed)
            driver.set_velocity("right", -speed)
        elif key == "x":
            driver.stop_all()
            print("\nstopped")
        elif key == "+":
            speed = round(min(demo["max_speed"], speed + step), 2)
            print(f"\nspeed: {speed:.2f}")
        elif key == "-":
            speed = round(max(demo["min_speed"], speed - step), 2)
            print(f"\nspeed: {speed:.2f}")
        elif key in ("q", "\x03"):
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenJ5 tracks bench demo")
    parser.add_argument("--config", default=None, help="path to tracks.json")
    parser.add_argument(
        "--mock", action="store_true", help="use the CI-safe mock (no GPIO)"
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run a scripted sequence (non-interactive, SSH-safe)",
    )
    parser.add_argument(
        "--seconds", type=float, default=1.0, help="seconds per selftest phase"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=None,
        help="override the config demo speed (-1.0..1.0)",
    )
    args = parser.parse_args()

    demo = load_demo_config(args.config)
    speed = args.speed if args.speed is not None else demo["speed"]

    driver = build_driver(args.config, args.mock)
    try:
        if args.selftest:
            run_selftest(driver, args.seconds, speed)
        else:
            run_interactive(driver, demo)
    finally:
        driver.brake_all()
        driver.shutdown()
        print("motors released, bye")


if __name__ == "__main__":
    main()
