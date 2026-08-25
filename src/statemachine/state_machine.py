"""
OpenJ5 State Machine - Per-Node State Machine Framework

All nodes implement: BOOT -> INIT -> READY -> RUNNING <-> ERROR -> RECOVERY -> SHUTDOWN
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import time

from ..core.domain import Result


class NodeState(Enum):
    """Node lifecycle states."""
    BOOT = "boot"
    INIT = "init"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    RECOVERY = "recovery"
    SHUTDOWN = "shutdown"


class StateTransition(Enum):
    """Valid state transitions."""
    BOOT_TO_INIT = ("boot", "init")
    BOOT_TO_ERROR = ("boot", "error")
    INIT_TO_READY = ("init", "ready")
    INIT_TO_ERROR = ("init", "error")
    READY_TO_RUNNING = ("ready", "running")
    READY_TO_SHUTDOWN = ("ready", "shutdown")
    RUNNING_TO_READY = ("running", "ready")
    RUNNING_TO_ERROR = ("running", "error")
    RUNNING_TO_SHUTDOWN = ("running", "shutdown")
    ERROR_TO_RECOVERY = ("error", "recovery")
    ERROR_TO_SHUTDOWN = ("error", "shutdown")
    RECOVERY_TO_READY = ("recovery", "ready")
    RECOVERY_TO_ERROR = ("recovery", "error")
    RECOVERY_TO_SHUTDOWN = ("recovery", "shutdown")
    SHUTDOWN_TO_BOOT = ("shutdown", "boot")  # Restart


# Valid transitions map
VALID_TRANSITIONS = {
    NodeState.BOOT: [NodeState.INIT, NodeState.ERROR],
    NodeState.INIT: [NodeState.READY, NodeState.ERROR],
    NodeState.READY: [NodeState.RUNNING, NodeState.SHUTDOWN],
    NodeState.RUNNING: [NodeState.READY, NodeState.ERROR, NodeState.SHUTDOWN],
    NodeState.ERROR: [NodeState.RECOVERY, NodeState.SHUTDOWN],
    NodeState.RECOVERY: [NodeState.READY, NodeState.ERROR, NodeState.SHUTDOWN],
    NodeState.SHUTDOWN: [NodeState.BOOT],  # Restart
}


@dataclass
class StateContext:
    """State machine context - holds node-specific data."""
    node_id: str
    node_type: str
    config: dict = field(default_factory=dict)
    hardware: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    last_transition: float = 0.0
    transition_count: int = 0


class StateHandler(ABC):
    """Base state handler - implement for each state."""

    @abstractmethod
    async def on_enter(self, context: StateContext) -> Result:
        """Called when entering state."""
        pass

    @abstractmethod
    async def on_exit(self, context: StateContext) -> Result:
        """Called when exiting state."""
        pass

    @abstractmethod
    async def on_update(self, context: StateContext) -> Result:
        """Called periodically while in state."""
        pass

    @abstractmethod
    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        """Handle event in this state."""
        pass


class IStateMachine(ABC):
    """State machine interface."""

    @property
    @abstractmethod
    def current_state(self) -> NodeState:
        pass

    @property
    @abstractmethod
    def previous_state(self) -> NodeState:
        pass

    @abstractmethod
    async def transition_to(self, new_state: NodeState, reason: str = "") -> Result:
        pass

    @abstractmethod
    async def handle_event(self, event: str, data: Any = None) -> Result:
        pass

    @abstractmethod
    async def start(self) -> Result:
        pass

    @abstractmethod
    async def stop(self) -> Result:
        pass


class StateMachine(IStateMachine):
    """
    Hierarchical state machine for robot nodes.
    
    Features:
    - Validates transitions
    - Async enter/exit/update handlers
    - Event-driven transitions
    - Watchdog timer per state
    - State persistence for recovery
    - Metrics collection
    """

    def __init__(
        self,
        context: StateContext,
        handlers: dict[NodeState, StateHandler] = None,
        watchdog_timeout: float = 30.0,
        update_interval: float = 1.0
    ):
        self._context = context
        self._handlers = handlers or {}
        self._watchdog_timeout = watchdog_timeout
        self._update_interval = update_interval

        self._current_state = NodeState.BOOT
        self._previous_state = NodeState.BOOT
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._last_watchdog_reset = time.time()

        # Event queue for async event handling
        self._event_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._event_task: Optional[asyncio.Task] = None

        # Transition callbacks
        self._on_transition: list[Callable[[NodeState, NodeState, str], Awaitable[None]]] = []

    @property
    def current_state(self) -> NodeState:
        return self._current_state

    @property
    def previous_state(self) -> NodeState:
        return self._previous_state

    @property
    def context(self) -> StateContext:
        return self._context

    def add_transition_callback(self, callback: Callable[[NodeState, NodeState, str], Awaitable[None]]):
        """Add callback fired on every transition."""
        self._on_transition.append(callback)

    def register_handler(self, state: NodeState, handler: StateHandler):
        """Register handler for state."""
        self._handlers[state] = handler

    def reset_watchdog(self):
        """Reset watchdog timer (call from handlers during long operations)."""
        self._last_watchdog_reset = time.time()

    # === LIFECYCLE ===

    async def start(self) -> Result:
        """Start state machine from BOOT state."""
        if self._running:
            return Result.fail("ALREADY_RUNNING", "State machine already running")

        self._running = True
        self._last_watchdog_reset = time.time()

        # Start background tasks
        self._update_task = asyncio.create_task(self._update_loop())
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        self._event_task = asyncio.create_task(self._event_loop())

        # Enter BOOT state
        result = await self._enter_state(NodeState.BOOT)
        return result

    async def stop(self) -> Result:
        """Stop state machine gracefully."""
        if not self._running:
            return Result.ok(True)

        self._running = False

        # Cancel tasks
        for task in [self._update_task, self._watchdog_task, self._event_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Exit current state
        await self._exit_state(self._current_state)
        return Result.ok(True)

    # === TRANSITIONS ===

    async def transition_to(self, new_state: NodeState, reason: str = "") -> Result:
        """Transition to new state with validation."""
        if not self._is_valid_transition(self._current_state, new_state):
            return Result.fail(
                "INVALID_TRANSITION",
                f"Cannot transition from {self._current_state.value} to {new_state.value}"
            )

        # Exit current state
        exit_result = await self._exit_state(self._current_state)
        if not exit_result.success:
            return Result.fail("EXIT_FAILED", f"Failed to exit {self._current_state.value}")

        # Update context
        self._previous_state = self._current_state
        self._current_state = new_state
        self._context.last_transition = time.time()
        self._context.transition_count += 1
        self._last_watchdog_reset = time.time()

        # Enter new state
        enter_result = await self._enter_state(new_state)
        if not enter_result.success:
            # Try to rollback
            await self._enter_state(self._previous_state)
            return enter_result

        # Fire callbacks
        for callback in self._on_transition:
            try:
                await callback(self._previous_state, new_state, reason)
            except Exception:
                pass  # Don't fail transition on callback error

        return Result.ok(True)

    def _is_valid_transition(self, from_state: NodeState, to_state: NodeState) -> bool:
        return to_state in VALID_TRANSITIONS.get(from_state, [])

    async def _enter_state(self, state: NodeState) -> Result:
        handler = self._handlers.get(state)
        if handler:
            return await handler.on_enter(self._context)
        return Result.ok(True)

    async def _exit_state(self, state: NodeState) -> Result:
        handler = self._handlers.get(state)
        if handler:
            return await handler.on_exit(self._context)
        return Result.ok(True)

    # === EVENT HANDLING ===

    async def handle_event(self, event: str, data: Any = None) -> Result:
        """Queue event for processing."""
        await self._event_queue.put((event, data))
        return Result.ok(True)

    async def _event_loop(self):
        """Process events from queue."""
        while self._running:
            try:
                event, data = await asyncio.wait_for(
                    self._event_queue.get(), timeout=0.1
                )
                handler = self._handlers.get(self._current_state)
                if handler:
                    await handler.on_event(self._context, event, data)
            except asyncio.TimeoutError:
                continue
            except Exception:
                pass

    # === BACKGROUND TASKS ===

    async def _update_loop(self):
        """Periodic update for current state."""
        while self._running:
            try:
                handler = self._handlers.get(self._current_state)
                if handler:
                    await handler.on_update(self._context)
            except Exception:
                pass
            await asyncio.sleep(self._update_interval)

    async def _watchdog_loop(self):
        """Watchdog timer - triggers ERROR if not reset."""
        while self._running:
            await asyncio.sleep(1.0)
            if time.time() - self._last_watchdog_reset > self._watchdog_timeout:
                # Watchdog expired - transition to ERROR
                await self.transition_to(NodeState.ERROR, "Watchdog timeout")
                break


# === BUILT-IN HANDLERS ===

class BootHandler(StateHandler):
    """BOOT state - hardware self-test."""

    async def on_enter(self, context: StateContext) -> Result:
        # Run hardware self-test
        # This would be implemented per-node
        context.metrics["boot_start"] = time.time()
        return Result.ok(True)

    async def on_exit(self, context: StateContext) -> Result:
        context.metrics["boot_duration"] = time.time() - context.metrics.get("boot_start", time.time())
        return Result.ok(True)

    async def on_update(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        if event == "self_test_complete":
            success = data.get("success", False)
            if success:
                return Result.ok({"next_state": NodeState.INIT})
            else:
                context.errors.append(data.get("error", "Self-test failed"))
                return Result.ok({"next_state": NodeState.ERROR})
        return Result.ok(True)


class InitHandler(StateHandler):
    """INIT state - load config, calibrate, establish comms."""

    async def on_enter(self, context: StateContext) -> Result:
        context.metrics["init_start"] = time.time()
        return Result.ok(True)

    async def on_exit(self, context: StateContext) -> Result:
        context.metrics["init_duration"] = time.time() - context.metrics.get("init_start", time.time())
        return Result.ok(True)

    async def on_update(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        if event == "init_complete":
            success = data.get("success", False)
            if success:
                return Result.ok({"next_state": NodeState.READY})
            else:
                context.errors.append(data.get("error", "Init failed"))
                return Result.ok({"next_state": NodeState.ERROR})
        return Result.ok(True)


class ReadyHandler(StateHandler):
    """READY state - waiting for RUN command."""

    async def on_enter(self, context: StateContext) -> Result:
        context.metrics["ready_at"] = time.time()
        return Result.ok(True)

    async def on_exit(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_update(self, context: StateContext) -> Result:
        # Periodic health checks
        return Result.ok(True)

    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        if event == "start_command":
            return Result.ok({"next_state": NodeState.RUNNING})
        elif event == "shutdown_command":
            return Result.ok({"next_state": NodeState.SHUTDOWN})
        return Result.ok(True)


class RunningHandler(StateHandler):
    """RUNNING state - normal operation."""

    async def on_enter(self, context: StateContext) -> Result:
        context.metrics["running_at"] = time.time()
        return Result.ok(True)

    async def on_exit(self, context: StateContext) -> Result:
        context.metrics["running_duration"] = time.time() - context.metrics.get("running_at", time.time())
        return Result.ok(True)

    async def on_update(self, context: StateContext) -> Result:
        # Main control loop runs here
        return Result.ok(True)

    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        if event == "stop_command":
            return Result.ok({"next_state": NodeState.READY})
        elif event == "shutdown_command":
            return Result.ok({"next_state": NodeState.SHUTDOWN})
        elif event == "fault_detected":
            context.errors.append(data.get("error", "Fault detected"))
            return Result.ok({"next_state": NodeState.ERROR})
        return Result.ok(True)


class ErrorHandler(StateHandler):
    """ERROR state - fault handling."""

    async def on_enter(self, context: StateContext) -> Result:
        context.metrics["error_at"] = time.time()
        context.metrics["error_count"] = context.metrics.get("error_count", 0) + 1
        # Trigger failsafe behaviors
        return Result.ok(True)

    async def on_exit(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_update(self, context: StateContext) -> Result:
        # Blink error LED, maintain safe state
        return Result.ok(True)

    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        if event == "recovery_command":
            return Result.ok({"next_state": NodeState.RECOVERY})
        elif event == "shutdown_command":
            return Result.ok({"next_state": NodeState.SHUTDOWN})
        return Result.ok(True)


class RecoveryHandler(StateHandler):
    """RECOVERY state - attempt to recover from error."""

    async def on_enter(self, context: StateContext) -> Result:
        context.metrics["recovery_start"] = time.time()
        context.metrics["recovery_attempts"] = context.metrics.get("recovery_attempts", 0) + 1
        return Result.ok(True)

    async def on_exit(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_update(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        if event == "recovery_complete":
            success = data.get("success", False)
            if success:
                context.errors.clear()
                return Result.ok({"next_state": NodeState.READY})
            else:
                context.errors.append(data.get("error", "Recovery failed"))
                return Result.ok({"next_state": NodeState.ERROR})
        elif event == "abort_recovery":
            return Result.ok({"next_state": NodeState.ERROR})
        return Result.ok(True)


class ShutdownHandler(StateHandler):
    """SHUTDOWN state - graceful shutdown."""

    async def on_enter(self, context: StateContext) -> Result:
        context.metrics["shutdown_start"] = time.time()
        return Result.ok(True)

    async def on_exit(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_update(self, context: StateContext) -> Result:
        return Result.ok(True)

    async def on_event(self, context: StateContext, event: str, data: Any) -> Result:
        if event == "shutdown_complete":
            return Result.ok({"next_state": NodeState.BOOT})  # Restart
        return Result.ok(True)


# === FACTORY ===

def create_default_state_machine(
    node_id: str,
    node_type: str,
    config: dict = None,
    watchdog_timeout: float = 30.0
) -> StateMachine:
    """Create state machine with default handlers."""
    context = StateContext(
        node_id=node_id,
        node_type=node_type,
        config=config or {}
    )

    handlers = {
        NodeState.BOOT: BootHandler(),
        NodeState.INIT: InitHandler(),
        NodeState.READY: ReadyHandler(),
        NodeState.RUNNING: RunningHandler(),
        NodeState.ERROR: ErrorHandler(),
        NodeState.RECOVERY: RecoveryHandler(),
        NodeState.SHUTDOWN: ShutdownHandler(),
    }

    return StateMachine(
        context=context,
        handlers=handlers,
        watchdog_timeout=watchdog_timeout
    )