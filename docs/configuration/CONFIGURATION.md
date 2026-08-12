# OpenJ5 Configuration Documentation

## Overview

**Configuration-Driven Development** is a core principle: **Zero hardcoded values**. Every parameter (servo limits, PID, topics, IPs, pins, calibrations) comes from external configuration.

---

## Configuration Hierarchy

```
Priority (Highest → Lowest):
1. Environment Variables (Secrets, Runtime Overrides)
2. Database / Config Service (PostgreSQL, Consul, etcd - Future)
3. YAML Files (config/common/, config/nodeX/)
4. JSON Files (config/nodeX/ - Node-Specific Overrides)
5. Compiled Defaults (Last Resort, Minimal)
```

---

## File Structure

```
config/
├── common/                    # Shared across all nodes
│   ├── communication.yaml     # MQTT, ROS2, WebSocket settings
│   ├── security.yaml          # TLS certs, JWT keys, CA
│   ├── topics.yaml            # MQTT Topic Schema (Versioned)
│   ├── hal.yaml               # Hardware Abstraction interfaces
│   └── safety.yaml            # Emergency stop, limits, watchdogs
├── node1_robot_core/          # Raspberry Pi 4
│   ├── node.yaml              # Node identity, network
│   ├── services.yaml          # Core services config
│   ├── plugins.yaml           # Plugin registry, enable/disable
│   ├── database.yaml          # SQLite/PostgreSQL
│   ├── eventbus.yaml          # Redis Streams/NATS
│   ├── ota.yaml               # OTA Manager
│   └── digital_twin.yaml      # Gazebo/Isaac Sim bridge
├── node2_head/                # ESP32-S3 Head Controller
│   ├── node.yaml
│   ├── servos.yaml            # 6 Servos: Neck Y/P/R, Eyes H/V, Eyelids
│   ├── pca9685.yaml           # PCA9685 config (I2C addr, freq)
│   ├── leds.yaml              # WS2812 patterns, brightness
│   ├── display.yaml           # OLED/TFT config
│   ├── audio.yaml             # I2S Microphones
│   ├── sensors.yaml           # IMU, ToF, Temperature
│   └── motion_primitives.yaml # LookAt, Nod, Shake, Blink, Scan
├── node3_right_arm/           # ESP32-S3 Right Arm
│   ├── node.yaml
│   ├── servos.yaml            # 6 Servos: Shoulder P/R/Rot, Elbow, Wrist, Gripper
│   ├── pca9685.yaml
│   ├── kinematics.yaml        # DH params, limits, collision
│   └── motion_primitives.yaml # Wave, Point, Grab, Release, Home, Reach
├── node4_left_arm/            # ESP32-S3 Left Arm (Mirrored)
│   ├── node.yaml
│   ├── servos.yaml            # Mirrored config from node3
│   ├── pca9685.yaml
│   ├── kinematics.yaml
│   └── motion_primitives.yaml
├── node5_torso/               # ESP32 Torso
│   ├── node.yaml
│   ├── servos.yaml            # 4 Servos: Torso Rot, Pitch, Battery Door, Expansion
│   ├── pca9685.yaml
│   ├── leds.yaml              # LED Strip + Fan PWM
│   ├── battery.yaml           # INA219, Voltage/Current/Temp thresholds
│   └── sensors.yaml           # IMU, ToF, Proximity
└── node6_tracks/              # ESP32 Tracks
    ├── node.yaml
    ├── motors.yaml            # 2x DC Motor + Encoder (L298N → TB6612/BTS7960/ODrive)
    ├── motor_driver.yaml      # Driver-specific config
    ├── encoders.yaml          # Quadrature encoder config
    ├── imu.yaml               # MPU6050/ICM20948
    ├── tof.yaml               # VL53L0X x2 (Front/Rear)
    ├── collision.yaml         # IR Bumpers
    ├── pid.yaml               # Velocity/Position PID
    └── motion_primitives.yaml # MoveForward, Rotate, Arc, Stop, Dock
```

---

## Configuration Schema (JSON Schema)

All configuration files have accompanying JSON Schema for validation.

