"""
OpenJ5 Robot Core - State Machine Orchestrator

Orchestrates state machines across all 6 nodes.
Coordinates global robot state from individual node states.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from robot_core.config import ConfigService
from robot_core.eventbus import EventBus, DomainEvent
from robot_core.logging import get_logger

logger = get_logger(__name__)


class NodeState(str, Enum):
    """Node lifecycle states."""
    BOOT = "boot"
    INIT = "init"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    RECOVERY = "recovery"
    SHUTDOWN = "shutdown"


class RobotState(str, Enum):
    """Aggregate robot states."""
    BOOTING = "booting"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    ERROR = "error"
    RECOVERING = "recovering"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


# Valid node state transitions
NODE_TRANSITIONS = {
    NodeState.BOOT: [NodeState.INIT, NodeState.ERROR],
    NodeState.INIT: [NodeState.READY, NodeState.ERROR],
    NodeState.READY: [NodeState.RUNNING, NodeState.SHUTDOWN],
    NodeState.RUNNING: [NodeState.READY, NodeState.ERROR, NodeState.SHUTDOWN],
    NodeState.ERROR: [NodeState.RECOVERY, NodeState.SHUTDOWN],
    NodeState.RECOVERY: [NodeState.READY, NodeState.ERROR, NodeState.SHUTDOWN],
    NodeState.SHUTDOWN: [],
}


@dataclass
class NodeStateInfo:
    """Node state information."""
    node_id: str
    node_type: str
    state: NodeState = NodeState.BOOT
    previous_state: NodeState = NodeState.BOOT
    last_transition: str = field(default_factory=datetime.now().isoformat)
    transition_count: int = 0
    errors: list[str] = field(default_factory=list)
    health_score: float = 1.0


@dataclass
class RobotStateInfo:
    """Aggregate robot state."""
    state: RobotState = RobotState.BOOTING
    nodes: dict[str, NodeStateInfo] = field(default_factory=dict)
    last_update: str = field(default_factory=datetime.now().isoformat)
    degraded_nodes: list[str] = field(default_factory=list)
    critical_errors: list[str] = field(default_factory=list)


class StateMachineOrchestrator:
    """
    Orchestrates state machines across all nodes.
    
    Responsibilities:
    - Track individual node states
    - Compute aggregate robot state
    - Coordinate global state transitions
    - Handle fault propagation and recovery
    - Publish state change events
    """
    
    def __init__(
        self,
        config: ConfigService,
        event_bus: EventBus,
        database=None,
        node_clients: dict[str, Any] = None,  # MQTT clients or gateways per node
    ):
        self.config = config
        self.event_bus = event_bus
        self.database = database
        self.node_clients = node_clients or {}
        
        self._robot_state = RobotStateInfo()
        self._running = False
        self._lock = asyncio.Lock()
        
        # Node type definitions
        self.node_types = {
            "node1": "robot_core",
            "node2": "head",
            "node3": "right_arm",
            "node4": "left_arm",
            "node5": "torso",
            "node6": "tracks",
        }
        
        # Critical nodes (if these fail, robot goes to ERROR)
        self.critical_nodes = {"node1", "node6"}  # Core + Tracks
        
        # Subscriptions
        self._subscriptions: list[str] = []
    
    async def start(self) -> None:
        """Start state machine orchestrator."""
        if self._running:
            return
        
        # Subscribe to node state events
        await self._subscribe_to_node_events()
        
        # Initialize all nodes as BOOT
        for node_id, node_type in self.node_types.items():
            self._robot_state.nodes[node_id] = NodeStateInfo(
                node_id=node_id,
                node_type=node_type,
            )
        
        # Start monitoring tasks
        self._running = True
        asyncio.create_task(self._monitor_node_health())
        asyncio.create_task(self._compute_robot_state_loop())
        
        logger.info("State machine orchestrator started")
    
    async def stop(self) -> None:
        """Stop orchestrator."""
        self._running = False
        
        # Unsubscribe
        for sub_id in self._subscriptions:
            await self.event_bus.unsubscribe(sub_id)
        self._subscriptions.clear()
        
        logger.info("State machine orchestrator stopped")
    
    async def _subscribe_to_node_events(self) -> None:
        """Subscribe to node state change events."""
        sub_id = await self.event_bus.subscribe(
            "NodeStateChanged",
            self._handle_node_state_change,
        )
        self._subscriptions.append(sub_id)
    
    async def _handle_node_state_change(self, event: DomainEvent) -> None:
        """Handle node state change event."""
        payload = event.payload
        node_id = payload.get("node_id")
        new_state = payload.get("new_state")
        previous_state = payload.get("previous_state", "")
        reason = payload.get("reason", "")
        
        if not node_id or not new_state:
            return
        
        async with self._lock:
            node_info = self._robot_state.nodes.get(node_id)
            if not node_info:
                logger.warning("State change for unknown node", node_id=node_id)
                return
            
            # Validate transition
            valid_next = NODE_TRANSITIONS.get(node_info.state, [])
            if NodeState(new_state) not in valid_next:
                logger.warning(
                    "Invalid state transition",
                    node_id=node_id,
                    from_state=node_info.state,
                    to_state=new_state,
                )
                # Allow but log
            
            # Update node state
            node_info.previous_state = node_info.state
            node_info.state = NodeState(new_state)
            node_info.last_transition = datetime.now().isoformat()
            node_info.transition_count += 1
            
            if reason:
                node_info.errors.append(f"{datetime.now().isoformat()}: {reason}")
            
            # Recompute robot state
            await self._recompute_robot_state()
            
            logger.info(
                "Node state changed",
                node_id=node_id,
                from_state=previous_state,
                to_state=new_state,
                reason=reason,
            )
    
    async def _recompute_robot_state(self) -> None:
        """Recompute aggregate robot state from node states."""
        nodes = self._robot_state.nodes
        
        # Count states
        state_counts = {state: 0 for state in NodeState}
        for node_info in nodes.values():
            state_counts[node_info.state] += 1
        
        total_nodes = len(nodes)
        critical_down = any(
            nodes[n].state in (NodeState.ERROR, NodeState.SHUTDOWN)
            for n in self.critical_nodes
        )
        
        # Determine robot state
        old_state = self._robot_state.state
        
        if critical_down:
            new_state = RobotState.ERROR
        elif state_counts[NodeState.BOOT] == total_nodes:
            new_state = RobotState.BOOTING
        elif state_counts[NodeState.INIT] > 0:
            new_state = RobotState.INITIALIZING
        elif state_counts[NodeState.ERROR] > 0:
            new_state = RobotState.DEGRADED
        elif state_counts[NodeState.RECOVERY] > 0:
            new_state = RobotState.RECOVERING
        elif state_counts[NodeState.SHUTDOWN] == total_nodes:
            new_state = RobotState.SHUTDOWN
        elif state_counts[NodeState.SHUTDOWN] > 0:
            new_state = RobotState.SHUTTING_DOWN
        elif state_counts[NodeState.READY] == total_nodes:
            new_state = RobotState.READY
        elif state_counts[NodeState.RUNNING] == total_nodes:
            new_state = RobotState.RUNNING
        else:
            new_state = RobotState.DEGRADED
        
        # Update degraded nodes list
        self._robot_state.degraded_nodes = [
            n for n, info in nodes.items()
            if info.state in (NodeState.ERROR, NodeState.RECOVERY)
        ]
        
        if new_state != old_state:
            self._robot_state.state = new_state
            self._robot_state.last_update = datetime.now().isoformat()
            
            # Publish robot state change event
            await self.event_bus.publish(DomainEvent(
                event_type="RobotStateChanged",
                source_node="node1",
                payload={
                    "previous_state": old_state.value,
                    "new_state": new_state.value,
                    "nodes": {n: info.state.value for n, info in nodes.items()},
                },
            ))
            
            logger.info("Robot state changed", from_state=old_state, to_state=new_state)
    
    async def _monitor_node_health(self) -> None:
        """Monitor node health and detect stuck states."""
        while self._running:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            async with self._lock:
                for node_id, node_info in self._robot_state.nodes.items():
                    # Check for stuck in BOOT/INIT
                    if node_info.state in (NodeState.BOOT, NodeState.INIT):
                        # Could implement timeout logic here
                        pass
                    
                    # Check for nodes that haven't sent heartbeat
                    # (would require tracking last seen timestamp)
    
    async def _compute_robot_state_loop(self) -> None:
        """Periodic robot state recomputation."""
        while self._running:
            await asyncio.sleep(10)
            async with self._lock:
                await self._recompute_robot_state()
    
    async def request_global_transition(self, target_state: RobotState, reason: str = "") -> bool:
        """Request global state transition (e.g., start all nodes)."""
        if target_state == RobotState.RUNNING:
            # Send start command to all READY nodes
            for node_id, node_info in self._robot_state.nodes.items():
                if node_info.state == NodeState.READY:
                    await self._send_node_command(node_id, "start", reason)
        elif target_state == RobotState.READY:
            # Send stop command to all RUNNING nodes
            for node_id, node_info in self._robot_state.nodes.items():
                if node_info.state == NodeState.RUNNING:
                    await self._send_node_command(node_id, "stop", reason)
        elif target_state == RobotState.SHUTDOWN:
            # Send shutdown to all nodes
            for node_id in self._robot_state.nodes:
                await self._send_node_command(node_id, "shutdown", reason)
        
        return True
    
    async def _send_node_command(self, node_id: str, command: str, reason: str) -> None:
        """Send command to specific node."""
        # Would send via MQTT to node's command topic
        await self.event_bus.publish(DomainEvent(
            event_type="NodeCommand",
            source_node="node1",
            payload={
                "node_id": node_id,
                "command": command,
                "reason": reason,
            },
        ))
    
    async def trigger_recovery(self, node_id: str) -> bool:
        """Trigger recovery for a node in ERROR state."""
        node_info = self._robot_state.nodes.get(node_id)
        if not node_info or node_info.state != NodeState.ERROR:
            return False
        
        await self._send_node_command(node_id, "recovery", "manual_recovery_triggered")
        return True
    
    async def trigger_emergency_stop(self, reason: str = "emergency_stop") -> bool:
        """Trigger emergency stop on all nodes."""
        logger.critical("EMERGENCY STOP TRIGGERED", reason=reason)
        
        for node_id in self._robot_state.nodes:
            await self._send_node_command(node_id, "emergency_stop", reason)
        
        return True
    
    def get_robot_state(self) -> RobotStateInfo:
        """Get current robot state."""
        return self._robot_state
    
    def get_node_state(self, node_id: str) -> Optional[NodeStateInfo]:
        """Get specific node state."""
        return self._robot_state.nodes.get(node_id)


async def get_state_machine_orchestrator(
    config: ConfigService,
    event_bus: EventBus,
    node_clients: dict,
) -> StateMachineOrchestrator:
    """Get state machine orchestrator instance."""
    orchestrator = StateMachineOrchestrator(config, event_bus, node_clients)
    await orchestrator.start()
    return orchestrator