# GOALS

## Obiettivi Strategici (Livello Progetto)

### G1 - Piattaforma Robotica Professionale Open Source
Creare una piattaforma robotica completa (HW + FW + SW + CAD + Docs) che sia riferimento per robotica open source professionale, non hobbistica.

**KPI**: Repository con >500 stelle GitHub, >20 contributor, >10 fork attivi entro Anno 2.

### G2 - Architettura che Dura 10+ Anni
Progettare un'architettura che sopravviva a: cambio MCU (ESP32 → ESP32-P4 / STM32 / RP2040 / RPi Pico), cambio protocolli (MQTT → ROS 2 / Zenoh / DDS / gRPC), cambio sensori/attuatori, cambio team, cambio AI framework.

**KPI**: Zero breaking changes architetturali per 5 anni; migrazione MCU/protocollo in < 2 settimane.

### G3 - Digital Twin Nativo
Il simulatore (Gazebo / Isaac Sim / Webots / MuJoCo) deve usare le **identiche API** del robot reale. Stesso Robot SDK, stesso HAL, stesso Event Bus. Switch reale ↔ simulato = 1 riga di config.

**KPI**: Stesso test suite passa su robot reale e simulatore senza modifiche.

### G4 - Robot SDK come Facciata Unica
Tutte le applicazioni (utenti, ricercatori, AI, behavior tree, teleop) usano **solo** `robot.head.lookAt()`, `robot.rightArm.wave()`, `robot.tracks.moveForward()`. Mai topic MQTT diretti, mai comandi servo diretti.

**KPI**: 100% delle applicazioni esempio usano solo Robot SDK. Zero import MQTT/ROS in app code.

### G5 - Tutto Configurabile, Nulla Hardcoded
Ogni valore (velocità servo, PID, limiti, topic MQTT, IP, porte, PIN GPIO, PID motori, soglie sensori) proviene da configurazione esterna (JSON/YAML/Config Service/DB). Zero magic numbers nel codice.

**KPI**: `grep -r "= [0-9]" src/` ritorna 0 risultati (eccetto costanti matematiche π, 180, 360, ecc.).

### G6 - Hardware Abstraction Layer Completa
Nessun codice applicativo tocca PCA9685, L298N, VL53L0X, MPU6050, I2S, SPI, I2C direttamente. Solo interfacce: `IServoDriver`, `IMotorDriver`, `IDistanceSensor`, `IIMU`, `IAudioInput`, `IDisplay`, `ILedStrip`.

**KPI**: Sostituzione PCA9685 → PCA9685-2 / PWM soft / ESP32 LEDC / STM32 PWM richiede solo nuovo driver, **zero cambi** in application code.

### G7 - Plugin Architecture per Tutto
Vision, Speech, AI, Navigation, Battery, Face Recognition, Camera, Lidar, Motion, Hardware, Communication = **Plugin**. Caricabili dinamicamente, versionati, dipendenze dichiarate, abilitabili/disabilitabili via config.

**KPI**: Aggiungere un nuovo modello AI (es. YOLOv10 → YOLOv11) = nuovo plugin, zero touch al core.

### G8 - Digital Twin per Sviluppo e CI/CD
Tutti i test (unit, integration, hardware-in-loop, simulation) girano in CI/CD su simulatore. Il robot reale serve solo per hardware-in-loop e validation finale.

**KPI**: Pipeline CI/CD completa (build → unit test → integration test sim → deploy staging → hardware-in-loop) < 30 min.

### G9 - Documentazione Continua e Obbligatoria
La documentazione non è un task separato: è parte del codice. Ogni PR che aggiunge/modifica codice **deve** aggiornare: README, API.md, ARCHITECTURE.md, CONFIGURATION.md, ADR (se architetturale), CHANGELOG.md, PROJECT_STATUS.md.

**KPI**: CI fallisce se mancano aggiornamenti doc per file modificati.

### G10 - Quality Gates Automatici
Ogni commit/PR passa: Build → Unit Test → Integration Test (sim) → Lint → Type Check → Doc Check → ADR Check → Architecture Review (automatizzato) → Deploy.

**KPI**: Zero merge direct to main. 100% PR passano quality gates.

---

## Obiettivi Tecnici per Nodo (Anno 1)

### Nodo 1 - Raspberry Pi 4 8GB (Robot Core)
| Obiettivo | Descrizione | Done Criteria |
|-----------|-------------|---------------|
| G1.1 | OS Base: Raspberry Pi OS Lite 64-bit (Bookworm) + Docker, boot NVMe USB3 (ADR-016) | Bootable, Docker, composes up |
| G1.2 | ROS 2 Humble/Iron + rosbridge | `ros2 topic list` funziona, bridge WS attivo |
| G1.3 | MQTT Broker (Mosquitto/EMQX) + Auth + ACL | Pub/sub da ESP32 funziona con auth |
| G1.4 | Robot Core Service (Config, Logging, DB, Scheduler, Plugin Manager) | Service up, REST API risponde, plugin load |
| G1.5 | REST API + WebSocket Server | OpenAPI spec, Swagger UI, WS real-time |
| G1.6 | Digital Twin Bridge (Gazebo/Isaac Sim ↔ Robot Core) | Stesso comando SDK muove sim e reale |
| G1.7 | OTA Manager per 5× ESP32 | OTA push da UI/API funziona su tutti i nodi |
| G1.8 | Configuration Service (File + DB + Hot Reload) | Cambio config → hot reload senza restart |
| G1.9 | Event Bus (Redis Streams / NATS / custom) | Pub/sub typed events, dead letter, replay |
| G1.10 | State Machine Orchestrator (tutti i nodi) | Tutti i 6 nodi: BOOT→INIT→READY→RUNNING |

