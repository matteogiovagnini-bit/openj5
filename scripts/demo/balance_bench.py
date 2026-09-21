#!/usr/bin/env python3
"""
OpenJ5 bench demo - Node 7 balance bring-up (A4988 + NEMA17).

Interactive console (position moves, degrees):
    l      = begin automatic leveling on the body IMU (not present on the bench)
    t <deg> = tilt to a fixed angle (e.g. "t 10", "t -15")
    s      = stow to 0 deg
    x      = stop and hold
    p      = print current position (steps + deg)
    q      = quit

Safety: run with the joint unloaded, belt on, keep fingers clear of the drive.
Ctrl-C brakes and releases. The bench cannot level (no IMU): use the mock
simulator for the leveling loop (tests/unit/test_balance_control.py).
Usage:  python3 scripts/demo/balance_bench.py [--config PATH]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hardware.drivers.a4988 import load_driver  # noqa: E402

STEPS_PER_DEG = 200 * 16 * 4 / 360.0  # motor / microstep / belt ratio from bench config


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenJ5 balance (A4988) bench demo")
    parser.add_argument("--config", default=None, help="path to balance.json (default bench)")
    args = parser.parse_args()

    driver = load_driver(args.config)
    print("A4988 balance joint | l=level(imu) t <deg>=tilt s=stow x=hold p=position q=quit")

    try:
        while True:
            line = input("> ").strip().lower()
            if not line:
                continue
            if line == "l":
                print("leveling needs the body IMU (MPU6050): use the simulator for now")
            elif line.startswith("t"):
                try:
                    deg = float(line.split()[1])
                except (IndexError, ValueError):
                    print("usage: t <deg>")
                    continue
                steps = int(round(deg * STEPS_PER_DEG))
                print(f"tilt to {deg:+.1f} deg = {steps} steps...")
                driver.set_position_steps(steps)
                print("done")
            elif line == "s":
                print("stow to 0 deg...")
                driver.set_position_steps(0)
                print("done")
            elif line == "x":
                driver.brake()
                print("holding")
            elif line == "p":
                pos = driver.get_position_steps()
                print(f"position: {pos} steps = {pos / STEPS_PER_DEG:+.2f} deg")
            elif line == "q":
                break
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        driver.shutdown()
        print("joint released, bye")


if __name__ == "__main__":
    main()