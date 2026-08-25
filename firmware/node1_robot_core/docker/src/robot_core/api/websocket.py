"""
OpenJ5 Robot Core - WebSocket Handler

Real-time event streaming and bidirectional communication.
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from robot_core.eventbus import EventBus, DomainEvent
from robot_core.statemachine import StateMachineOrchestrator
from robot_core.health import HealthService


def create_websocket_handler(
    event_bus: EventBus,
    state_machine: StateMachineOrchestrator,
    health_service: HealthService,
) -> APIRouter:

    router = APIRouter()
    connections: dict[str, WebSocket] = {}

    @router.websocket("/events")
    async def event_stream(ws: WebSocket, token: str = Query("")):
        """WebSocket endpoint for real-time robot events."""
        await ws.accept()

        client_id = str(uuid.uuid4())
        connections[client_id] = ws

        # Send welcome message
        await ws.send_json({
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat(),
        })

        async def send_event(event: DomainEvent) -> None:
            """Send event to this WebSocket client."""
            try:
                await ws.send_json({
                    "type": "event",
                    "event_type": event.event_type,
                    "source_node": event.source_node,
                    "payload": event.payload,
                    "aggregate_id": event.aggregate_id or "",
                    "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                })
            except Exception:
                pass

        subscription = await event_bus.subscribe("*", send_event)

        try:
            while True:
                data = await ws.receive_text()
                message = json.loads(data)

                msg_type = message.get("type", "")

                if msg_type == "ping":
                    await ws.send_json({"type": "pong"})

                elif msg_type == "subscribe":
                    event_types = message.get("event_types", [])
                    await event_bus.subscribe_filtered(event_types, send_event)
                    await ws.send_json({
                        "type": "subscribed",
                        "event_types": event_types,
                    })

                elif msg_type == "command":
                    cmd = message.get("command", {})
                    await event_bus.publish(DomainEvent(
                        event_type=cmd.get("event_type", "UserCommand"),
                        source_node="websocket",
                        payload={
                            "client_id": client_id,
                            "command_type": cmd.get("command_type", ""),
                            "parameters": cmd.get("parameters", {}),
                            "timestamp": datetime.now().isoformat(),
                        },
                    ))
                    await ws.send_json({
                        "type": "command_ack",
                        "command_type": cmd.get("command_type", ""),
                    })

                elif msg_type == "state_query":
                    robot_state = await health_service.check_all()
                    await ws.send_json({
                        "type": "state_update",
                        "state": robot_state.state,
                        "overall": robot_state.overall,
                        "nodes": {
                            nid: {
                                "state": nh.state,
                                "cpu": nh.cpu_percent,
                                "memory": nh.memory_percent,
                                "errors": len(nh.errors),
                            }
                            for nid, nh in robot_state.node_health.items()
                        },
                    })

        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            connections.pop(client_id, None)
            await event_bus.unsubscribe(subscription)

    return router