### Example: `config/common/topics.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MQTT Topic Schema",
  "type": "object",
  "required": ["version", "base_topic", "nodes"],
  "properties": {
    "version": { "type": "string", "pattern": "^v\\d+$" },
    "base_topic": { "type": "string", "pattern": "^openj5/.*$" },
    "nodes": {
      "type": "object",
      "patternProperties": {
        "^node[1-6]$": {
          "type": "object",
          "required": ["cmd", "evt", "telemetry", "state"],
          "properties": {
            "cmd": { "type": "string" },
            "evt": { "type": "string" },
            "telemetry": { "type": "string" },
            "state": { "type": "string" }
          }
        }
      }
    }
  }
}
```

---

## Node Configuration Examples

### Node 1: Robot Core (`config/node1_robot_core/node.yaml`)

```yaml
node:
  id: "node1"
  name: "robot_core"
  type: "robot_core"
  hardware: "raspberry_pi_4_8gb"
  os: "ubuntu_server_24_04_lts"
  architecture: "arm64"

network:
  hostname: "openj5-core"
  interfaces:
    eth0:
      dhcp: true
      static_ip: null
    wlan0:
      dhcp: true
      ap_mode: false
  mqtt:
    host: "localhost"
    port: 8883
    tls: true
    ca_cert: "/etc/openj5/certs/ca.crt"
    client_cert: "/etc/openj5/certs/node1.crt"
    client_key: "/etc/openj5/certs/node1.key"
    keepalive: 60
  ros2:
    domain_id: 42
    rmw_impl: "rmw_fastrtps_cpp"
  websocket:
    port: 8081
    tls: true

services:
  config_service:
    enabled: true
    hot_reload: true
    watch_interval_ms: 1000
  logging_service:
    enabled: true
    level: "INFO"
    format: "json"
    outputs: ["stdout", "file", "loki"]
    file_path: "/var/log/openj5/robot_core.jsonl"
    correlation_id_header: "X-Correlation-ID"
  database:
    enabled: true
    type: "postgresql"
    host: "localhost"
    port: 5432
    name: "openj5"
    user: "openj5"
    password_env: "OPENJ5_DB_PASSWORD"
    pool_size: 10
    migrations_path: "/opt/openj5/migrations"
  event_bus:
    enabled: true
    type: "redis_streams"
    host: "localhost"
    port: 6379
    password_env: "OPENJ5_REDIS_PASSWORD"
    streams:
      - "openj5.events.commands"
      - "openj5.events.telemetry"
      - "openj5.events.state"
      - "openj5.events.errors"
    consumer_group: "robot_core"
    max_len: 10000
  plugin_manager:
    enabled: true
    plugin_dirs:
      - "/opt/openj5/plugins"
      - "/home/openj5/.openj5/plugins"
    auto_load: true
    sandbox: false
  ota_manager:
    enabled: true
    firmware_dir: "/opt/openj5/firmware"
    signing_key_env: "OPENJ5_OTA_SIGNING_KEY"
    verify_signature: true
    rollback_on_failure: true
    max_parallel: 2
  scheduler:
    enabled: true
    timezone: "UTC"
    jobs:
      - id: "health_check"
        trigger: "interval"
        seconds: 30
        func: "health_check_all_nodes"
      - id: "db_cleanup"
        trigger: "cron"
        cron: "0 3 * * *"
        func: "cleanup_old_telemetry"
  rest_api:
    enabled: true
    host: "0.0.0.0"
    port: 8080
    tls: true
    cert_file: "/etc/openj5/certs/api.crt"
    key_file: "/etc/openj5/certs/api.key"
    cors_origins: ["https://openj5.local", "http://localhost:3000"]
    rate_limit: "100/minute"
    auth:
      type: "jwt"
      algorithm: "RS256"
      public_key_env: "OPENJ5_JWT_PUBLIC_KEY"
      issuer: "openj5"
      audience: "openj5-api"
  digital_twin:
    enabled: true
    simulator: "gazebo"
    gazebo:
      model_path: "/opt/openj5/simulation/gazebo/models"
      world_file: "/opt/openj5/simulation/gazebo/worlds/openj5.world"
      bridge_config: "/opt/openj5/config/node1_robot_core/gazebo_bridge.yaml"
    isaac_sim:
      enabled: false
      usd_path: "/opt/openj5/simulation/isaac_sim/openj5.usd"

