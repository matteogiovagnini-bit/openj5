"""
OpenJ5 Robot Core - Main Entry Point

Orchestrates all core services:
- Configuration Service
- Logging Service
- Database
- Event Bus (Redis Streams)
- Health Service (monitoring + alerting)
- Plugin Manager
- OTA Manager
- Task Scheduler
- State Machine Orchestrator
- Digital Twin Bridge
- REST API + WebSocket
"""
import asyncio
import signal
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from robot_core.config import ConfigService, get_config_service
from robot_core.logging import setup_logging, get_logger
from robot_core.database import DatabaseManager
from robot_core.eventbus import DomainEvent, EventBus, get_event_bus
from robot_core.health import get_health_service
from robot_core.plugins import PluginManager
from robot_core.ota import OTAManager
from robot_core.scheduler import TaskScheduler
from robot_core.statemachine import StateMachineOrchestrator
from robot_core.digital_twin import DigitalTwinBridge
from robot_core.api import create_api_app


logger = get_logger(__name__)


class RobotCore:
    """Main Robot Core application orchestrating all services."""

    def __init__(self):
        self.config: ConfigService = None
        self.database: DatabaseManager = None
        self.event_bus: EventBus = None
        self.health_service = None
        self.plugin_manager: PluginManager = None
        self.ota_manager: OTAManager = None
        self.scheduler: TaskScheduler = None
        self.state_machine: StateMachineOrchestrator = None
        self.digital_twin: DigitalTwinBridge = None
        self.api_app: FastAPI = None
        self._shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def initialize(self) -> None:
        """Initialize all services in dependency order."""
        logger.info("Initializing OpenJ5 Robot Core...")

        # 1. Configuration Service (must be first)
        self.config = await get_config_service(Path("/config"))
        logger.info("Configuration service initialized")

        # 2. Logging Service
        setup_logging(self.config.get_section("logging"))
        logger.info("Logging service initialized")

        # 3. Database
        self.database = DatabaseManager(self.config)
        await self.database.initialize()
        logger.info("Database connected")

        # 4. Event Bus
        self.event_bus = await get_event_bus(self.config)
        logger.info("Event bus initialized")

        # 5. Health Service
        self.health_service = await get_health_service(
            config=self.config,
            database=self.database,
            event_bus=self.event_bus,
        )
        logger.info("Health service initialized")

        # 6. Plugin Manager
        self.plugin_manager = PluginManager(
            config=self.config,
            event_bus=self.event_bus,
            database=self.database,
        )
        await self.plugin_manager.initialize()
        logger.info("Plugin manager initialized")

        # 7. OTA Manager
        self.ota_manager = OTAManager(
            config=self.config,
            event_bus=self.event_bus,
            database=self.database,
        )
        await self.ota_manager.initialize()
        logger.info("OTA manager started")

        # 8. Task Scheduler
        self.scheduler = TaskScheduler(
            config=self.config,
            database=self.database,
        )
        await self.scheduler.start()
        logger.info("Task scheduler started")

        # 9. State Machine Orchestrator
        self.state_machine = StateMachineOrchestrator(
            config=self.config,
            event_bus=self.event_bus,
            database=self.database,
        )
        await self.state_machine.start()
        logger.info("State machine orchestrator started")

        # 10. Digital Twin Bridge
        self.digital_twin = DigitalTwinBridge(
            config=self.config,
            event_bus=self.event_bus,
            database=self.database,
        )
        await self.digital_twin.connect()
        logger.info("Digital twin bridge connected")

        # 11. REST API + WebSocket
        self.api_app = create_api_app(
            config=self.config,
            event_bus=self.event_bus,
            plugin_manager=self.plugin_manager,
            ota_manager=self.ota_manager,
            scheduler=self.scheduler,
            state_machine=self.state_machine,
            digital_twin=self.digital_twin,
            health_service=self.health_service,
        )
        logger.info("API application created")

        # 12. Load and start plugins
        await self.plugin_manager.load_all_plugins()
        await self.plugin_manager.start_all_plugins()
        logger.info("All plugins loaded and started")

        logger.info("OpenJ5 Robot Core initialization complete")

    async def start(self) -> None:
        """Start all services."""
        logger.info("Starting OpenJ5 Robot Core services...")

        api_config = self.config.get_section("api")
        self._tasks.append(asyncio.create_task(
            self._run_api_server(
                host=api_config.get("host", "0.0.0.0"),
                port=api_config.get("port", 8080),
            )
        ))
        self._tasks.append(asyncio.create_task(self._health_check_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))

        logger.info("OpenJ5 Robot Core started")

    async def _run_api_server(self, host: str, port: int) -> None:
        """Run FastAPI server."""
        server = uvicorn.Server(uvicorn.Config(
            app=self.api_app,
            host=host,
            port=port,
            ssl_keyfile="/certs/api.key" if self.config.get("api.tls") else None,
            ssl_certfile="/certs/api.crt" if self.config.get("api.tls") else None,
            log_config=None,
            access_log=False,
        ))
        await server.serve()

    async def _health_check_loop(self) -> None:
        """Periodic health checks."""
        interval = self.config.get("health.check_interval", 30)
        while not self._shutdown_event.is_set():
            try:
                await self.health_service.check_all()
            except Exception as e:
                logger.error(f"Health check failed: {e}")
            await asyncio.sleep(interval)

    async def _metrics_loop(self) -> None:
        """Periodic metrics collection."""
        interval = self.config.get("metrics.interval", 60)
        while not self._shutdown_event.is_set():
            try:
                psutil = __import__("psutil")
                await self.event_bus.publish(DomainEvent(
                    event_type="system.metrics",
                    source_node="node1",
                    payload={
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_percent": psutil.disk_usage("/").percent,
                    },
                ))
            except Exception as e:
                logger.error(f"Metrics collection failed: {e}")
            await asyncio.sleep(interval)

    async def shutdown(self) -> None:
        """Graceful shutdown of all services."""
        logger.info("Shutting down OpenJ5 Robot Core...")
        self._shutdown_event.set()

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self.digital_twin:
            await self.digital_twin.disconnect()
        if self.state_machine:
            await self.state_machine.stop()
        if self.scheduler:
            await self.scheduler.stop()
        if self.ota_manager:
            await self.ota_manager.shutdown()
        if self.plugin_manager:
            await self.plugin_manager.shutdown()
        if self.health_service:
            await self.health_service.stop()
        if self.event_bus:
            await self.event_bus.disconnect()
        if self.database:
            await self.database.close()

        logger.info("OpenJ5 Robot Core shutdown complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler."""
    core = RobotCore()
    await core.initialize()
    await core.start()
    app.state.robot_core = core
    yield
    await core.shutdown()


async def main() -> None:
    """Main entry point."""
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    core = RobotCore()
    await core.initialize()
    await core.start()
    await shutdown_event.wait()
    await core.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass