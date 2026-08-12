"""
OpenJ5 Robot Core - Digital Twin Bridge

Synchronizes state between real robot and simulator (Gazebo/Isaac Sim).
Same Robot SDK controls both real and simulated robot.
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


class SimulatorBackend(str, Enum):
    GAZEBO = "gazebo"
    ISAAC_SIM = "isaac_sim"
    WEBOTS = "webots"
    MUJOCO = "mujoco"


@dataclass
class SimulatorConfig:
    """Simulator connection configuration."""
    backend: SimulatorBackend = SimulatorBackend.GAZEBO
    host: str = "localhost"
    port: int = 11345  # gz-transport
    model_path: str = "/opt/openj5/simulation/gazebo/models"
    world_file: str = "/opt/openj5/simulation/gazebo/worlds/openj5.sdf"
    bridge_config: str = "/opt/openj5/config/gazebo_bridge.yaml"
    headless: bool = True
    use_gpu: bool = False


@dataclass
class SyncState:
    """Synchronization state."""
    connected: bool = False
    sim_time: float = 0.0
    real_time: float = 0.0
    time_sync_offset: float = 0.0
    last_sync: str = field(default_factory=datetime.now().isoformat)
    entities_synced: int = 0
    sync_errors: int = 0


class DigitalTwinBridge:
    """
    Bridges Robot Core with physics simulator.
    
    Features:
    - Bidirectional state sync (commands -> sim, telemetry <- sim)
    - Time synchronization
    - Entity mapping (ROS2 topics <-> gz-transport)
    - Sensor simulation (camera, lidar, IMU)
    - Actuator command forwarding
    """
    
    def __init__(
        self,
        config: ConfigService,
        event_bus: EventBus,
        database=None,
        command_bus: Any = None,
        query_bus: Any = None,
    ):
        self.config = config
        self.event_bus = event_bus
        self.database = database
        self.command_bus = command_bus
        self.query_bus = query_bus
        
        self.sim_config = self._load_sim_config()
        self.state = SyncState()
        self._running = False
        self._gz_client = None
        self._ros2_bridge = None
        
        # Entity mapping: robot entity -> sim entity
        self._entity_map = {
            # Joints
            "neck_yaw": "openj5::head::neck_yaw_joint",
            "neck_pitch": "openj5::head::neck_pitch_joint",
            "neck_roll": "openj5::head::neck_roll_joint",
            "eyes_h": "openj5::head::eyes_horizontal_joint",
            "eyes_v": "openj5::head::eyes_vertical_joint",
            "eyelids": "openj5::head::eyelids_joint",
            # Arms
            "right_shoulder_pitch": "openj5::right_arm::shoulder_pitch_joint",
            "right_shoulder_roll": "openj5::right_arm::shoulder_roll_joint",
            "right_shoulder_yaw": "openj5::right_arm::shoulder_yaw_joint",
            "right_elbow": "openj5::right_arm::elbow_joint",
            "right_wrist": "openj5::right_arm::wrist_joint",
            "right_gripper": "openj5::right_arm::gripper_joint",
            "left_shoulder_pitch": "openj5::left_arm::shoulder_pitch_joint",
            "left_shoulder_roll": "openj5::left_arm::shoulder_roll_joint",
            "left_shoulder_yaw": "openj5::left_arm::shoulder_yaw_joint",
            "left_elbow": "openj5::left_arm::elbow_joint",
            "left_wrist": "openj5::left_arm::wrist_joint",
            "left_gripper": "openj5::left_arm::gripper_joint",
            # Torso
            "torso_rotation": "openj5::torso::rotation_joint",
            "torso_pitch": "openj5::torso::pitch_joint",
            "battery_door": "openj5::torso::battery_door_joint",
            # Tracks
            "left_wheel": "openj5::tracks::left_wheel_joint",
            "right_wheel": "openj5::tracks::right_wheel_joint",
        }
    
    def _load_sim_config(self) -> SimulatorConfig:
        """Load simulator configuration."""
        return SimulatorConfig(
            backend=SimulatorBackend(self.config.get("digital_twin.simulator", "gazebo")),
            host=self.config.get("digital_twin.host", "localhost"),
            port=self.config.get("digital_twin.port", 11345),
            model_path=self.config.get("digital_twin.model_path", "/opt/openj5/simulation/gazebo/models"),
            world_file=self.config.get("digital_twin.world_file", "/opt/openj5/simulation/gazebo/worlds/openj5.sdf"),
            bridge_config=self.config.get("digital_twin.bridge_config", "/opt/openj5/config/gazebo_bridge.yaml"),
            headless=self.config.get("digital_twin.headless", True),
            use_gpu=self.config.get("digital_twin.use_gpu", False),
        )
    
    async def connect(self) -> bool:
        """Connect to simulator."""
        try:
            if self.sim_config.backend == SimulatorBackend.GAZEBO:
                return await self._connect_gazebo()
            elif self.sim_config.backend == SimulatorBackend.ISAAC_SIM:
                return await self._connect_isaac_sim()
            else:
                logger.error("Unsupported simulator backend", backend=self.sim_config.backend)
                return False
        except Exception as e:
            logger.error("Failed to connect to simulator", error=str(e))
            return False
    
    async def _connect_gazebo(self) -> bool:
        """Connect to Gazebo via gz-transport."""
        try:
            # Import gz-transport Python bindings
            import gz.transport as gz_transport
            
            self._gz_client = gz_transport.Node()
            
            # Advertise joint command topics
            for joint_name, sim_joint in self._entity_map.items():
                topic = f"/model/openj5/joint/{sim_joint}/cmd_pos"
                self._gz_client.advertise(topic, gz_transport.MESSAGE_TYPE_DOUBLE)
            
            # Subscribe to joint states
            self._gz_client.subscribe(
                "/model/openj5/joint_state",
                self._on_joint_state,
            )
            
            # Subscribe to world stats (sim time)
            self._gz_client.subscribe(
                "/world/stats",
                self._on_world_stats,
            )
            
            self.state.connected = True
            logger.info("Connected to Gazebo", host=self.sim_config.host, port=self.sim_config.port)
            return True
            
        except ImportError:
            logger.warning("gz-transport not available, using ROS2 bridge fallback")
            return await self._connect_ros2_bridge()
        except Exception as e:
            logger.error("Gazebo connection failed", error=str(e))
            return False
    
    async def _connect_ros2_bridge(self) -> bool:
        """Connect via ROS2-Gazebo bridge (ros_gz_bridge)."""
        # This assumes ros_gz_bridge is running separately
        # We connect to ROS2 topics that bridge Gazebo topics
        logger.info("Using ROS2-Gazebo bridge")
        self.state.connected = True
        return True
    
    async def _connect_isaac_sim(self) -> bool:
        """Connect to NVIDIA Isaac Sim."""
        # Isaac Sim uses ROS2 bridge or Omniverse connectors
        logger.info("Isaac Sim backend not yet implemented")
        return False
    
    async def disconnect(self) -> None:
        """Disconnect from simulator."""
        if self._gz_client:
            self._gz_client.shutdown()
            self._gz_client = None
        self.state.connected = False
        logger.info("Disconnected from simulator")
    
    async def sync_command(self, command: dict) -> bool:
        """
        Sync robot command to simulator.
        
        Args:
            command: {"entity": "neck_yaw", "position": 0.5, "velocity": 1.0}
        """
        if not self.state.connected:
            return False
        
        entity = command.get("entity")
        position = command.get("position")
        velocity = command.get("velocity")
        
        if entity not in self._entity_map:
            logger.warning("Unknown entity for sim sync", entity=entity)
            return False
        
        sim_joint = self._entity_map[entity]
        
        try:
            if self._gz_client:
                # Send position command
                topic = f"/model/openj5/joint/{sim_joint}/cmd_pos"
                await self._gz_client.publish(topic, position)
                
                if velocity is not None:
                    vel_topic = f"/model/openj5/joint/{sim_joint}/cmd_vel"
                    await self._gz_client.publish(vel_topic, velocity)
            
            self.state.entities_synced += 1
            return True
            
        except Exception as e:
            logger.error("Sim sync failed", entity=entity, error=str(e))
            self.state.sync_errors += 1
            return False
    
    async def sync_bulk_commands(self, commands: list[dict]) -> int:
        """Sync multiple commands at once."""
        synced = 0
        for cmd in commands:
            if await self.sync_command(cmd):
                synced += 1
        return synced
    
    async def _on_joint_state(self, msg) -> None:
        """Handle joint state from simulator."""
        # Convert Gazebo joint state to robot telemetry
        # msg contains: name[], position[], velocity[], effort[]
        
        telemetry = {}
        for name, pos, vel, eff in zip(msg.name, msg.position, msg.velocity, msg.effort):
            # Map sim joint name back to robot entity
            robot_entity = self._reverse_map(name)
            if robot_entity:
                telemetry[robot_entity] = {
                    "position": pos,
                    "velocity": vel,
                    "effort": eff,
                }
        
        if telemetry:
            await self.event_bus.publish(DomainEvent(
                event_type="SimJointTelemetry",
                source_node="simulator",
                payload={"joints": telemetry, "timestamp": datetime.now().isoformat()},
            ))
    
    async def _on_world_stats(self, msg) -> None:
        """Handle world stats (sim time)."""
        sim_time = msg.sim_time.sec + msg.sim_time.nsec * 1e-9
        real_time = asyncio.get_event_loop().time()
        
        self.state.sim_time = sim_time
        self.state.real_time = real_time
        self.state.time_sync_offset = sim_time - real_time
        self.state.last_sync = datetime.now().isoformat()
    
    def _reverse_map(self, sim_name: str) -> Optional[str]:
        """Map sim joint name to robot entity."""
        for robot_entity, sim_entity in self._entity_map.items():
            if sim_entity in sim_name or sim_name.endswith(sim_entity.split("::")[-1]):
                return robot_entity
        return None
    
    async def publish_sensor_data(self, sensor_type: str, data: dict) -> None:
        """Publish sensor data to simulator (for sensor simulation)."""
        if not self.state.connected:
            return
        
        # For camera: publish to Gazebo camera topic
        # For lidar: publish to Gazebo lidar topic
        # For IMU: publish to Gazebo IMU topic
        
        topic_map = {
            "camera": "/model/openj5/sensor/camera/image",
            "depth": "/model/openj5/sensor/depth/image",
            "lidar": "/model/openj5/sensor/lidar/scan",
            "imu": "/model/openj5/sensor/imu/data",
        }
        
        topic = topic_map.get(sensor_type)
        if topic and self._gz_client:
            try:
                await self._gz_client.publish(topic, data)
            except Exception as e:
                logger.error("Sensor publish failed", sensor=sensor_type, error=str(e))
    
    async def reset_simulation(self) -> bool:
        """Reset simulation to initial state."""
        if not self._gz_client:
            return False
        
        try:
            await self._gz_client.publish("/world/openj5/control", {"reset": True})
            logger.info("Simulation reset")
            return True
        except Exception as e:
            logger.error("Simulation reset failed", error=str(e))
            return False
    
    async def set_sim_time_scale(self, scale: float) -> bool:
        """Set simulation time scale (1.0 = real-time)."""
        if not self._gz_client:
            return False
        
        try:
            await self._gz_client.publish(
                "/world/openj5/set_time_scale",
                {"scale": scale},
            )
            return True
        except Exception as e:
            logger.error("Time scale set failed", error=str(e))
            return False
    
    def get_sync_state(self) -> SyncState:
        """Get synchronization state."""
        return self.state
    
    async def health_check(self) -> dict:
        """Health check for digital twin."""
        return {
            "connected": self.state.connected,
            "backend": self.sim_config.backend.value,
            "sim_time": self.state.sim_time,
            "time_offset": self.state.time_sync_offset,
            "entities_synced": self.state.entities_synced,
            "sync_errors": self.state.sync_errors,
            "healthy": self.state.connected and self.state.sync_errors < 10,
        }


async def get_digital_twin_bridge(
    config: ConfigService,
    event_bus: EventBus,
    database=None,
    command_bus: Any = None,
    query_bus: Any = None,
) -> DigitalTwinBridge:
    """Get digital twin bridge instance."""
    bridge = DigitalTwinBridge(config, event_bus, database, command_bus, query_bus)
    await bridge.connect()
    return bridge