plugins:
  enabled:
    - "vision_plugin"
    - "speech_plugin"
    - "ai_plugin"
    - "navigation_plugin"
    - "battery_plugin"
  disabled:
    - "experimental_plugin"
  config:
    vision_plugin:
      model: "yolov8n"
      device: "cpu"
      confidence_threshold: 0.5
    speech_plugin:
      stt_model: "whisper-base"
      tts_model: "piper"
      language: "it"
    ai_plugin:
      llm_model: "llama-3-8b-instruct"
      context_window: 4096
    navigation_plugin:
      slam_toolbox: true
      nav2: true
```

---

### Node 2: Head Controller (`config/node2_head/servos.yaml`)

```yaml
pca9685:
  i2c_bus: 1
  address: 0x40
  frequency_hz: 50
  oe_pin: 22

servos:
  - name: "neck_yaw"
    channel: 0
    min_pulse: 150
    max_pulse: 600
    home_pulse: 375
    min_angle_deg: -90.0
    max_angle_deg: 90.0
    home_angle_deg: 0.0
    speed_deg_per_sec: 60.0
    acceleration_deg_per_sec2: 120.0
    offset_deg: 0.0
    reversed: false
    calibration:
      center_pulse: 375
      range_pulse: 450

  - name: "neck_pitch"
    channel: 1
    min_pulse: 150
    max_pulse: 600
    home_pulse: 375
    min_angle_deg: -45.0
    max_angle_deg: 45.0
    home_angle_deg: 0.0
    speed_deg_per_sec: 60.0
    acceleration_deg_per_sec2: 120.0
    offset_deg: 0.0
    reversed: false
    calibration:
      center_pulse: 375
      range_pulse: 450

  - name: "neck_roll"
    channel: 2
    min_pulse: 150
    max_pulse: 600
    home_pulse: 375
    min_angle_deg: -30.0
    max_angle_deg: 30.0
    home_angle_deg: 0.0
    speed_deg_per_sec: 60.0
    acceleration_deg_per_sec2: 120.0
    offset_deg: 0.0
    reversed: false
    calibration:
      center_pulse: 375
      range_pulse: 450

  - name: "eyes_horizontal"
    channel: 3
    min_pulse: 200
    max_pulse: 550
    home_pulse: 375
    min_angle_deg: -45.0
    max_angle_deg: 45.0
    home_angle_deg: 0.0
    speed_deg_per_sec: 120.0
    acceleration_deg_per_sec2: 240.0
    offset_deg: 0.0
    reversed: false
    calibration:
      center_pulse: 375
      range_pulse: 350

  - name: "eyes_vertical"
    channel: 4
    min_pulse: 200
    max_pulse: 550
    home_pulse: 375
    min_angle_deg: -30.0
    max_angle_deg: 30.0
    home_angle_deg: 0.0
    speed_deg_per_sec: 120.0
    acceleration_deg_per_sec2: 240.0
    offset_deg: 0.0
    reversed: true
    calibration:
      center_pulse: 375
      range_pulse: 350

  - name: "eyelids"
    channel: 5
    min_pulse: 250
    max_pulse: 500
    home_pulse: 375
    min_angle_deg: 0.0
    max_angle_deg: 90.0
    home_angle_deg: 0.0
    speed_deg_per_sec: 180.0
    acceleration_deg_per_sec2: 360.0
    offset_deg: 0.0
    reversed: false
    calibration:
      center_pulse: 375
      range_pulse: 250
