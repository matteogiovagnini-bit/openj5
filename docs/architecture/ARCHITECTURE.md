# OpenJ5 Architecture Documentation

## Overview

OpenJ5 follows **Hexagonal Architecture (Ports & Adapters)** with **Domain-Driven Design (DDD)**, **Event-Driven Architecture**, and **Plugin Architecture**. The system is composed of 7 distributed nodes (6 original + Node 7 Balance, ADR-017) communicating through an abstract Communication Gateway. Per ADR-019 all actuator/sensor nodes are ESP32-S3 and Node 1 (the Raspberry Pi) is brain only.

---

## System Context Diagram

```mermaid
C4Context
    title System Context Diagram - OpenJ5 Robot Platform

    Person(user, "User / Researcher", "Interacts via Web UI, API, Teleop")
    Person(developer, "Developer", "Extends platform via Plugins, SDK")

    System_Boundary(openj5, "OpenJ5 Platform") {
        System(node1, "Node 1: Robot Core (RPi4)", "Raspberry Pi OS Lite 64-bit + Docker + MQTT Broker\nBrain only (ADR-019): AI, Vision, Speech, Planning, Behavior\nConfig, Logging, DB, OTA, Plugin Manager")
        System(node2, "Node 2: Head Controller (ESP32-S3)", "6 Servos, LED, Display, Microphones, Sensors")
        System(node3, "Node 3: Right Arm (ESP32-S3)", "6 Servos: Shoulder P/R/Rot, Elbow, Wrist, Gripper")
        System(node4, "Node 4: Left Arm (ESP32-S3)", "6 Servos: Mirrored Right Arm")
        System(node5, "Node 5: Torso (ESP32-S3)", "4 Servos, LED, Fan, Battery Monitor, Sensors")
        System(node6, "Node 6: Tracks (ESP32-S3)", "2 DC Motors + Encoder, 2x ToF, Collision Sensors (ADR-019)")
        System(node7, "Node 7: Balance Controller (ESP32-S3)", "NEMA17 + A4988, Body IMU MPU6050, Active Body Leveling (ADR-017)")
        System(sim, "Digital Twin (Gazebo/Isaac Sim)", "Physics Simulation, Visualization")
    }

    System_Ext(mqtt, "MQTT Broker (Mosquitto/EMQX)", "Message Transport")
    System_Ext(ros2, "ROS 2 Network", "Alternative Transport")
    System_Ext(cloud, "Cloud / Fleet Manager", "Multi-robot, OTA, Monitoring")

    Rel(user, node1, "REST API / WebSocket / Web UI")
    Rel(developer, node1, "SDK / Plugin Development")
    Rel(node1, mqtt, "MQTT over TLS/mTLS")
    Rel(node2, mqtt, "MQTT over TLS/mTLS")
    Rel(node3, mqtt, "MQTT over TLS/mTLS")
    Rel(node4, mqtt, "MQTT over TLS/mTLS")
    Rel(node5, mqtt, "MQTT over TLS/mTLS")
    Rel(node6, mqtt, "MQTT over TLS/mTLS")
    Rel(node7, mqtt, "MQTT over TLS/mTLS")
    Rel(node1, ros2, "ROS 2 Bridge (Optional)")
    Rel(node1, sim, "Digital Twin Bridge")
    Rel(node1, cloud, "Fleet Management / OTA")
```

---

## Container Diagram (Node 1 - Robot Core)

