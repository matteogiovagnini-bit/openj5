#!/usr/bin/env python3
"""
OpenJ5 bench demo - Nodo 6 tracks bring-up on L298N + 2x DC gear motors.

Interactive console:
    w = forward   s = backward   a = spin left   d = spin right
    x = stop      q = quit
    + / - = speed up / down (step 0.1)

Safety: run with wheels OFF the ground. Ctrl-C always stops the motors.
Usage:  python3 scripts/demo/tracks_bench.py [--config PATH]
"""
from __future__ import annotations

import argparse
import sys
import termios
import tty
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hardware.drivers.l298n import load_driver  # noqa: E402


def read_key() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenJ5 tracks bench demo")
    parser.add_argument("--config", default=None, help="path to tracks.json")
    args = parser.parse_args()

    driver = load_driver(args.config)
    speed = 0.5
    print(f"motors: {driver.motor_names} | speed: {speed:.1f}")
    print("w=forward s=back a=left-spin d=right-spin +=faster -=slower x=stop q=quit")

    try:
        while True:
            key = read_key()
            if key in ("w", "s"):
                driver.set_velocity("left", speed if key == "w" else -speed)
                driver.set_velocity("right", speed if key == "w" else -speed)
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
                speed = round(min(1.0, speed + 0.1), 1)
                print(f"\nspeed: {speed:.1f}")
            elif key == "-":
                speed = round(max(0.2, speed - 0.1), 1)
                print(f"\nspeed: {speed:.1f}")
            elif key == "q":
                break
            elif key in ("\x03",):
                break
    finally:
        driver.brake_all()
        driver.shutdown()
        print("\nmotors released, bye")


if __name__ == "__main__":
    main()
