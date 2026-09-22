"""Unit tests for core domain commands, queries and buses (T-003).

Includes a regression guard for the abstract ``__post_init__`` defect that
made 9 command classes uninstantiable (breaking ~50 SDK dispatch sites).
"""
import asyncio
import time

import pytest

from core.domain import (
    BehaviorCommand, BodyCommand, Command, CommandBus, CommandError,
    DeployOTACommand, EmergencyStopCommand, GetBalanceStateQuery,
    GetBatteryStateQuery, GetBodyTiltQuery, GetNodeHealthQuery,
    GetPluginListQuery, GetRobotStateQuery, LoadPluginCommand, MoveArmCommand,
    MoveHeadCommand, MoveTracksCommand, Query, QueryBus, Result,
    SayTextCommand, SetExpressionCommand, SetLEDCommand, UnloadPluginCommand,
)
from core.domain.commands import (
    CommandHandler, GetCalibrationQuery, GetConfigQuery, QueryHandler,
    SaveCalibrationCommand, SetConfigurationCommand,
)

ALL_COMMANDS = [
    MoveHeadCommand, MoveArmCommand, MoveTracksCommand, BodyCommand,
    SetExpressionCommand, SetLEDCommand, BehaviorCommand,
    EmergencyStopCommand, DeployOTACommand, LoadPluginCommand,
    UnloadPluginCommand, SaveCalibrationCommand, SetConfigurationCommand,
]

ALL_QUERIES = [
    GetRobotStateQuery, GetNodeHealthQuery, GetBatteryStateQuery,
    GetPluginListQuery, GetBodyTiltQuery, GetBalanceStateQuery,
    GetConfigQuery, GetCalibrationQuery,
]


# === Result ===

def test_result_ok_and_truthiness():
    result = Result.ok({"state": "running"}, source="test")
    assert result.success and result
    assert result.data == {"state": "running"}
    assert result.metadata == {"source": "test"}
    assert result.unwrap() == {"state": "running"}


def test_result_fail_and_unwrap_raises():
    result = Result.fail("E_MOVE", "cannot move", {"limit": 1})
    assert not result
    assert result.error_code == "E_MOVE"
    with pytest.raises(CommandError) as exc:
        result.unwrap()
    assert exc.value.code == "E_MOVE"
    assert exc.value.message == "cannot move"
    assert exc.value.details == {"limit": 1}


def test_command_error_string_form():
    err = CommandError("E_X", "boom")
    assert str(err) == "E_X: boom"
    assert err.details == {}


# === Base classes ===

def test_command_defaults():
    cmd = MoveHeadCommand()
    assert isinstance(cmd, Command)
    assert len(cmd.command_id) == 36  # uuid4
    assert cmd.correlation_id == "" and cmd.causation_id == ""
    assert cmd.metadata == {}
    assert cmd.timestamp <= time.time()


def test_query_defaults():
    query = GetRobotStateQuery()
    assert isinstance(query, Query)
    assert len(query.query_id) == 36
    assert query.correlation_id == ""


def test_every_command_is_instantiable():
    """Regression: commands without their own __post_init__ used to be
    abstract (and therefore uninstantiable) through Command."""
    for cls in ALL_COMMANDS:
        cls()
    SayTextCommand(text="validated command")  # has a mandatory invariant


def test_every_query_is_instantiable():
    for cls in ALL_QUERIES:
        cls()


# === Validation (invariant enforcement in __post_init__) ===

def test_move_head_speed_bounds():
    MoveHeadCommand(speed=0.0)
    MoveHeadCommand(speed=1.0)
    with pytest.raises(ValueError, match="speed"):
        MoveHeadCommand(speed=1.5)


def test_move_arm_validation():
    assert MoveArmCommand(arm="left").arm == "left"
    with pytest.raises(ValueError, match="arm"):
        MoveArmCommand(arm="middle")
    with pytest.raises(ValueError, match="speed"):
        MoveArmCommand(speed=-0.1)


def test_move_tracks_limits():
    MoveTracksCommand(linear_velocity=0.5, angular_velocity=1.0)
    with pytest.raises(ValueError, match="linear_velocity"):
        MoveTracksCommand(linear_velocity=0.6)
    with pytest.raises(ValueError, match="angular_velocity"):
        MoveTracksCommand(angular_velocity=-1.2)


def test_body_command_validation():
    BodyCommand(action="level")
    BodyCommand(action="tilt", angle_deg=35.0, speed=1.0)
    with pytest.raises(ValueError, match="action"):
        BodyCommand(action="wobble")
    with pytest.raises(ValueError, match="speed"):
        BodyCommand(action="level", speed=0.0)
    with pytest.raises(ValueError, match="angle_deg"):
        BodyCommand(action="tilt", angle_deg=-91.0)