```mermaid
C4Container
    title Container Diagram - Node 1: Robot Core (Raspberry Pi 4)

    Container_Boundary(robot_core, "Robot Core") {
        Container(config_svc, "Configuration Service", "Python/FastAPI", "Hot-reload JSON/YAML/DB config, Schema validation")
        Container(logging_svc, "Logging Service", "Python/Structlog", "Structured JSON logs, Correlation IDs, Log aggregation")
        Container(db, "Database (SQLite/PostgreSQL)", "SQLAlchemy", "Robot state, Events, Calibration, Telemetry")
        Container(event_bus, "Event Bus", "Redis Streams / NATS", "Pub/Sub typed events, Dead letter, Replay")
        Container(plugin_mgr, "Plugin Manager", "Python/Importlib", "Dynamic load/unload, Versioning, Dependencies")
        Container(ota_mgr, "OTA Manager", "Python", "Signed firmware deploy, Rollback, Staged rollout")
        Container(scheduler, "Task Scheduler", "APScheduler", "Cron/Interval tasks, Health checks, Maintenance")
        Container(robot_core_svc, "Robot Core Service", "Python/FastAPI", "Orchestration, State Machine, Health")
        Container(rest_api, "REST API + WebSocket", "FastAPI + Uvicorn", "OpenAPI/Swagger, Auth JWT, Rate limiting")
        Container(mqtt_broker, "MQTT Broker", "Mosquitto/EMQX", "TLS, ACL, Persistent sessions, Bridge to ROS2")
        Container(ros2_bridge, "ROS 2 Bridge", "rosbridge_suite", "WebSocket ↔ ROS 2 topics/services/actions")
        Container(digital_twin, "Digital Twin Bridge", "Python", "Gazebo/Isaac Sim ↔ Robot Core sync")
    }

    Container(node2, "Node 2: Head", "ESP-IDF/C++", "MQTT Client")
    Container(node3, "Node 3: Right Arm", "ESP-IDF/C++", "MQTT Client")
    Container(node4, "Node 4: Left Arm", "ESP-IDF/C++", "MQTT Client")
    Container(node5, "Node 5: Torso", "ESP-IDF/C++", "MQTT Client")
    Container(node6, "Node 6: Tracks", "ESP-IDF/C++", "MQTT Client")
    Container(node7, "Node 7: Balance", "ESP-IDF/C++", "MQTT Client")
    Container(sim, "Digital Twin", "Gazebo/Isaac Sim", "ROS 2 / gRPC")

    Rel(robot_core_svc, config_svc, "Gets config")
    Rel(robot_core_svc, logging_svc, "Logs to")
    Rel(robot_core_svc, db, "Persists state/events")
    Rel(robot_core_svc, event_bus, "Publishes/Subscribes events")
    Rel(robot_core_svc, plugin_mgr, "Manages plugins")
    Rel(robot_core_svc, ota_mgr, "Triggers OTA")
    Rel(robot_core_svc, scheduler, "Schedules tasks")
    Rel(robot_core_svc, mqtt_broker, "Publishes/Subscribes via Gateway")
    Rel(robot_core_svc, digital_twin, "Syncs state")
    Rel(rest_api, robot_core_svc, "Calls internal API")
    Rel(rest_api, event_bus, "WebSocket event stream")
    Rel(mqtt_broker, node2, "MQTT over TLS")
    Rel(mqtt_broker, node3, "MQTT over TLS")
    Rel(mqtt_broker, node4, "MQTT over TLS")
    Rel(mqtt_broker, node5, "MQTT over TLS")
    Rel(mqtt_broker, node6, "MQTT over TLS")
    Rel(mqtt_broker, node7, "MQTT over TLS")
    Rel(ros2_bridge, sim, "ROS 2 topics")
    Rel(digital_twin, sim, "State sync")
```

---

## Component Diagram - Core Domain (Hexagonal Architecture)

