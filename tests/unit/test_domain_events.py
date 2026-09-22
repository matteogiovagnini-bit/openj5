"""Unit tests for core domain events (T-003).

Immutable DomainEvent hierarchy, per-class categories, registry (EVENT_CLASSES),
schemas, factory and deserializer.
"""
import time

import pytest

from core.domain import (
    BatteryTelemetryEvent, BalanceStateChangedEvent, BodyCommandEvent,
    BodyTelemetryEvent, DomainEvent, EventCategory, FaceDetectedEvent,
    HardwareFaultEvent, MoveHeadCommandEvent, NodeStateChangedEvent,
    OTADeployedEvent, ServoTelemetryEvent, SafetyViolationEvent,
)
from core.domain.events import (
    EVENT_CATEGORIES, EVENT_CLASSES, EVENT_SCHEMAS, create_event,
    deserialize_event,
)


# === Base event ===

def test_base_event_defaults():
    event = DomainEvent()
    assert event.event_type == "DomainEvent"
    assert event.event_version == 1
    assert event.category is EventCategory.BUSINESS
    assert event.correlation_id == event.event_id  # defaults to own id
    assert event.payload == {}
    assert 0.0 < event.timestamp <= time.time()


def test_base_event_to_dict_contract():
    data = DomainEvent(source_node="node1").to_dict()
    assert set(data) == {
        "event_id", "event_type", "event_version", "category",
        "timestamp", "source_node", "correlation_id", "causation_id", "payload",
    }
    assert data["category"] == "business"  # serialized as value, not enum


def test_explicit_correlation_is_preserved():
    event = DomainEvent(correlation_id="corr-1", causation_id="cause-1")
    assert event.correlation_id == "corr-1"
    assert event.causation_id == "cause-1"


def test_events_are_immutable():
    event = MoveHeadCommandEvent()
    with pytest.raises(AttributeError):
        event.target_x = 1.0  # frozen dataclass


def test_payload_defaults_not_shared_between_instances():
    first, second = BodyCommandEvent(), BodyCommandEvent()
    first.payload["action"] = "tilt"
    assert second.payload == {}


# === Per-class categories ===

@pytest.mark.parametrize("cls,expected", [
    (MoveHeadCommandEvent, EventCategory.COMMAND),
    (ServoTelemetryEvent, EventCategory.TELEMETRY),
    (NodeStateChangedEvent, EventCategory.STATE),
    (HardwareFaultEvent, EventCategory.ERROR),
    (FaceDetectedEvent, EventCategory.BUSINESS),
])
def test_subclass_declares_its_category(cls, expected):
    assert cls().category is expected


def test_body_command_event_carries_logical_intent():
    event = BodyCommandEvent(action="tilt", angle_deg=15.0)
    assert event.category is EventCategory.COMMAND
    assert event.action == "tilt"
    assert event.angle_deg == 15.0


def test_body_telemetry_and_balance_state_events():
    telemetry = BodyTelemetryEvent(body_pitch_deg=1.2, control_hz=100)
    state = BalanceStateChangedEvent(enabled=True, target_pitch_deg=0.0)
    assert telemetry.category is EventCategory.TELEMETRY
    assert state.category is EventCategory.STATE
    assert state.enabled


def test_serialization_roundtrip_on_subclass():
    original = MoveHeadCommandEvent(target_x=0.8, source_node="sdk")
    restored = MoveHeadCommandEvent.from_dict(original.to_dict())
    assert restored == original
    assert restored.category is EventCategory.COMMAND
    # Subclass-specific fields must survive the roundtrip (they used to be
    # silently dropped by to_dict, losing payload data on every publish).
    assert restored.target_x == 0.8


def test_base_from_dict_drops_unknown_subclass_fields():
    data = MoveHeadCommandEvent(target_x=0.5).to_dict()
    base = DomainEvent.from_dict(data)
    assert type(base) is DomainEvent
    assert base.event_id == data["event_id"]
    assert base.category is EventCategory.COMMAND  # coerced from string


def test_from_dict_coerces_wire_scalars():
    # Redis returns strings for numbers.
    data = MoveHeadCommandEvent(target_x=0.5).to_dict()
    data["event_version"] = str(data["event_version"])
    data["timestamp"] = str(data["timestamp"])
    restored = MoveHeadCommandEvent.from_dict(data)
    assert restored.event_version == 1
    assert isinstance(restored.timestamp, float)


# === Registry, categories and schemas ===

def test_event_classes_registry_is_complete_and_valid():
    assert len(EVENT_CLASSES) == 29
    for name, cls in EVENT_CLASSES.items():
        assert cls.__name__ == name
        assert issubclass(cls, DomainEvent)
        cls()  # every registered event must be instantiable


def test_event_categories_match_actual_instances():
    for name, cls in EVENT_CLASSES.items():
        assert EVENT_CATEGORIES[name] is cls().category, name


def test_move_head_category_is_command_not_business():
    # Regression: EVENT_CATEGORIES used to read the class-level default and
    # reported BUSINESS for every event.
    assert EVENT_CATEGORIES["MoveHeadCommandEvent"] is EventCategory.COMMAND


def test_event_schemas_declare_correct_category_and_required_fields():
    for name, schema in EVENT_SCHEMAS.items():
        assert schema["properties"]["event_type"]["const"] == name
        assert schema["properties"]["category"]["const"] == EVENT_CATEGORIES[name].value
        assert "event_id" in schema["required"]
        assert "payload" in schema["required"]


def test_event_schema_for_body_command():
    schema = EVENT_SCHEMAS["BodyCommandEvent"]
    assert schema["properties"]["category"]["const"] == "command"
    assert schema["properties"]["event_version"]["const"] == 1


# === Factory & deserializer ===

def test_create_event_builds_typed_instance():
    event = create_event("BodyCommandEvent", action="stow")
    assert isinstance(event, BodyCommandEvent)
    assert event.action == "stow"


def test_create_event_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown event type"):
        create_event("NotAnEvent")


def test_deserialize_event_roundtrip():
    original = BatteryTelemetryEvent(voltage_v=10.4, percentage=12.0)
    restored = deserialize_event(original.to_dict())
    assert restored == original


def test_deserialize_event_unknown_type_falls_back_to_base():
    restored = deserialize_event({"event_type": "LegacyEvent", "payload": {}})
    assert type(restored) is DomainEvent
    assert restored.event_type == "LegacyEvent"


def test_ota_deployed_event_defaults():
    event = OTADeployedEvent(node_id="node2", firmware_version="0.3.0")
    assert event.success and not event.rollback
    assert event.category is EventCategory.BUSINESS


def test_safety_violation_event_fields():
    event = SafetyViolationEvent(
        node_id="node6", violation_type="velocity_limit", command_id="cmd-1",
    )
    assert event.category is EventCategory.ERROR
    assert event.violation_type == "velocity_limit"