def test_say_text_requires_content():
    SayTextCommand(text="hello")
    with pytest.raises(ValueError, match="text"):
        SayTextCommand(text="")


def test_simple_commands_carry_defaults():
    assert SetExpressionCommand().expression == "neutral"
    assert SetLEDCommand().pattern == "solid"
    assert BehaviorCommand().behavior == "idle"
    assert EmergencyStopCommand().scope == "all"
    assert DeployOTACommand().target_nodes == []
    assert LoadPluginCommand().config == {}
    assert UnloadPluginCommand().plugin_id == ""
    assert SaveCalibrationCommand().data == {}
    assert SetConfigurationCommand().persistent


# === CommandBus ===

class _ResultHandler:
    async def handle(self, command):
        return Result.ok(type(command).__name__)


class _RawHandler:
    async def handle(self, command):
        return "raw-payload"


class _CommandErrorHandler:
    async def handle(self, command):
        raise CommandError("E_BLOCKED", "blocked by safety", {"rule": "ws"})


class _BoomHandler:
    async def handle(self, command):
        raise RuntimeError("kaput")


def test_command_bus_unknown_command_has_no_handler():
    bus = CommandBus()
    result = asyncio.run(bus.dispatch(MoveHeadCommand()))
    assert not result.success
    assert result.error_code == "NO_HANDLER"


def test_command_bus_passes_result_through():
    bus = CommandBus()
    bus.register(MoveHeadCommand, _ResultHandler())
    result = asyncio.run(bus.dispatch(MoveHeadCommand()))
    assert result.success
    assert result.data == "MoveHeadCommand"


def test_command_bus_wraps_non_result_return():
    bus = CommandBus()
    bus.register(BodyCommand, _RawHandler())
    result = asyncio.run(bus.dispatch(BodyCommand(action="level")))
    assert result.success and result.data == "raw-payload"


def test_command_bus_maps_command_error():
    bus = CommandBus()
    bus.register(MoveTracksCommand, _CommandErrorHandler())
    result = asyncio.run(bus.dispatch(MoveTracksCommand()))
    assert not result.success
    assert result.error_code == "E_BLOCKED"
    assert result.metadata == {"rule": "ws"}


def test_command_bus_maps_unexpected_exception():
    bus = CommandBus()
    bus.register(EmergencyStopCommand, _BoomHandler())
    result = asyncio.run(bus.dispatch(EmergencyStopCommand()))
    assert not result.success
    assert result.error_code == "HANDLER_ERROR"
    assert result.error_message == "kaput"


def test_command_bus_registration_is_last_wins():
    bus = CommandBus()
    bus.register(BehaviorCommand, _ResultHandler())
    bus.register(BehaviorCommand, _RawHandler())
    result = asyncio.run(bus.dispatch(BehaviorCommand()))
    assert result.data == "raw-payload"


# === QueryBus ===

def test_query_bus_unknown_query_has_no_handler():
    bus = QueryBus()
    result = asyncio.run(bus.dispatch(GetBodyTiltQuery()))
    assert result.error_code == "NO_HANDLER"


def test_query_bus_wraps_and_maps_errors():
    bus = QueryBus()
    bus.register(GetRobotStateQuery, _RawHandler())
    bus.register(GetNodeHealthQuery, _CommandErrorHandler())
    bus.register(GetBalanceStateQuery, _BoomHandler())

    ok = asyncio.run(bus.dispatch(GetRobotStateQuery()))
    assert ok.success and ok.data == "raw-payload"

    blocked = asyncio.run(bus.dispatch(GetNodeHealthQuery()))
    assert blocked.error_code == "E_BLOCKED"

    boom = asyncio.run(bus.dispatch(GetBalanceStateQuery()))
    assert boom.error_code == "HANDLER_ERROR"


def test_query_bus_passes_result_through():
    bus = QueryBus()
    bus.register(GetBatteryStateQuery, _ResultHandler())
    result = asyncio.run(bus.dispatch(GetBatteryStateQuery()))
    assert result.success and result.data == "GetBatteryStateQuery"


# === Handler contracts ===

def test_handlers_are_abstract_contracts():
    with pytest.raises(TypeError):
        CommandHandler()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        QueryHandler()  # type: ignore[abstract]

    class _Concrete(CommandHandler):
        async def handle(self, command):
            return Result.ok()

    assert isinstance(_Concrete(), CommandHandler)