```mermaid
C4Component
    title Component Diagram - Core Domain (Hexagonal Architecture)

    Container_Boundary(domain, "Domain Layer (Zero External Deps)") {
        Component(entities, "Entities", "Robot, Node, Servo, Motor, Sensor, Battery, Plugin")
        Component(value_objects, "Value Objects", "Angle, Position, Velocity, Quaternion, Temperature, Voltage")
        Component(domain_events, "Domain Events", "NodeStateChanged, ServoMoved, CommandReceived, ErrorOccurred")
        Component(repositories, "Repository Interfaces", "IRobotRepository, INodeRepository, IConfigRepository, IEventStore")
        Component(services, "Domain Services", "KinematicsService, MotionPlanner, CollisionAvoidance, BatteryManager")
        Component(policies, "Policies / Rules", "SafetyPolicy, MotionLimitsPolicy, PowerBudgetPolicy")
    }

    Container_Boundary(application, "Application Layer") {
        Component(use_cases, "Use Cases / Commands", "MoveHead, MoveArm, MoveTracks, SayText, LoadPlugin, DeployOTA")
        Component(queries, "Queries", "GetRobotState, GetNodeHealth, GetServoPosition, GetBatteryLevel")
        Component(event_handlers, "Event Handlers", "OnFaceDetected, OnBatteryLow, OnNodeError, OnCommandReceived")
        Component(command_bus, "Command Bus", "Dispatches commands to handlers")
        Component(query_bus, "Query Bus", "Dispatches queries to handlers")
    }

    Container_Boundary(infrastructure, "Infrastructure Layer (Adapters)") {
        Component(mqtt_gateway, "MQTT Gateway Adapter", "Implements ICommunicationGateway")
        Component(ros2_gateway, "ROS 2 Gateway Adapter", "Implements ICommunicationGateway")
        Component(ws_gateway, "WebSocket Gateway Adapter", "Implements ICommunicationGateway")
        Component(redis_event_bus, "Redis Event Bus Adapter", "Implements IEventBus")
        Component(sqlite_repo, "SQLite Repository Adapter", "Implements IRepository")
        Component(file_config, "File Config Adapter", "Implements IConfigProvider (JSON/YAML)")
        Component(pca9685_driver, "PCA9685 Driver Adapter", "Implements IServoDriver")
        Component(motor_driver, "Motor HAL Adapters", "Implements IMotorDriver: MockMotorDriver on the host; L298NDriver on the Node 6 ESP32-S3 firmware (ADR-019)")
        Component(a4988_driver, "A4988 Driver Adapter", "Implements IStepperDriver")
        Component(vl53l0x_driver, "VL53L0X Driver Adapter", "Implements IDistanceSensor")
        Component(mpu6050_driver, "MPU6050 Driver Adapter", "Implements IIMU")
        Component(plugin_loader, "Plugin Loader", "Implements IPluginManager")
        Component(ota_adapter, "OTA Adapter", "Implements IOTAManager")
    }

    Container_Boundary(sdk, "Robot SDK (Facade)") {
        Component(robot_facade, "Robot Facade", "High-level API: robot.head.lookAt(), robot.arm.wave()")
        Component(head_api, "Head API", "lookAt, home, nod, shake, blink, scan")
        Component(arm_api, "Arm API", "wave, point, grab, release, reach, home")
        Component(tracks_api, "Tracks API", "moveForward, rotate, moveTo, stop, dock")
        Component(body_api, "Body API", "level, tilt, stow, stop")
        Component(speech_api, "Speech API", "say, listen, setVoice, setLanguage")
        Component(behavior_api, "Behavior API", "idle, followPerson, sleep, dance")
    }

    Rel(robot_facade, head_api, "Delegates to")
    Rel(robot_facade, arm_api, "Delegates to")
    Rel(robot_facade, tracks_api, "Delegates to")
    Rel(robot_facade, body_api, "Delegates to")
    Rel(robot_facade, speech_api, "Delegates to")
    Rel(robot_facade, behavior_api, "Delegates to")

    Rel(head_api, command_bus, "Sends MoveHeadCommand")
    Rel(arm_api, command_bus, "Sends MoveArmCommand")
    Rel(tracks_api, command_bus, "Sends MoveTracksCommand")
    Rel(body_api, command_bus, "Sends BodyCommand")
    Rel(speech_api, command_bus, "Sends SayTextCommand")
    Rel(behavior_api, command_bus, "Sends BehaviorCommand")

    Rel(command_bus, use_cases, "Routes to handler")
    Rel(query_bus, queries, "Routes to handler")

    Rel(use_cases, entities, "Creates/Updates")
    Rel(use_cases, domain_events, "Emits")
    Rel(use_cases, repositories, "Persists via interface")
    Rel(use_cases, services, "Uses domain logic")
    Rel(use_cases, policies, "Validates against rules")

    Rel(event_handlers, domain_events, "Handles")
    Rel(event_handlers, command_bus, "May emit commands")
    Rel(event_handlers, services, "Uses domain logic")

    Rel(mqtt_gateway, use_cases, "Receives commands via Gateway")
    Rel(ros2_gateway, use_cases, "Receives commands via Gateway")
    Rel(ws_gateway, use_cases, "Receives commands via Gateway")

    Rel(redis_event_bus, event_bus, "Implements")
    Rel(sqlite_repo, repositories, "Implements")
    Rel(file_config, config_svc, "Implements")
    Rel(pca9685_driver, hal, "Implements IServoDriver")
    Rel(motor_driver, hal, "Implements IMotorDriver")
    Rel(vl53l0x_driver, hal, "Implements IDistanceSensor")
    Rel(mpu6050_driver, hal, "Implements IIMU")
```