### Nodo 2 - ESP32-S3 Head Controller
| Obiettivo | Descrizione | Done Criteria |
|-----------|-------------|---------------|
| G2.1 | Firmware base: FreeRTOS + ESP-IDF + MQTT + OTA | Boot, MQTT connect, OTA receive |
| G2.2 | PCA9685 Driver (IServoDriver impl) | 16 canali PWM configurabili da JSON |
| G2.3 | 6 Servi Testa: Neck Yaw/Pitch/Roll, Eyes H/V, Eyelids | Movimenti fluidi, limiti, home, speed/accel da config |
| G2.4 | LED Driver (WS2812 / PWM) | Pattern, colori, brightness da config |
| G2.5 | Display Driver (OLED/TFT/LCD via SPI/I2C) | Testo, immagini, animazioni da config |
| G2.6 | Audio Input (I2S MEMS Mic x2) | Stream audio → MQTT/RTP, VAD base |
| G2.7 | Sensori locali (IMU testa, ToF, temperatura) | Dati pubblicati su Event Bus |
| G2.8 | State Machine completa | BOOT→INIT→READY→RUNNING→ERROR→RECOVERY→SHUTDOWN |
| G2.9 | Motion Primitives (LookAt, Nod, Shake, Blink, Scan) | Comandi logici → traiettorie servo |

### Nodo 3 - ESP32-S3 Right Arm Controller
| Obiettivo | Descrizione | Done Criteria |
|-----------|-------------|---------------|
| G3.1 | Firmware base identico a Nodo 2 | Stesso template, build system condiviso |
| G3.2 | PCA9685 Driver (condiviso con Nodo 2) | Stesso driver, config diversa |
| G3.3 | 6 Servi Braccio DX: Shoulder P/R/Rot, Elbow, Wrist, Gripper | Cinematica diretta/inversa base, limiti, collision avoidance base |
| G3.4 | Motion Primitives: Wave, Point, Grab, Release, Home, Reach | Comandi logici → traiettorie |

### Nodo 4 - ESP32-S3 Left Arm Controller
| Obiettivo | Descrizione | Done Criteria |
|-----------|-------------|---------------|
| G4.1 | Identico a Nodo 3 (specchio) | Stesso firmware, config mirrored |

### Nodo 5 - ESP32 Torso Controller
| Obiettivo | Descrizione | Done Criteria |
|-----------|-------------|---------------|
| G5.1 | Firmware base template | Stesso template nodi ESP32 |
| G5.2 | 4 Servi: Torso Rot, Torso Pitch, Battery Door, Expansion | Movimenti coordinati con braccia/head |
| G5.3 | LED Strip + Fan Control (PWM) | Pattern LED, fan curve da config |
| G5.4 | Battery Monitor (INA219/ADC) + Temperature (DS18B20/ADC) | Telemetria pubblicata su Event Bus |
| G5.5 | Sensori espansione (IMU torso, ToF, prossimità) | Dati su Event Bus |

### Nodo 6 - ESP32 Track Controller
| Obiettivo | Descrizione | Done Criteria |
|-----------|-------------|---------------|
| G6.1 | Firmware base template | Stesso template |
| G6.2 | Motor Driver Abstraction (IMotorDriver) | L298N impl + interfaccia per TB6612/BTS7960/ODrive |
| G6.3 | 2 Motori DC + Encoder (odometria) | Odometria differenziale pubblicata |
| G6.4 | IMU (MPU6050/ICM20948) | Fuso con odometria → pose 2D |
| G6.5 | ToF (VL53L0X/VL53L1X) anteriore/posteriore | Distance pubblicata, anticollisione |
| G6.6 | Sensori anticollisione (IR/bumper) | Emergency stop su Event Bus |
| G6.7 | Motion Primitives: MoveForward, Rotate, Arc, Stop, Dock | Comandi logici → PID motori |

---

## Obiettivi Trasversali

### Architettura & Qualità
| ID | Obiettivo | Metrica |
|----|-----------|---------|
| T1 | Hexagonal Architecture (Ports & Adapters) | Core domain zero dipendenze esterne |
| T2 | Dependency Injection ovunque | Zero `new` di servizi in domain code |
| T3 | Event Sourcing per stati critici | Event store per robot state, battery, errors |
| T4 | CQRS per comandi/queries | Command Bus + Query Bus separati |
| T5 | Circuit Breaker / Retry / Timeout su Communication Gateway | Resilienza rete dimostrata |
| T6 | Structured Logging (JSON, structured, correlated) | Log aggregabili, trace ID correlati |
| T7 | Metrics (Prometheus) + Tracing (OpenTelemetry) | Dashboard Grafana funzionale |
| T8 | Security: mTLS MQTT, JWT REST, signed OTA | Penetration test base passato |

