"""Shared fixtures for core domain unit tests (T-003).

Builders construct valid domain objects so individual tests only vary the
property under examination. No I/O, no external services: unit tests run
against the pure domain only (CODING_STANDARD §8).
"""
import time

import pytest

from core.domain import (
    Angle, MotorConfig, Node, NodeHealth, NodeIdentity, NodeState, NodeType,
    PIDConfig, Robot, ServoConfig, StepperConfig,
)


@pytest.fixture
def servo_config() -> ServoConfig:
    return ServoConfig(
        name="neck_yaw", channel=0,
        min_pulse=100, max_pulse=500, home_pulse=300,
        min_angle=Angle(-90.0), max_angle=Angle(90.0), home_angle=Angle(0.0),
        speed_dps=180.0, acceleration_dps2=360.0,
        offset=Angle(0.0), reversed=False, calibration={},
    )


@pytest.fixture
def motor_config() -> MotorConfig:
    return MotorConfig(
        motor_id="left_track", motor_type="dc_geared",
        encoder_ppr=1440, gear_ratio=30.0, wheel_diameter_mm=65.0,
        max_rpm=300.0,
        pid=PIDConfig(
            kp=1.0, ki=0.1, kd=0.01,
            output_min=-1.0, output_max=1.0,
            integral_min=-0.5, integral_max=0.5,
        ),
    )


@pytest.fixture
def stepper_config() -> StepperConfig:
    return StepperConfig(
        name="balance_joint", steps_per_rev=200, microsteps=16, gear_ratio=4.0,
    )


def _make_health(
    node_id: str,
    state: NodeState = NodeState.RUNNING,
    temperature_c: float = 40.0,
    heartbeat_age_s: float = 0.1,
    errors: list[str] | None = None,
) -> NodeHealth:
    return NodeHealth(
        node_id=node_id, state=state,
        cpu_percent=10.0, memory_percent=20.0,
        temperature_c=temperature_c, uptime_sec=60.0,
        last_heartbeat=time.time() - heartbeat_age_s,
        errors=list(errors or []), warnings=[],
    )


@pytest.fixture
def make_node():
    """Factory: valid Node with identity + health (keyword overrides allowed)."""

    def _make(
        node_id: str = "node2",
        node_type: NodeType = NodeType.HEAD,
        state: NodeState = NodeState.RUNNING,
        temperature_c: float = 40.0,
        heartbeat_age_s: float = 0.1,
        errors: list[str] | None = None,
    ) -> Node:
        identity = NodeIdentity(
            node_id=node_id, name=node_id, node_type=node_type,
            hardware="esp32-s3", firmware_version="0.2.0", hardware_version="1.0",
        )
        health = _make_health(node_id, state, temperature_c, heartbeat_age_s, errors)
        return Node(identity=identity, health=health)

    return _make


@pytest.fixture
def robot(make_node) -> Robot:
    """Healthy robot aggregate with one RUNNING node."""
    agg = Robot()
    agg.add_node(make_node())
    return agg