---

## Communication Flow - Command & Event

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant SDK as Robot SDK
    participant Gateway as CommunicationGateway
    participant MQTT as MQTT Broker
    participant Node2 as Node 2 (Head)
    participant EventBus as Event Bus
    participant Behavior as Behavior Engine
    participant Planner as Motion Planner

    User->>SDK: robot.head.lookAt(x, y, z)
    SDK->>Gateway: publish("openj5/v1/head/cmd", {command: "look_at", target: {...}})
    Gateway->>MQTT: Publish to topic
    MQTT->>Node2: Deliver to subscribed node
    Node2->>Node2: Validate command, check limits
    Node2->>Node2: Compute IK → Servo trajectories
    Node2->>Node2: Send PWM to PCA9685
    Node2->>MQTT: Publish "openj5/v1/head/evt" {event: "servo_moved", positions: {...}}
    MQTT->>Gateway: Deliver event
    Gateway->>EventBus: Publish DomainEvent(ServoMoved)
    EventBus->>Behavior: Notify FaceDetected → LookAt
    EventBus->>Planner: Notify for coordination
    Behavior->>SDK: Next high-level command
```

---

## Data Flow - Configuration

```mermaid
flowchart TD
    subgraph Config_Sources["Configuration Sources"]
        JSON[("JSON Files\nconfig/nodeX/")]
        YAML[("YAML Files\nconfig/common/")]
        DB[("Database\nPostgreSQL/SQLite")]
        ENV[("Environment Variables\nSecrets, Overrides")]
        REMOTE[("Config Service\nConsul/et/Etcd - Future")]
    end

    subgraph Config_Service["Configuration Service (Node 1)"]
        LOADER[Config Loader\nPriority: ENV > DB > YAML > JSON]
        VALIDATOR[Schema Validator\nJSON Schema / Pydantic]
        CACHE[Hot-Reload Cache\nWatchers + Invalidation]
        PROVIDER[IConfigProvider\nget(key), watch(key, callback)]
    end

    subgraph Consumers["Consumers (All Nodes)"]
        NODE1[Node 1: Robot Core]
        NODE2[Node 2: Head]
        NODE3[Node 3: Right Arm]
        NODE4[Node 4: Left Arm]
        NODE5[Node 5: Torso]
        NODE6[Node 6: Tracks]
        PLUGINS[Plugins]
        DRIVERS[Hardware Drivers]
    end

    JSON --> LOADER
    YAML --> LOADER
    DB --> LOADER
    ENV --> LOADER
    REMOTE -.-> LOADER

    LOADER --> VALIDATOR
    VALIDATOR --> CACHE
    CACHE --> PROVIDER

    PROVIDER --> NODE1
    PROVIDER --> NODE2
    PROVIDER --> NODE3
    PROVIDER --> NODE4
    PROVIDER --> NODE5
    PROVIDER --> NODE6
    PROVIDER --> PLUGINS
    PROVIDER --> DRIVERS
```

---

## State Machine - Per Node

```mermaid
stateDiagram-v2
    [*] --> BOOT: Power On
    BOOT --> INIT: HW Self-Test OK
    BOOT --> ERROR: HW Self-Test FAIL

    INIT --> READY: Config Loaded, Comms Established, Calibration OK
    INIT --> ERROR: Timeout or Config Invalid

    READY --> RUNNING: Start Command Received
    READY --> SHUTDOWN: Shutdown Command

    RUNNING --> ERROR: Fault Detected (Watchdog, Comm Loss, HW Error)
    RUNNING --> READY: Stop Command
    RUNNING --> SHUTDOWN: Shutdown Command

    ERROR --> RECOVERY: Auto-Recovery Triggered
    ERROR --> SHUTDOWN: Critical Fault / Manual Override

    RECOVERY --> READY: Recovery Successful
    RECOVERY --> ERROR: Recovery Failed
    RECOVERY --> SHUTDOWN: Abort Recovery

    SHUTDOWN --> [*]: Cleanup Complete, Power Off