```

---

### Node 2: Head Motion Primitives (`config/node2_head/motion_primitives.yaml`)

```yaml
primitives:
  - name: "home"
    description: "Return all servos to home position"
    servos:
      - neck_yaw: 0.0
      - neck_pitch: 0.0
      - neck_roll: 0.0
      - eyes_horizontal: 0.0
      - eyes_vertical: 0.0
      - eyelids: 0.0
    duration_sec: 1.0
    easing: "ease_in_out_cubic"

  - name: "look_at"
    description: "Look at specific 3D coordinates"
    parameters:
      - name: "x"
        type: "float"
        unit: "meters"
      - name: "y"
        type: "float"
        unit: "meters"
      - name: "z"
        type: "float"
        unit: "meters"
    implementation: "inverse_kinematics"

  - name: "nod"
    description: "Nod head up/down"
    parameters:
      - name: "amplitude_deg"
        type: "float"
        default: 20.0
      - name: "cycles"
        type: "int"
        default: 2
      - name: "speed_multiplier"
        type: "float"
        default: 1.0
    sequence:
      - servos:
          neck_pitch: -20.0
        duration_sec: 0.5
      - servos:
          neck_pitch: 20.0
        duration_sec: 0.5
      - servos:
          neck_pitch: 0.0
        duration_sec: 0.5
    repeat: "{{cycles}}"

  - name: "shake"
    description: "Shake head left/right"
    parameters:
      - name: "amplitude_deg"
        type: "float"
        default: 30.0
      - name: "cycles"
        type: "int"
        default: 2
    sequence:
      - servos:
          neck_yaw: -30.0
        duration_sec: 0.4
      - servos:
          neck_yaw: 30.0
        duration_sec: 0.4
      - servos:
          neck_yaw: 0.0
        duration_sec: 0.4
    repeat: "{{cycles}}"

  - name: "blink"
    description: "Close and open eyelids"
    parameters:
      - name: "duration_ms"
        type: "int"
        default: 150
    sequence:
      - servos:
          eyelids: 90.0
        duration_sec: 0.1
      - servos:
          eyelids: 0.0
        duration_sec: 0.1

  - name: "scan"
    description: "Scan environment left to right"
    parameters:
      - name: "start_deg"
        type: "float"
        default: -90.0
      - name: "end_deg"
        type: "float"
        default: 90.0
      - name: "step_deg"
        type: "float"
        default: 15.0
      - name: "pause_sec"
        type: "float"
        default: 0.5
    implementation: "custom_scan_algorithm"
```

---

### Node 6: Tracks (`config/node6_tracks/motors.yaml`)

```yaml
motor_driver:
  type: "l298n"  # Options: l298n, tb6612, bts7960, odrive
  config:
    l298n:
      left_motor:
        ena_pin: 18
        in1_pin: 19
        in2_pin: 21
      right_motor:
        enb_pin: 23
        in3_pin: 22
        in4_pin: 5
      pwm_frequency_hz: 1000
      pwm_resolution_bits: 10

motors:
  - id: "left"
    type: "dc_geared"
    encoder:
      type: "quadrature"
      pin_a: 34
      pin_b: 35
      ppr: 1024  # Pulses Per Revolution
      inverted: false
    gear_ratio: 30:1
    wheel_diameter_mm: 80
    wheel_base_mm: 200
    max_rpm: 200
    pid:
      kp: 0.8
      ki: 0.1
      kd: 0.05
      output_min: -1023
      output_max: 1023
      integral_min: -500
      integral_max: 500

  - id: "right"
    type: "dc_geared"
    encoder:
      type: "quadrature"
      pin_a: 36
      pin_b: 39
      ppr: 1024
      inverted: true
    gear_ratio: 30:1
    wheel_diameter_mm: 80
    wheel_base_mm: 200
    max_rpm: 200
    pid:
      kp: 0.8
      ki: 0.1
      kd: 0.05
      output_min: -1023
      output_max: 1023
      integral_min: -500
      integral_max: 500

odometry:
  type: "differential"
  update_rate_hz: 50
  covariance:
    x: 0.01
    y: 0.01
    theta: 0.001
```

---

### Node 6: Tracks Motion Primitives (`config/node6_tracks/motion_primitives.yaml`)

```yaml
primitives:
  - name: "move_forward"
    description: "Move forward at specified velocity"
    parameters:
      - name: "velocity_mps"
        type: "float"
        unit: "m/s"
        min: -0.5
        max: 0.5
        default: 0.2
      - name: "distance_m"
        type: "float"
        unit: "meters"
        min: 0.0
        default: 0.0  # 0 = continuous
    implementation: "velocity_control_with_odometry"

  - name: "rotate"
    description: "Rotate in place"
    parameters:
      - name: "angular_velocity_radps"
        type: "float"
        unit: "rad/s"
        min: -1.0
        max: 1.0
        default: 0.5
      - name: "angle_rad"
        type: "float"
        unit: "radians"
        default: 0.0  # 0 = continuous
    implementation: "velocity_control_with_imu_fusion"

  - name: "arc"
    description: "Move in an arc (different wheel velocities)"
    parameters:
      - name: "linear_velocity_mps"
        type: "float"
        unit: "m/s"
        default: 0.2
      - name: "angular_velocity_radps"
        type: "float"
        unit: "rad/s"
        default: 0.3
    implementation: "differential_drive_arc"

  - name: "stop"
    description: "Emergency stop - brake both motors"
    parameters: []
    implementation: "brake_motors"
    priority: "critical"

  - name: "dock"
    description: "Autonomous docking to charging station"
    parameters:
      - name: "dock_id"
        type: "string"
    implementation: "nav2_docking"
