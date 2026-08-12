"""
OpenJ5 Robot Core - Task Scheduler

APScheduler-based task scheduler for recurring jobs.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable, Optional
from enum import Enum

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from robot_core.config import ConfigService
from robot_core.logging import get_logger

logger = get_logger(__name__)


class JobType(Enum):
    INTERVAL = "interval"
    CRON = "cron"
    DATE = "date"


@dataclass
class ScheduledJob:
    """Scheduled job definition."""
    id: str
    name: str
    func: str  # function path: "module:function"
    trigger: JobType
    trigger_args: dict
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    max_instances: int = 1
    coalesce: bool = True
    misfire_grace_time: int = 300
    enabled: bool = True


class TaskScheduler:
    """
    Task scheduler for recurring maintenance jobs.
    
    Jobs defined in config:
    - health_check_all_nodes: every 30s
    - db_cleanup: daily at 3am
    - firmware_check: every 6h
    - metrics_collection: every 60s
    - config_reload_check: every 10s
    """
    
    def __init__(self, config: ConfigService, database=None):
        self.config = config
        self.database = database
        self.scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            },
            timezone="UTC",
        )
        self._jobs: dict[str, ScheduledJob] = {}
        self._function_registry: dict[str, Callable] = {}
        self._running = False
    
    def register_function(self, name: str, func: Callable) -> None:
        """Register callable function by name."""
        self._function_registry[name] = func
    
    async def start(self) -> None:
        """Start scheduler and load jobs from config."""
        if self._running:
            return
        
        # Register built-in functions
        self._register_builtin_functions()
        
        # Load jobs from config
        await self._load_jobs()
        
        self.scheduler.start()
        self._running = True
        logger.info("Task scheduler started", jobs=len(self._jobs))
    
    async def stop(self) -> None:
        """Stop scheduler."""
        if not self._running:
            return
        
        self.scheduler.shutdown(wait=True)
        self._running = False
        logger.info("Task scheduler stopped")
    
    def _register_builtin_functions(self) -> None:
        """Register built-in scheduler functions."""
        # These would be imported from respective services
        self.register_function("health_check_all_nodes", self._health_check_all_nodes)
        self.register_function("db_cleanup", self._db_cleanup)
        self.register_function("firmware_check", self._firmware_check)
        self.register_function("metrics_collection", self._metrics_collection)
        self.register_function("config_reload_check", self._config_reload_check)
        self.register_function("backup_database", self._backup_database)
        self.register_function("rotate_logs", self._rotate_logs)
        self.register_function("check_node_connectivity", self._check_node_connectivity)
    
    async def _load_jobs(self) -> None:
        """Load jobs from configuration."""
        jobs_config = self.config.get_section("scheduler.jobs")
        
        for job_config in jobs_config:
            if not job_config.get("enabled", True):
                continue
            
            job = ScheduledJob(
                id=job_config["id"],
                name=job_config.get("name", job_config["id"]),
                func=job_config["func"],
                trigger=JobType(job_config["trigger"]),
                trigger_args=job_config.get("trigger_args", {}),
                args=job_config.get("args", []),
                kwargs=job_config.get("kwargs", {}),
                max_instances=job_config.get("max_instances", 1),
                coalesce=job_config.get("coalesce", True),
                misfire_grace_time=job_config.get("misfire_grace_time", 300),
            )
            
            await self.add_job(job)
    
    async def add_job(self, job: ScheduledJob) -> bool:
        """Add scheduled job."""
        if job.id in self._jobs:
            await self.remove_job(job.id)
        
        # Get function
        func = self._function_registry.get(job.func)
        if not func:
            logger.error("Function not registered", job_id=job.id, func=job.func)
            return False
        
        # Create trigger
        if job.trigger == JobType.INTERVAL:
            trigger = IntervalTrigger(**job.trigger_args)
        elif job.trigger == JobType.CRON:
            trigger = CronTrigger(**job.trigger_args)
        else:
            logger.error("Unsupported trigger type", job_id=job.id, trigger=job.trigger)
            return False
        
        # Add to scheduler
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job.id,
            name=job.name,
            args=job.args,
            kwargs=job.kwargs,
            max_instances=job.max_instances,
            coalesce=job.coalesce,
            misfire_grace_time=job.misfire_grace_time,
        )
        
        self._jobs[job.id] = job
        logger.info("Job added", job_id=job.id, trigger=job.trigger.value)
        return True
    
    async def remove_job(self, job_id: str) -> bool:
        """Remove scheduled job."""
        try:
            self.scheduler.remove_job(job_id)
            self._jobs.pop(job_id, None)
            logger.info("Job removed", job_id=job_id)
            return True
        except Exception as e:
            logger.error("Failed to remove job", job_id=job_id, error=str(e))
            return False
    
    async def pause_job(self, job_id: str) -> bool:
        """Pause scheduled job."""
        try:
            self.scheduler.pause_job(job_id)
            if job_id in self._jobs:
                self._jobs[job_id].enabled = False
            return True
        except Exception as e:
            logger.error("Failed to pause job", job_id=job_id, error=str(e))
            return False
    
    async def resume_job(self, job_id: str) -> bool:
        """Resume scheduled job."""
        try:
            self.scheduler.resume_job(job_id)
            if job_id in self._jobs:
                self._jobs[job_id].enabled = True
            return True
        except Exception as e:
            logger.error("Failed to resume job", job_id=job_id, error=str(e))
            return False
    
    def get_jobs(self) -> list[ScheduledJob]:
        """Get all scheduled jobs."""
        return list(self._jobs.values())
    
    def get_job_status(self, job_id: str) -> dict:
        """Get job status."""
        job = self.scheduler.get_job(job_id)
        if not job:
            return {"exists": False}
        
        return {
            "exists": True,
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "pending": job.pending,
        }
    
    # === Built-in Job Functions ===
    
    async def _health_check_all_nodes(self) -> None:
        """Health check all robot nodes."""
        logger.info("Running health check on all nodes")
        # Implementation would call node health check via MQTT
    
    async def _db_cleanup(self) -> None:
        """Cleanup old telemetry data."""
        logger.info("Running database cleanup")
        # Implementation would delete old records
    
    async def _firmware_check(self) -> None:
        """Check for new firmware versions."""
        logger.info("Checking for firmware updates")
        # Implementation would check firmware registry
    
    async def _metrics_collection(self) -> None:
        """Collect and publish system metrics."""
        import psutil
        metrics = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "timestamp": datetime.now().isoformat(),
        }
        logger.debug("Metrics collected", **metrics)
    
    async def _config_reload_check(self) -> None:
        """Check if config files have changed."""
        # Implementation would check file mtimes
        pass
    
    async def _backup_database(self) -> None:
        """Backup database."""
        logger.info("Running database backup")
    
    async def _rotate_logs(self) -> None:
        """Rotate log files."""
        logger.info("Rotating logs")
    
    async def _check_node_connectivity(self) -> None:
        """Check connectivity to all nodes."""
        logger.info("Checking node connectivity")


async def get_scheduler(config: ConfigService, database=None) -> TaskScheduler:
    """Get scheduler instance."""
    scheduler = TaskScheduler(config, database)
    await scheduler.start()
    return scheduler