```

---

## Deployment Diagram

```mermaid
C4Deployment
    title Deployment Diagram - OpenJ5 Physical Layout

    Deployment_Node(rpi4, "Raspberry Pi 4 8GB", "Raspberry Pi OS Lite 64-bit (Bookworm), NVMe USB3") {
        Container(docker, "Docker Engine", "Container Runtime") {
            Container(mosquitto, "Mosquitto MQTT", "Port 8883 (TLS)")
            Container(redis, "Redis Stack", "Port 6379 (Streams)")
            Container(postgres, "PostgreSQL 16", "Port 5432")
            Container(robot_core, "Robot Core Service", "Port 8080 (REST), 8081 (WS)")
            Container(ros2_bridge, "ROS 2 Bridge", "Port 9090 (WS)")
            Container(gazebo, "Gazebo Headless", "Port 11345 (gz-transport)")
        }
    }

    Deployment_Node(esp32_2, "ESP32-S3 Node 2: Head", "ESP-IDF 5.2 FreeRTOS") {
        Component(pca9685_2, "PCA9685 (I2C 0x40)", "16ch PWM")
        Component(servos_2, "6x Servos", "Neck Y/P/R, Eyes H/V, Eyelids")
        Component(leds_2, "WS2812 LED Strip", "GPIO 48")
        Component(display_2, "OLED/TFT Display", "SPI/I2C")
        Component(mics_2, "2x I2S MEMS Mic", "I2S")
        Component(sensors_2, "IMU, ToF, Temp", "I2C")
    }

    Deployment_Node(esp32_3, "ESP32-S3 Node 3: Right Arm", "ESP-IDF 5.2 FreeRTOS") {
        Component(pca9685_3, "PCA9685 (I2C 0x41)", "16ch PWM")
        Component(servos_3, "6x Servos", "Shoulder P/R/Rot, Elbow, Wrist, Gripper")
    }

    Deployment_Node(esp32_4, "ESP32-S3 Node 4: Left Arm", "ESP-IDF 5.2 FreeRTOS") {
        Component(pca9685_4, "PCA9685 (I2C 0x42)", "16ch PWM")
        Component(servos_4, "6x Servos", "Mirrored Right Arm")
    }

    Deployment_Node(esp32_5, "ESP32-S3 Node 5: Torso", "ESP-IDF 5.2 FreeRTOS") {
        Component(pca9685_5, "PCA9685 (I2C 0x43)", "16ch PWM")
        Component(servos_5, "4x Servos", "Torso Rot/Pitch, Battery Door, Expansion")
        Component(leds_5, "LED Strip + Fan PWM", "GPIO")
        Component(battery_5, "INA219 + DS18B20", "I2C/1-Wire")
        Component(sensors_5, "IMU, ToF, Proximity", "I2C")
    }

    Deployment_Node(esp32_6, "ESP32-S3 Node 6: Tracks", "ESP-IDF 5.2 FreeRTOS") {
        Component(l298n_6, "L298N Driver (firmware)", "LEDC PWM 1000 Hz / 10 bit + Dir")
        Component(motors_6, "2x DC Motor + Encoder", "GPIO Interrupts")
        Component(tof_6, "VL53L0X x2", "I2C (Mux)")
        Component(collision_6, "IR Bumpers", "GPIO")
    }

    Deployment_Node(esp32_7, "ESP32-S3 Node 7: Balance", "ESP-IDF 5.2 FreeRTOS") {
        Component(a4988_7, "A4988 (STEP/DIR/ENABLE)", "NEMA17")
        Component(imu_7, "MPU6050 (body)", "I2C + Madgwick")
    }

    Deployment_Node(network, "Network Infrastructure", "WiFi 5/6 + Ethernet") {
        Component(wifi_ap, "WiFi Access Point", "WPA3 Enterprise")
        Component(switch, "Managed Switch", "VLANs: Robot, Mgmt, IoT")
        Component(router, "Router/Firewall", "VPN, mTLS Termination")
    }

    Rel(rpi4, network, "Ethernet 1Gbps")
    Rel(esp32_2, network, "WiFi 2.4GHz (MQTT TLS)")
    Rel(esp32_3, network, "WiFi 2.4GHz (MQTT TLS)")
    Rel(esp32_4, network, "WiFi 2.4GHz (MQTT TLS)")
    Rel(esp32_5, network, "WiFi 2.4GHz (MQTT TLS)")
    Rel(esp32_6, network, "WiFi 2.4GHz (MQTT TLS)")
    Rel(esp32_7, network, "WiFi 2.4GHz (MQTT TLS)")

    Rel(mosquitto, esp32_2, "MQTT over TLS/mTLS")
    Rel(mosquitto, esp32_3, "MQTT over TLS/mTLS")
    Rel(mosquitto, esp32_4, "MQTT over TLS/mTLS")
    Rel(mosquitto, esp32_5, "MQTT over TLS/mTLS")
    Rel(mosquitto, esp32_6, "MQTT over TLS/mTLS")
    Rel(mosquitto, esp32_7, "MQTT over TLS/mTLS")
