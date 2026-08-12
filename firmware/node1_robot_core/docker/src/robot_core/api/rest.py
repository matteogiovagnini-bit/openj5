"""
OpenJ5 Robot Core - REST API Router
"""

import uuid
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from robot_core.config import ConfigService
from robot_core.eventbus import EventBus, DomainEvent
from robot_core.plugins import PluginManager
from robot_core.ota import OTAManager
from robot_core.scheduler import TaskScheduler, ScheduledJob, JobType
from robot_core.statemachine import StateMachineOrchestrator, RobotState, NODE_TRANSITIONS
from robot_core.digital_twin import DigitalTwinBridge
from robot_core.health import HealthService
from robot_core.api.models import *


def create_rest_api(
    config: ConfigService,
    event_bus: EventBus,
    plugin_manager: PluginManager,
    ota_manager: OTAManager,
    scheduler: TaskScheduler,
    state_machine: StateMachineOrchestrator,
    digital_twin: DigitalTwinBridge,
    health_service: HealthService,
) -> APIRouter:

    router = APIRouter()

    # ============================================================
    # Robot Control
    # ============================================================

    @router.post("/robot/command", response_model=CommandResponse)
    async def send_command(cmd: RobotCommand):
        if not cmd.command_id:
            cmd.command_id = str(uuid.uuid4())
        target = cmd.target_node if cmd.target_node != "robot" else "all"
        await event_bus.publish(DomainEvent(
            event_type="RobotCommand",
            source_node="api",
            payload={
                "command_id": cmd.command_id,
                "target": target,
                "command_type": cmd.command_type,
                "parameters": cmd.parameters,
                "timeout": cmd.timeout,
                "timestamp": datetime.now().isoformat(),
            },
        ))
        return CommandResponse(
            command_id=cmd.command_id,
            status="accepted",
            message=f"Command {cmd.command_type} sent to {target}",
        )

    @router.post("/robot/stop", response_model=CommandResponse)
    async def emergency_stop():
        await state_machine.trigger_emergency_stop("api_triggered")
        return CommandResponse(
            command_id=str(uuid.uuid4()),
            status="accepted",
            message="Emergency stop triggered",
        )

    @router.post("/robot/home", response_model=CommandResponse)
    async def home_robot():
        await event_bus.publish(DomainEvent(
            event_type="HomeCommand",
            source_node="api",
            payload={"timestamp": datetime.now().isoformat()},
        ))
        return CommandResponse(
            command_id=str(uuid.uuid4()),
            status="accepted",
            message="Homing initiated",
        )

    @router.get("/robot/status", response_model=RobotStatus)
    async def get_robot_status():
        health = await health_service.check_all()
        rs = state_machine.get_robot_state()
        return RobotStatus(
            mode=RobotMode(config.get("robot.mode", "manual")),
            state=rs.state.value if hasattr(rs.state, 'value') else str(rs.state),
            battery=config.get("robot.battery_level"),
            nodes={
                node_id: NodeInfo(
                    node_id=node_id,
                    state=nh.state.value if hasattr(nh.state, 'value') else str(nh.state),
                    firmware_version=config.get(f"nodes.{node_id}.firmware_version", "unknown"),
                    uptime=0,
                    cpu_percent=nh.cpu_percent,
                    memory_percent=nh.memory_percent,
                    temperature=nh.temperature,
                    errors=nh.errors[-5:],
                    warnings=nh.warnings[-5:],
                )
                for node_id, nh in health.node_health.items()
            },
        )

    # ============================================================
    # Configuration
    # ============================================================

    @router.get("/config")
    async def get_config(path: Optional[str] = Query(None)):
        if path:
            value = config.get(path)
            if value is None:
                raise HTTPException(404, f"Config path '{path}' not found")
            return {"path": path, "value": value}
        return config.export()

    @router.put("/config")
    async def set_config(update: ConfigUpdate):
        try:
            config.set(update.path, update.value, persist=update.persist)
            return {"status": "ok", "path": update.path, "value": update.value}
        except ValueError as e:
            raise HTTPException(400, str(e))

    # ============================================================
    # Nodes
    # ============================================================

    @router.get("/nodes", response_model=dict[str, NodeInfo])
    async def list_nodes():
        health = await health_service.check_all()
        return {
            node_id: NodeInfo(
                node_id=node_id,
                state=nh.state.value if hasattr(nh.state, 'value') else str(nh.state),
                firmware_version=config.get(f"nodes.{node_id}.firmware_version", "unknown"),
                uptime=0,
                cpu_percent=nh.cpu_percent,
                memory_percent=nh.memory_percent,
                temperature=nh.temperature,
                errors=nh.errors[-5:],
                warnings=nh.warnings[-5:],
            )
            for node_id, nh in health.node_health.items()
        }

    @router.get("/nodes/{node_id}", response_model=NodeInfo)
    async def get_node(node_id: str):
        health = await health_service.check_all()
        nh = health.node_health.get(node_id)
        if not nh:
            raise HTTPException(404, f"Node '{node_id}' not found")
        return NodeInfo(
            node_id=node_id,
            state=nh.state.value if hasattr(nh.state, 'value') else str(nh.state),
            firmware_version=config.get(f"nodes.{node_id}.firmware_version", "unknown"),
            uptime=0,
            cpu_percent=nh.cpu_percent,
            memory_percent=nh.memory_percent,
            temperature=nh.temperature,
            errors=nh.errors[-5:],
            warnings=nh.warnings[-5:],
        )

    # ============================================================
    # State Machine
    # ============================================================

    @router.get("/state")
    async def get_robot_state():
        rs = state_machine.get_robot_state()
        return {
            "state": rs.state.value if hasattr(rs.state, 'value') else str(rs.state),
            "node_states": {
                nid: ni.state.value if hasattr(ni.state, 'value') else str(ni.state)
                for nid, ni in rs.nodes.items()
            },
            "valid_transitions": {
                s.value: [t.value for t in transitions]
                for s, transitions in NODE_TRANSITIONS.items()
            },
            "degraded_nodes": rs.degraded_nodes,
            "critical_errors": rs.critical_errors,
        }

    @router.post("/state/transition")
    async def transition_state(target_state: str = Query(..., description="Target state")):
        try:
            target = RobotState(target_state)
            await state_machine.request_global_transition(target, "api_request")
            return {"status": "ok", "target": target_state}
        except (ValueError, KeyError) as e:
            raise HTTPException(400, f"Invalid state transition: {e}")

    # ============================================================
    # Plugins
    # ============================================================

    @router.get("/plugins", response_model=list[PluginInfo])
    async def list_plugins():
        plugins = plugin_manager.list_plugins()
        return [
            PluginInfo(
                id=p.get("plugin_id", ""),
                name=p.get("name", ""),
                version=p.get("version", ""),
                state=p.get("state", "unknown"),
            )
            for p in plugins
        ]

    @router.post("/plugins/{plugin_id}/action")
    async def plugin_action(plugin_id: str, action: PluginAction):
        try:
            if action.action == "enable":
                ok = await plugin_manager.start_plugin(plugin_id)
            elif action.action == "disable":
                ok = await plugin_manager.stop_plugin(plugin_id)
            elif action.action == "reload":
                ok = await plugin_manager.reload_plugin(plugin_id)
            elif action.action == "unload":
                ok = await plugin_manager.unload_plugin(plugin_id)
            else:
                raise HTTPException(400, f"Unknown action '{action.action}'")
            if not ok:
                raise HTTPException(400, f"Plugin action '{action.action}' failed for {plugin_id}")
            return {"status": "ok", "plugin_id": plugin_id, "action": action.action}
        except ValueError as e:
            raise HTTPException(400, str(e))

    # ============================================================
    # OTA Updates
    # ============================================================

    @router.post("/ota/register")
    async def register_firmware(pkg: OTAPackage):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
                tmp_path = tmp.name
            firmware_info = await ota_manager.register_firmware(
                node_id=pkg.node_id,
                version=pkg.version,
                hardware=f"openj5-{pkg.node_id}",
                firmware_path=Path(tmp_path),
                changelog=f"Registered via API: {pkg.firmware_id}",
            )
            return {"status": "ok", "firmware_id": firmware_info.sha256[:16]}
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.post("/ota/deploy")
    async def deploy_firmware(
        node_ids: str = Query(..., description="Comma-separated node IDs"),
        version: str = Query(..., description="Firmware version"),
        force: bool = Query(False),
    ):
        try:
            nodes = [n.strip() for n in node_ids.split(",")]
            job = await ota_manager.deploy(nodes, version, force=force)
            return {"status": "ok", "job_id": job.job_id, "target_nodes": nodes}
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.get("/ota/status", response_model=list[OTAStatus])
    async def list_ota_status():
        return [
            OTAStatus(
                firmware_id=jid,
                node_id=",".join(j.target_nodes),
                status=j.status,
                progress=sum(j.progress.values()) / len(j.progress) if j.progress else 0.0,
                error=j.error,
            )
            for jid, j in ota_manager._jobs.items()
        ]

    @router.get("/ota/status/{job_id}", response_model=OTAStatus)
    async def get_ota_status(job_id: str):
        job = await ota_manager.get_job_status(job_id)
        if not job:
            raise HTTPException(404, f"Deployment job '{job_id}' not found")
        return OTAStatus(
            firmware_id=job_id,
            node_id=",".join(job.target_nodes),
            status=job.status,
            progress=sum(job.progress.values()) / len(job.progress) if job.progress else 0.0,
            error=job.error,
        )

    # ============================================================
    # Scheduler
    # ============================================================

    @router.get("/scheduler/jobs", response_model=list[ScheduleJobResponse])
    async def list_scheduled_jobs():
        jobs = scheduler.get_jobs()
        return [
            ScheduleJobResponse(job_id=j.id, status="active" if j.enabled else "paused")
            for j in jobs
        ]

    @router.post("/scheduler/jobs")
    async def create_scheduled_job(job: ScheduleJob):
        job_obj = ScheduledJob(
            id=job.job_id or str(uuid.uuid4()),
            name=job.name,
            func="",
            trigger=JobType.INTERVAL if job.interval else JobType.CRON,
            trigger_args={"seconds": int(job.interval)} if job.interval else {"expression": job.cron},
        )
        ok = await scheduler.add_job(job_obj)
        if not ok:
            raise HTTPException(400, "Failed to create job")
        return ScheduleJobResponse(job_id=job_obj.id, status="created")

    @router.delete("/scheduler/jobs/{job_id}")
    async def delete_scheduled_job(job_id: str):
        ok = await scheduler.remove_job(job_id)
        if not ok:
            raise HTTPException(404, f"Job '{job_id}' not found")
        return {"status": "ok", "job_id": job_id}

    # ============================================================
    # Health
    # ============================================================

    @router.get("/health/detailed")
    async def health_detailed():
        health = await health_service.check_all()
        return {
            "overall": health.overall,
            "state": health.state,
            "nodes": {
                node_id: {
                    "state": nh.state.value if hasattr(nh.state, 'value') else str(nh.state),
                    "cpu": nh.cpu_percent,
                    "memory": nh.memory_percent,
                    "temp": nh.temperature,
                    "errors": len(nh.errors),
                    "warnings": len(nh.warnings),
                }
                for node_id, nh in health.node_health.items()
            },
            "system": {
                name: {"healthy": r.healthy, "message": r.message}
                for name, r in health.system_checks.items()
            },
        }

    # ============================================================
    # Calibration
    # ============================================================

    @router.post("/calibration/positions")
    async def save_calibration_position(pos: CalibrationPosition):
        profile = config.get("calibration.current_profile", "default")
        key = f"calibration.profiles.{profile}.positions.{pos.name}"
        config.set(key, pos.model_dump(), persist=True)
        return {"status": "ok", "profile": profile, "position": pos.name}

    @router.get("/calibration/positions", response_model=dict[str, CalibrationPosition])
    async def list_calibration_positions():
        profile = config.get("calibration.current_profile", "default")
        positions = config.get(f"calibration.profiles.{profile}.positions", {})
        return {
            name: CalibrationPosition(name=name, **data)
            for name, data in positions.items()
        }

    # ============================================================
    # System
    # ============================================================

    @router.post("/system/shutdown")
    async def system_shutdown():
        rs = state_machine.get_robot_state()
        await state_machine.request_global_transition(RobotState.SHUTDOWN, "api_request")
        return {"status": "ok", "message": "Shutdown initiated"}

    @router.post("/system/restart")
    async def system_restart():
        await state_machine.request_global_transition(RobotState.READY, "api_restart")
        return {"status": "ok", "message": "Restart initiated"}

    @router.get("/system/info")
    async def system_info():
        return {
            "robot_name": config.get("robot.name", "OpenJ5"),
            "version": config.get("robot.version", "1.0.0"),
            "platform": "raspberry-pi-4",
            "uptime": 0,
            "nodes": 6,
            "plugins": len(plugin_manager.list_plugins()),
            "config_version": config.get("config.version", 1),
        }

    # ============================================================
    # Digital Twin
    # ============================================================

    @router.get("/simulation/status")
    async def simulation_status():
        sync = digital_twin.get_sync_state()
        return {
            "connected": sync.connected,
            "backend": digital_twin.sim_config.backend.value,
            "sim_time": sync.sim_time,
            "time_offset": sync.time_sync_offset,
            "entities_synced": sync.entities_synced,
            "sync_errors": sync.sync_errors,
        }

    @router.post("/simulation/pause")
    async def simulation_pause():
        await digital_twin.set_sim_time_scale(0.0)
        return {"status": "ok"}

    @router.post("/simulation/resume")
    async def simulation_resume():
        await digital_twin.set_sim_time_scale(1.0)
        return {"status": "ok"}

    @router.post("/simulation/reset")
    async def simulation_reset():
        ok = await digital_twin.reset_simulation()
        if not ok:
            raise HTTPException(400, "Simulation reset failed")
        return {"status": "ok"}

    return router