```

---

## Configuration Loading (Python Example)

```python
# src/config/config_loader.py
from pathlib import Path
from typing import Any, TypeVar, Type
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml
import json
import os

T = TypeVar('T', bound=BaseModel)

class ConfigLoader:
    """Configuration loader with priority: ENV > DB > YAML > JSON > Defaults"""

    def __init__(self, config_root: Path = Path("/etc/openj5")):
        self.config_root = config_root
        self._cache = {}
        self._watchers = {}

    def load(self, model: Type[T], node_id: str, config_name: str) -> T:
        """Load configuration for a specific node and config file"""
        # Priority order (highest first)
        sources = [
            self._load_env_override(node_id, config_name),
            self._load_from_database(node_id, config_name),
            self._load_yaml(self.config_root / "common" / f"{config_name}.yaml"),
            self._load_yaml(self.config_root / f"node{node_id}" / f"{config_name}.yaml"),
            self._load_json(self.config_root / f"node{node_id}" / f"{config_name}.json"),
        ]

        # Merge with priority
        merged = {}
        for source in sources:
            if source:
                merged = {**merged, **source}

        try:
            return model(**merged)
        except ValidationError as e:
            raise ConfigValidationError(f"Config validation failed for {node_id}/{config_name}: {e}")

    def watch(self, model: Type[T], node_id: str, config_name: str, callback: callable):
        """Hot-reload configuration on file changes"""
        # Implementation uses watchdog or inotify
        pass

# Usage
servo_config = config_loader.load(ServoConfig, "2", "servos")
motion_primitives = config_loader.load(MotionPrimitivesConfig, "2", "motion_primitives")
```

---

## Environment Variable Override Pattern

```bash
# Override any config value via environment variable
# Pattern: OPENJ5_<NODE>_<CONFIG>_<KEY> (dots become underscores)

export OPENJ5_NODE2_SERVOS_NECK_YAW_MAX_ANGLE_DEG=100.0
export OPENJ5_NODE6_MOTORS_LEFT_PID_KP=1.0
export OPENJ5_COMMON_COMMUNICATION_MQTT_HOST=192.168.1.100
export OPENJ5_NODE1_DATABASE_PASSWORD=secret_from_vault
```

---

## Validation & CI Integration

```yaml
# .github/workflows/config-validation.yml
name: Config Validation
on: [push, pull_request]
jobs:
  validate-configs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate all JSON configs
        run: |
          find config -name "*.json" -exec python -m json.tool {} \;
      - name: Validate all YAML configs
        run: |
          find config -name "*.yaml" -exec python -c "import yaml; yaml.safe_load(open('{}'))" \;
      - name: Validate against JSON Schemas
        run: |
          python scripts/validate_configs.py
      - name: Check for magic numbers in source
        run: |
          if grep -r "= [0-9]" src/ --include="*.py" --include="*.cpp" --include="*.h" | grep -v "3.14\|180\|360\|1000\|1024"; then
            echo "Magic numbers found!"
            exit 1
          fi
```

---

## Configuration Service API (Node 1)

```
GET    /api/v1/config/{node_id}/{config_name}     # Get config
PUT    /api/v1/config/{node_id}/{config_name}     # Update config (triggers hot-reload)
POST   /api/v1/config/{node_id}/{config_name}/validate  # Validate without applying
GET    /api/v1/config/{node_id}/{config_name}/schema      # Get JSON Schema
WS     /api/v1/config/{node_id}/{config_name}/watch       # Real-time updates
```

---

## Migration Strategy

When config schema changes:

1. **Add new fields as optional** with defaults
2. **Provide migration script** in `scripts/migrate_config_vX_to_vY.py`
3. **Support dual schema** for 1 major version
4. **Document in CHANGELOG.md** and **ADR**