```

---

## Plugin Architecture

```mermaid
classDiagram
    class IPlugin {
        <<interface>>
        +id: string
        +version: string
        +dependencies: string[]
        +initialize(config: IConfigProvider): Result
        +start(): Result
        +stop(): Result
        +healthCheck(): HealthStatus
    }

    class PluginMetadata {
        +name: string
        +version: string
        +author: string
        +description: string
        +entryPoint: string
        +dependencies: Dependency[]
        +permissions: Permission[]
        +configSchema: JSONSchema
    }

    class PluginManager {
        +loadPlugin(path: string): Result~IPlugin~
        +unloadPlugin(id: string): Result
        +getPlugin(id: string): IPlugin?
        +getAllPlugins(): IPlugin[]
        +resolveDependencies(plugin: IPlugin): Result
        +enablePlugin(id: string): Result
        +disablePlugin(id: string): Result
    }

    class PluginRegistry {
        +register(metadata: PluginMetadata): void
        +unregister(id: string): void
        +getAvailable(): PluginMetadata[]
        +installFromRegistry(id: string, version: string): Result
    }

    IPlugin <|-- VisionPlugin
    IPlugin <|-- SpeechPlugin
    IPlugin <|-- AIPlugin
    IPlugin <|-- NavigationPlugin
    IPlugin <|-- MotionPlugin
    IPlugin <|-- HardwarePlugin
    IPlugin <|-- CommunicationPlugin

    PluginManager --> IPlugin: manages
    PluginManager --> PluginRegistry: queries
```

---

## Hardware Abstraction Layer (HAL)

```mermaid
classDiagram
    class IServoDriver {
        <<interface>>
        +initialize(config: ServoConfig): Result
        +setPosition(channel: int, angle: float, speed: float): Result
        +getPosition(channel: int): float
        +setSpeed(channel: int, speed: float): Result
        +home(channel: int): Result
        +enable(channel: int): Result
        +disable(channel: int): Result
        +calibrate(channel: int, min: int, max: int, home: int): Result
        +shutdown(): void
    }

    class IMotorDriver {
        <<interface>>
        +motor_names: list~str~
        +initialize(): None
        +set_velocity(motor: str, velocity: float): None
        +get_velocity(motor: str): float
        +stop_all(): None
        +brake_all(): None
        +shutdown(): None
    }

    class L298NDriver {
        +pwm_frequency_hz: float
        +pwm_resolution_bits: int
        +ramp_step: float
        +ramp_seconds: float
        +min_velocity: float
        +max_velocity: float
    }

    class MockMotorDriver {
        +last_schedule: dict
        +get_levels(motor: str): MotorLevels
    }

    class IDistanceSensor {
        <<interface>>
        +initialize(config: SensorConfig): Result
        +readDistance(): DistanceReading
        +startContinuous(intervalMs: int): Result
        +stopContinuous(): Result
        +setThreshold(threshold: float, callback: Fn): Result
    }

    class IIMU {
        <<interface>>
        +initialize(config: IMUConfig): Result
        +getOrientation(): Quaternion
        +getAngularVelocity(): Vector3
        +getLinearAcceleration(): Vector3
        +calibrate(): Result
        +setFusionAlgorithm(algo: FusionAlgo): Result
    }

    class IStepperDriver {
        <<interface>>
        +initialize(config: StepperConfig): Result
        +enable(): void
        +disable(): void
        +setPositionSteps(steps: int): Result
        +setVelocityStepsS(steps_s: float): Result
        +getPositionSteps(): int
        +getVelocityStepsS(): float
        +home(): Result
        +brake(): Result
        +shutdown(): void
    }

    class ICameraDriver {
        <<interface>>
        +initialize(config: CameraConfig): Result
        +capture(): ImageFrame
        +startStream(callback: Fn): Result
        +stopStream(): Result
        +setResolution(w: int, h: int): Result
        +setFPS(fps: int): Result
    }

    IServoDriver <|-- PCA9685Driver
    IServoDriver <|-- SoftPWMDriver
    IServoDriver <|-- ESP32LECDriver
    IServoDriver <|-- GazeboServoDriver

    IMotorDriver <|-- L298NDriver
    IMotorDriver <|-- MockMotorDriver
    IMotorDriver <|-- TB6612Driver
    IMotorDriver <|-- BTS7960Driver
    IMotorDriver <|-- ODriveDriver
    IMotorDriver <|-- GazeboMotorDriver

    IStepperDriver <|-- A4988StepperDriver
    IStepperDriver <|-- DRV8825Driver
    IStepperDriver <|-- TMC2209Driver
    IStepperDriver <|-- GazeboStepperDriver

    IDistanceSensor <|-- VL53L0XDriver
    IDistanceSensor <|-- UltrasonicDriver
    IDistanceSensor <|-- GazeboDistanceDriver

    IIMU <|-- MPU6050Driver
    IIMU <|-- ICM20948Driver
    IIMU <|-- GazeboIMUDriver

    ICameraDriver <|-- V4L2CameraDriver
    ICameraDriver <|-- IPCameraDriver
    ICameraDriver <|-- GazeboCameraDriver
