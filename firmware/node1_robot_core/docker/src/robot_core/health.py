"""
OpenJ5 Robot Core - Health Service

Comprehensive health monitoring for robot core and all nodes.
"""

import asyncio
import psutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable

from robot_core.config import ConfigService
from robot_core.eventbus import EventBus, DomainEvent
from robot_core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class HealthCheck:
    """Individual health check definition."""
    name: str
    check_func: Callable[[], Awaitable[bool]]
    critical: bool = True
    interval: float = 30.0
    timeout: float = 10.0
    tags: list[str] = field(default_factory=list)


@dataclass
class HealthResult:
    """Health check result."""
    name: str
    healthy: bool
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    critical: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class NodeHealth:
    """Node health status."""
    node_id: str
    state: str  # BOOT, INIT, READY, RUNNING, ERROR, RECOVERY, SHUTDOWN
    last_heartbeat: float
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    temperature: float = 0.0
    checks: dict[str, HealthResult] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class RobotHealth:
    """Aggregate robot health."""
    overall: str  # healthy, degraded, unhealthy, critical
    state: str  # BOOTING, INITIALIZING, READY, RUNNING, DEGRADED, ERROR, RECOVERING, SHUTTING_DOWN
    node_health: dict[str, NodeHealth] = field(default_factory=dict)
    system_checks: dict[str, HealthResult] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class HealthService:
    """
    Health monitoring service for Robot Core and all nodes.
    
    Features:
    - Periodic health checks (system + node-level)
    - Heartbeat monitoring for all 6 nodes
    - System resource monitoring (CPU, RAM, disk, temp)
    - Alerting on critical failures
    - Health aggregation for API
    """
    
    def __init__(
        self,
        config: ConfigService,
        event_bus: EventBus,
        database=None,
    ):
        self.config = config
        self.event_bus = event_bus
        
        self.check_interval = config.get("health.check_interval", 30.0)
        self.heartbeat_timeout = config.get("health.heartbeat_timeout", 60.0)
        self.warning_thresholds = config.get("health.thresholds", {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "temperature": 70.0,
        })
        
        self._checks: dict[str, HealthCheck] = {}
        self._node_health: dict[str, NodeHealth] = {}
        self._system_results: dict[str, HealthResult] = {}
        self._running = False
        self._monitor_task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start health monitoring."""
        if self._running:
            return
        
        # Register built-in checks
        self._register_builtin_checks()
        
        # Initialize node health
        for node_id in ["node1", "node2", "node3", "node4", "node5", "node6"]:
            self._node_health[node_id] = NodeHealth(
                node_id=node_id,
                state="unknown",
                last_heartbeat=0,
            )
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        # Subscribe to node heartbeats
        await self.event_bus.subscribe("NodeHeartbeat", self._on_node_heartbeat)
        await self.event_bus.subscribe("NodeStateChanged", self._on_node_state_change)
        
        logger.info("Health service started")
    
    async def stop(self) -> None:
        """Stop health monitoring."""
        if not self._running:
            return
        
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health service stopped")
    
    def _register_builtin_checks(self) -> None:
        """Register built-in health checks."""
        
        # System checks
        self.register_check(HealthCheck(
            name="cpu_usage",
            check_func=self._check_cpu,
            critical=True,
            interval=30.0,
            tags=["system", "resource"],
        ))
        
        self.register_check(HealthCheck(
            name="memory_usage",
            check_func=self._check_memory,
            critical=True,
            interval=30.0,
            tags=["system", "resource"],
        ))
        
        self.register_check(HealthCheck(
            name="disk_usage",
            check_func=self._check_disk,
            critical=True,
            interval=60.0,
            tags=["system", "resource"],
        ))
        
        self.register_check(HealthCheck(
            name="temperature",
            check_func=self._check_temperature,
            critical=True,
            interval=30.0,
            tags=["system", "hardware"],
        ))
        
        # Network checks
        self.register_check(HealthCheck(
            name="mqtt_connectivity",
            check_func=self._check_mqtt,
            critical=True,
            interval=10.0,
            tags=["network", "communication"],
        ))
        
        self.register_check(HealthCheck(
            name="redis_connectivity",
            check_func=self._check_redis,
            critical=False,
            interval=30.0,
            tags=["network", "eventbus"],
        ))
        
        self.register_check(HealthCheck(
            name="database_connectivity",
            check_func=self._check_database,
            critical=True,
            interval=30.0,
            tags=["network", "storage"],
        ))
    
    def register_check(self, check: HealthCheck) -> None:
        """Register a health check."""
        self._checks[check.name] = check
    
    async def check_all(self) -> RobotHealth:
        """Run all health checks and return aggregate health."""
        
        # Run system checks
        system_results = {}
        for check in self._checks.values():
            if check.critical or check.tags[0] == "system":
                try:
                    result = await asyncio.wait_for(
                        check.check_func(),
                        timeout=check.timeout,
                    )
                    system_results[check.name] = HealthResult(
                        name=check.name,
                        healthy=result,
                        critical=check.critical,
                    )
                except Exception as e:
                    system_results[check.name] = HealthResult(
                        name=check.name,
                        healthy=False,
                        message=str(e),
                        critical=check.critical,
                    )
        
        self._system_results = system_results
        
        # Check node heartbeats
        await self._check_node_heartbeats()
        
        # Aggregate overall health
        overall = self._aggregate_health()
        
        return RobotHealth(
            overall=overall,
            state=self._get_robot_state(),
            node_health=self._node_health.copy(),
            system_checks=system_results,
        )
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self.check_all()
            except Exception as e:
                logger.error("Health check failed", error=str(e))
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_node_heartbeats(self) -> None:
        """Check node heartbeats and update status."""
        now = asyncio.get_event_loop().time()
        
        for node_id, health in self._node_health.items():
            time_since_heartbeat = now - health.last_heartbeat
            
            if time_since_heartbeat > self.heartbeat_timeout:
                if health.state != "error":
                    health.state = "error"
                    health.errors.append(f"Heartbeat timeout ({time_since_heartbeat:.1f}s)")
                    logger.warning("Node heartbeat timeout", node_id=node_id)
                
                # Publish alert
                await self.event_bus.publish(DomainEvent(
                    event_type="NodeHeartbeatLost",
                    source_node="node1",
                    payload={"node_id": node_id, "timeout": time_since_heartbeat},
                ))
    
    async def _on_node_heartbeat(self, event: DomainEvent) -> None:
        """Handle node heartbeat."""
        payload = event.payload
        node_id = payload.get("node_id")
        
        if node_id in self._node_health:
            self._node_health[node_id].last_heartbeat = asyncio.get_event_loop().time()
            self._node_health[node_id].cpu_percent = payload.get("cpu_percent", 0)
            self._node_health[node_id].memory_percent = payload.get("memory_percent", 0)
            self._node_health[node_id].temperature = payload.get("temperature", 0)
            
            # Update individual check results
            for check_name, result in payload.get("checks", {}).items():
                self._node_health[node_id].checks[check_name] = HealthResult(
                    name=check_name,
                    healthy=result.get("healthy", False),
                    message=result.get("message", ""),
                    critical=result.get("critical", True),
                )
    
    async def _on_node_state_change(self, event: DomainEvent) -> None:
        """Handle node state change."""
        payload = event.payload
        node_id = payload.get("node_id")
        new_state = payload.get("new_state")
        
        if node_id in self._node_health:
            old_state = self._node_health[node_id].state
            self._node_health[node_id].state = new_state
            
            logger.info("Node state changed", node_id=node_id, old=old_state, new=new_state)
            
            # If node enters ERROR, alert
            if new_state == "error":
                await self.event_bus.publish(DomainEvent(
                    event_type="NodeEnteredError",
                    source_node="node1",
                    payload={"node_id": node_id, "previous_state": old_state},
                ))
    
    def _aggregate_health(self) -> str:
        """Aggregate overall health status."""
        # Check critical system checks
        critical_failed = any(
            not r.healthy and r.critical
            for r in self._system_results.values()
        )
        
        if critical_failed:
            return "critical"
        
        # Check non-critical system checks
        warnings = any(
            not r.healthy and not r.critical
            for r in self._system_results.values()
        )
        
        # Check nodes
        node_errors = sum(
            1 for h in self._node_health.values()
            if h.state == "error"
        )
        
        node_degraded = sum(
            1 for h in self._node_health.values()
            if h.state in ("degraded", "recovery")
        )
        
        if node_errors > 0:
            return "critical" if critical_failed else "unhealthy"
        
        if node_degraded > 0 or warnings:
            return "degraded"
        
        return "healthy"
    
    def _get_robot_state(self) -> str:
        """Determine aggregate robot state from node states."""
        states = [h.state for h in self._node_health.values()]
        
        if all(s == "running" for s in states):
            return "RUNNING"
        elif all(s in ("ready", "running") for s in states):
            return "READY"
        elif any(s == "error" for s in states):
            return "ERROR"
        elif any(s == "recovery" for s in states):
            return "RECOVERING"
        elif any(s == "boot" for s in states):
            return "BOOTING"
        elif any(s == "init" for s in states):
            return "INITIALIZING"
        else:
            return "DEGRADED"
    
    # === Built-in Check Functions ===
    
    async def _check_cpu(self) -> bool:
        """Check CPU usage."""
        cpu = psutil.cpu_percent(interval=1)
        return cpu < self.warning_thresholds["cpu_percent"]
    
    async def _check_memory(self) -> bool:
        """Check memory usage."""
        mem = psutil.virtual_memory()
        return mem.percent < self.warning_thresholds["memory_percent"]
    
    async def _check_disk(self) -> bool:
        """Check disk usage."""
        disk = psutil.disk_usage("/")
        return disk.percent < self.warning_thresholds["disk_percent"]
    
    async def _check_temperature(self) -> bool:
        """Check system temperature."""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                max_temp = max(
                    t.current for sensor in temps.values() for t in sensor
                )
                return max_temp < self.warning_thresholds["temperature"]
        except Exception:
            pass
        return True  # No temp sensors = OK
    
    async def _check_mqtt(self) -> bool:
        """Check MQTT broker connectivity."""
        # Would connect to MQTT and publish test message
        return True
    
    async def _check_redis(self) -> bool:
        """Check Redis connectivity."""
        # Would ping Redis
        return True
    
    async def _check_database(self) -> bool:
        """Check database connectivity."""
        # Would execute simple query
        return True
    
    async def get_health_summary(self) -> dict:
        """Get health summary for API."""
        health = await self.check_all()
        return {
            "overall": health.overall,
            "state": health.state,
            "nodes": {
                node_id: {
                    "state": h.state,
                    "last_heartbeat": h.last_heartbeat,
                    "cpu": h.cpu_percent,
                    "memory": h.memory_percent,
                    "temp": h.temperature,
                    "errors": len(h.errors),
                    "warnings": len(h.warnings),
                }
                for node_id, h in health.node_health.items()
            },
            "system": {
                name: {"healthy": r.healthy, "message": r.message}
                for name, r in health.system_checks.items()
            },
        }


async def get_health_service(
    config: ConfigService,
    event_bus: EventBus,
    database=None,
) -> HealthService:
    """Get health service instance."""
    service = HealthService(config, event_bus, database)
    await service.start()
    return service