### CAD & Meccanica
| ID | Obiettivo | Metrica |
|----|-----------|---------|
| M1 | FreeCAD parametrico completo | Tutti i parametri in spreadsheet, assembly parametrici |
| M2 | BOM automatico da CAD | Script estrae BOM + costi + link fornitori |
| M3 | STL generati parametricamente | `make stl` genera tutti i pezzi per taglia scelta |
| M4 | Assemblaggio simulato (cinematica) | Verifica interferenze, range movimento in FreeCAD |
| M5 | Documentazione assemblaggio (PDF/HTML) | Istruzioni passo-passo con foto/render |

### Elettronica
| ID | Obiettivo | Metrica |
|----|-----------|---------|
| E1 | Schemi KiCad per tutti e 6 i nodi | Schemi completi, ERC/DNC passati |
| E2 | PCB per Nodi 2-6 (ESP32 + PCA9685 + connettori) | PCB ordinabili, BOM generato |
| E3 | Cablaggio documentato (pinout, wire gauge, connettori) | Harness diagram + wire list |
| E4 | Power budget calcolato e verificato | Current draw < budget batteria per 2h+ |
| E5 | Schema alimentazione (batteria, BMS, 5V/3.3V regolatori) | Schema completo, testato |

### Simulazione & Digital Twin
| ID | Obiettivo | Metrica |
|----|-----------|---------|
| S1 | URDF/XACRO parametrico da FreeCAD | Export automatico FreeCAD → URDF |
| S2 | Gazebo Garden / Isaac Sim model | Robot si muove in sim con ROS 2 control |
| S3 | Plugin HAL per simulatore | Stesso `IServoDriver` → Gazebo plugin |
| S4 | CI/CD testa su simulatore | Pipeline GitHub Actions gira test su Gazebo |

---

## Obiettivi Futuri (Post-MVP - Anno 2+)

| Area | Obiettivi |
|------|-----------|
| **AI/Vision** | YOLOv10/11, Segment Anything, Depth estimation, Pose estimation, Face recognition, Gesture recognition |
| **Speech** | Whisper.cpp (STT), Piper/Coqui (TTS), Wake word, Voice activity detection, Speaker diarization |
| **Behavior** | Behavior Trees (BehaviorTree.CPP), Emotional state machine, Social navigation, Human-robot interaction |
| **Navigation** | Nav2 + SLAM (Cartographer/Slam Toolbox), Localization (AMCL), Global/Local planner, Costmaps 2D/3D |
| **Manipolazione** | MoveIt 2, Pick & Place, Grasp planning, 7 DoF arms (upgrade), Force/torque sensing, Compliance control |
| **Sensori** | LIDAR 2D/3D (RPLIDAR/Velodyne/Ouster), Depth camera (RealSense/ZED/OAK-D), Tactile sensors, Force sensors |
| **Comunicazione** | ROS 2 DDS (Fast DDS/Cyclone), Zenoh, gRPC, WebRTC per teleop, Matter/Thread per IoT |
| **Fleet** | Multi-robot coordination, Fleet manager, Shared map, Task allocation, Cloud robotics |
| **Sicurezza** | ISO 13482 / ISO 10218 compliance path, Safety-rated LiDAR, E-stop wired + wireless, Risk assessment |
| **Certificazione** | CE marking path, FCC/CE per elettronica, Open Source Hardware Association certification |

---

## Prioritizzazione (MoSCoW - Anno 1)

| Must Have | Should Have | Could Have | Won't Have (Anno 1) |
|-----------|-------------|------------|---------------------|
| 6 nodi HW funzionanti | Digital Twin Gazebo | Isaac Sim support | LIDAR / SLAM / Nav2 |
| Communication Gateway (MQTT) | ROS 2 Bridge | Zenoh / gRPC | Braccia 7 DoF |
| Event Bus | Plugin Manager (core) | Plugin marketplace | Force/torque sensing |
| Robot SDK (API complete) | OTA Manager (tutti nodi) | WebRTC teleop | Tactile sensors |
| HAL (Servo, Motor, Sensor) | Config Service (hot reload) | Multi-robot | Fleet management |
| State Machine (tutti nodi) | Structured Logging | OpenTelemetry | Safety certification |
| FreeCAD parametrico (v1) | BOM auto-generate | Assembly simulation | ISO 13482 |
| PCB Nodi 2-6 | Power budget verified | Harness docs | CE marking |
| Unit + Integration Test >80% | CI/CD pipeline | Simulation test in CI | Multi-robot |
| Docs complete (100% API) | ADR per ogni decisione | Architecture diagrams | Plugin marketplace |