```

> **Motor HAL — implemented shape (ADR-018, ADR-019, T-025 Phase 1).** The diagram
> above shows the port as actually implemented: signed normalized velocity
> (`set_velocity`/`get_velocity`, `[-1, +1]`), `motor_names`, `stop_all` (coast),
> `brake_all` (hold) and idempotent `shutdown`. The value mapping is factored
> into the pure helpers `clamp_velocity`, `motor_levels` (`MotorLevels`) and
> `ramp_schedule` in `src/hardware/hal/motor.py`, mirrored 1:1 by
> `firmware/common/include/hal/motor_logic.hpp`. Per ADR-019 the real `L298NDriver`
> is the **ESP32-S3 firmware** adapter (`firmware/common/drivers/l298n_driver.cpp`,
> LEDC 1000 Hz / 10 bit); the host `L298NDriver` (and its `L298NMotor` channel) was
> retired and only the CI-safe `MockMotorDriver` remains on the host as the
> Digital-Twin adapter. The C++ port (`motor_driver.hpp` + `motor_logic.hpp`,
> ADR-018) is delivered; the dedicated Python↔C++ parity test is the remainder of
> T-032. The richer interface sketched in earlier revisions — `setPID`,
> `enable`/`disable`, `getOdometry` returning `Result` — is the **future
> production/firmware contract** (encoders, PID, odometry belong to the Node 6
> ESP32 firmware and a dedicated encoder/controller port), **not** this port; it
> is intentionally out of scope (ADR-018 §2).

---

## Security Architecture

```mermaid
flowchart TD
    subgraph Trust_Zone["Trusted Zone (Robot Internal)"]
        CA[("Private CA\nRoot Certificate")]
        NODE_CERTS["Node Certificates\n(per ESP32 + RPi)"]
        MQTT_TLS["MQTT over TLS 1.3\nmTLS Required"]
        API_JWT["REST API + WS\nJWT RS256"]
        OTA_SIGN["OTA Signing\nECDSA P-256"]
    end

    subgraph Untrusted_Zone["Untrusted Zone (External)"]
        USER[User / Web UI]
        FLEET[Fleet Manager]
        TELEOP[Teleop Client]
    end

    CA --> NODE_CERTS
    NODE_CERTS --> MQTT_TLS
    CA --> API_JWT
    CA --> OTA_SIGN

    USER -->|HTTPS + JWT| API_JWT
    FLEET -->|mTLS| MQTT_TLS
    TELEOP -->|WSS + JWT| API_JWT

    MQTT_TLS -.->|Encrypted| ESP32_NODES[("All 6 ESP32-S3 Nodes")]
    API_JWT -.->|Encrypted| ROBOT_CORE[("Robot Core (RPi4)")]
    OTA_SIGN -.->|Signed Firmware| ESP32_NODES
