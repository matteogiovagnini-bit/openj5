"""Unit tests for core domain repository ports (T-003).

Repositories are Protocol contracts (ports): verify the expected surface
exists so adapters and consumers fail loudly at import/test time instead of
with runtime AttributeErrors.
"""
from typing import get_args, get_origin

import pytest

from core.domain import (
    ICalibrationRepository, IConfigRepository, IEventStore, IMotorRepository,
    INodeRepository, IPluginRepository, IRobotRepository, IServoRepository,
    IUnitOfWork, UnitOfWorkConfig,
)
from core.domain.repositories import IRepository


def _is_protocol(obj) -> bool:
    # typing.is_protocol is Python 3.12+; _is_protocol exists since 3.8.
    return bool(getattr(obj, "_is_protocol", False))

REPOSITORY_INTERFACES = [
    (IRobotRepository, {"get_by_id", "save", "delete", "exists",
                        "get_current_robot", "get_robot_history"}),
    (INodeRepository, {"get_by_id", "save", "delete", "exists",
                       "get_by_identity", "get_all_nodes", "get_nodes_by_type",
                       "update_state", "update_last_seen", "update_health"}),
    (IServoRepository, {"get_by_id", "save", "delete", "exists",
                        "get_by_node", "get_by_name", "update_calibration",
                        "update_position", "update_target"}),
    (IMotorRepository, {"get_by_id", "save", "delete", "exists",
                        "get_by_node", "update_odometry",
                        "update_target_velocity"}),
    (IPluginRepository, {"get_by_id", "save", "delete", "exists",
                         "get_enabled_plugins", "get_by_metadata",
                         "update_state", "update_config"}),
    (ICalibrationRepository, {"get_by_id", "save", "delete", "exists",
                              "get_by_node", "get_latest", "get_by_component"}),
]

SERVICE_INTERFACES = [
    (IEventStore, {"append", "get_events", "get_events_by_type",
                   "get_events_by_correlation", "get_events_by_node"}),
    (IConfigRepository, {"get", "set", "get_schema", "validate", "watch",
                         "unwatch", "reload"}),
]


@pytest.mark.parametrize("iface,methods", REPOSITORY_INTERFACES + SERVICE_INTERFACES)
def test_interface_is_protocol_with_expected_methods(iface, methods):
    assert _is_protocol(iface)
    for method in methods:
        assert hasattr(iface, method), f"{iface.__name__} misses {method}"


def test_base_repository_is_generic_protocol():
    assert _is_protocol(IRepository)
    bound = IRepository[object]
    assert get_origin(bound) is not None
    assert get_args(bound) == (object,)


def test_unit_of_work_exposes_all_ports():
    annotations = IUnitOfWork.__annotations__
    expected = {
        "robot", "nodes", "servos", "motors", "plugins", "calibrations",
        "events", "config",
    }
    assert expected <= set(annotations)
    for method in ("commit", "rollback"):
        assert hasattr(IUnitOfWork, method)


def test_unit_of_work_config_defaults():
    config = UnitOfWorkConfig()
    assert not config.read_only
    assert config.timeout == 30.0


def test_unit_of_work_config_custom():
    config = UnitOfWorkConfig(read_only=True, timeout=5.0)
    assert config.read_only and config.timeout == 5.0