```

---

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| ADR-001 | Hexagonal Architecture for Core Domain | Accepted | 2026-07-15 |
| ADR-002 | 6-Node Distributed Architecture | Accepted | 2026-07-15 |
| ADR-003 | Communication Gateway Pattern (Multi-Protocol) | Accepted | 2026-07-15 |
| ADR-004 | Event-Driven Architecture with Central Event Bus | Accepted | 2026-07-15 |
| ADR-005 | Hardware Abstraction Layer (HAL) for All Drivers | Accepted | 2026-07-15 |
| ADR-006 | Robot SDK as Single Facade for Applications | Accepted | 2026-07-15 |
| ADR-007 | Plugin Architecture for All Features | Accepted | 2026-07-15 |
| ADR-008 | Configuration-Driven Development (JSON/YAML Only) | Accepted | 2026-07-15 |
| ADR-009 | State Machine per Node (BOOT→INIT→READY→RUNNING→ERROR→RECOVERY→SHUTDOWN) | Accepted | 2026-07-15 |
| ADR-010 | Digital Twin Native (Gazebo/Isaac Sim) | Accepted | 2026-07-15 |
| ADR-011 | OTA with Signed Firmware and Rollback | Accepted | 2026-07-15 |
| ADR-012 | FreeCAD Parametric CAD with Spreadsheet Configuration | Accepted | 2026-07-15 |
| ADR-013 | Security: mTLS, JWT, Signed OTA, Fail-Safe | Accepted | 2026-07-15 |
| ADR-014 | Python for Robot Core, C++ for Firmware | Accepted | 2026-07-15 |
| ADR-015 | MQTT as Primary Transport Protocol | Accepted | 2026-07-15 |
| ADR-016 | Raspberry Pi OS Lite 64-bit (Bookworm) + NVMe-over-USB3 for Node 1 | Accepted | 2026-08-25 |
| ADR-017 | Node 7 Balance Controller (NEMA17 + A4988 + MPU6050) | Accepted | 2026-09-21 |
| ADR-018 | Motor HAL Port (`IMotorDriver`): Contract Shape, Placement and Python↔C++ Parity | Accepted | 2026-10-09 |
| ADR-019 | Standardize All Nodes on ESP32-S3 (the Raspberry Pi Is Brain Only) | Accepted | 2026-10-09 |

---

## Quality Gates (Automated in CI/CD)

| Gate | Tool | Threshold |
|------|------|-----------|
| **Build** | CMake/ESP-IDF/Poetry | Must pass |
| **Unit Tests** | pytest/Unity/Catch2 | >90% coverage (core), >80% (plugins) |
| **Integration Tests** | pytest + testcontainers | All pass |
| **Static Analysis** | ruff/mypy/cppcheck/clang-tidy | Zero errors, zero critical warnings |
| **Architecture Tests** | ArchUnit/custom | No layer violations, no circular deps |
| **Documentation Check** | Custom script | All modified files have doc updates |
| **ADR Check** | Custom script | Architectural changes have ADR |
| **Security Scan** | bandit/trivy/semgrep | Zero critical/high |
| **Dependency Check** | pip-audit/cargo-audit | Zero known vulnerabilities |
| **Simulation Tests** | Gazebo + pytest | Parity with real robot tests |

---

## Technology Stack Summary

| Layer | Technology | Version |
|-------|------------|---------|
| **Core Language (Robot Core)** | Python | 3.11+ |
| **Core Language (Firmware)** | C++ | C++20 (ESP-IDF) |
| **SDK Languages** | Python, C++, TypeScript | 3.11+, 20, 5.0+ |
| **Message Transport** | MQTT (Mosquitto/EMQX) | 5.0 / 2.0 |
| **Alternative Transport** | ROS 2 (Fast DDS/Cyclone) | Humble/Iron |
| **Event Bus** | Redis Streams / NATS | 7.2+ / 2.10+ |
| **Database** | SQLite (dev) / PostgreSQL | 3.45+ / 16+ |
| **Config** | JSON / YAML / Pydantic | - |
| **Web Framework** | FastAPI + Uvicorn | 0.110+ / 0.30+ |
| **Containerization** | Docker + Compose | 26+ / 2.27+ |
| **CAD** | FreeCAD | 0.21+ |
| **Electronics** | KiCad | 8.0+ |
| **Simulation** | Gazebo Garden / Isaac Sim | Harmonic / 2023.1+ |
| **CI/CD** | GitHub Actions | - |
| **Testing** | pytest, Unity, Catch2, Gazebo | - |
| **Observability** | Prometheus, Grafana, OpenTelemetry | - |