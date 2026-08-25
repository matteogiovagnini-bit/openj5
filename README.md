# OpenJ5

**La Piattaforma Robotica Open Source per l'Era dell'AI Embodiment**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Architecture: Hexagonal](https://img.shields.io/badge/Architecture-Hexagonal-blue.svg)](https://alistair.cockburn.us/hexagonal-architecture/)
[![Status: In Development](https://img.shields.io/badge/Status-In%20Development-orange.svg)]()

---

## 🎯 Visione

OpenJ5 è una **piattaforma robotica professionale open source** ispirata a Johnny 5 (Corto Circuito), progettata per durare 10+ anni senza riscritture architetturali. È completamente stampabile in 3D, parametrica, documentata e basata su architettura distribuita a 6 nodi.

> **"Non costruiamo un robot. Costruiamo la piattaforma che rende banale costruire robot."**

---

## 🏗️ Architettura a 6 Nodi

| Nodo | Hardware | Responsabilità |
|------|----------|----------------|
| **Nodo 1** | Raspberry Pi 4 8GB | Robot Core: AI, Vision, Speech, Planning, Behavior, MQTT Broker, REST API, Digital Twin, OTA, Plugin Manager |
| **Nodo 2** | ESP32-S3 | Head Controller: 6 Servi (Neck Yaw/Pitch/Roll, Eyes H/V, Eyelids), LED, Display, Microfoni, Sensori locali |
| **Nodo 3** | ESP32-S3 | Right Arm Controller: 6 Servi (Shoulder P/R/Rot, Elbow, Wrist, Gripper) |
| **Nodo 4** | ESP32-S3 | Left Arm Controller: Identico al destro (mirrored) |
| **Nodo 5** | ESP32 | Torso Controller: 4 Servi (Torso Rot/Pitch, Battery Door, Expansion), LED, Fan, Battery Monitor, Sensori |
| **Nodo 6** | ESP32 | Track Controller: 2 Motori DC + Encoder (L298N), IMU, ToF, Sensori anticollisione |

---

## 🧱 Principi Architetturali (Non Negoziali)

| Principio | Descrizione |
|-----------|-------------|
| **Hexagonal Architecture** | Core domain zero dipendenze esterne. Ports & Adapters per tutto. |
| **Dependency Injection** | Zero `new` di servizi nel domain code. Composition root only. |
| **Event-Driven Architecture** | Event Bus centrale. `FaceDetected` → `BehaviorEngine` → `MotionPlanner` → `HeadController`. Zero coupling diretto. |
| **Hardware Abstraction Layer Totale** | `IServoDriver`, `IMotorDriver`, `IDistanceSensor`, `IIMU`, `ICameraDriver`, `IAudioInput`, `IDisplay`, `ILedStrip`. Zero codice applicativo tocca PCA9685, L298N, VL53L0X, ecc. |
| **Communication Gateway** | Nessun modulo usa MQTT direttamente. Solo `ICommunicationGateway`. Implementazioni: MQTT, ROS 2, WebSocket, Serial, BLE, CAN, Zenoh, gRPC. |
| **Robot SDK come Facciata Unica** | `robot.head.lookAt()`, `robot.rightArm.wave()`, `robot.tracks.moveForward()`. Mai topic MQTT o angoli servo nel codice applicativo. |
| **Plugin Architecture** | Vision, Speech, AI, Navigation, Battery, Face Recognition, Camera, Lidar, Motion, Hardware, Communication = Plugin. Caricabili dinamicamente. |
| **Configuration-Driven Everything** | Tutto in JSON/YAML. Zero magic numbers. `grep -r "= [0-9]" src/` → 0 risultati. |
| **State Machine per Nodo** | BOOT → INIT → READY → RUNNING → ERROR → RECOVERY → SHUTDOWN su ogni nodo. |
| **Digital Twin Nativo** | Stesso SDK controlla robot reale E simulatore (Gazebo/Isaac Sim/Webots). Switch = 1 riga di config. |
| **OTA per Tutti gli ESP32** | Firmware firmato, verifica signature su flash, rollback automatico. |

---

## 📁 Struttura Repository

```
OpenJ5/
├── src/
│   ├── core/                    # Hexagonal Core (Domain, Application, Infrastructure)
│   │   ├── domain/              # Entities, Value Objects, Domain Events, Repository Interfaces
│   │   ├── application/         # Use Cases, Commands, Queries, Event Handlers
│   │   └── infrastructure/      # Adapters: MQTT, ROS2, DB, Config, Logging, OTA
│   ├── plugins/                 # Plugin System (Vision, Speech, AI, Navigation, etc.)
│   ├── sdk/                     # Robot SDK - Facciata pubblica ad alto livello
│   ├── gateway/                 # Communication Gateway (Ports & Adapters)
│   ├── eventbus/                # Event Bus Implementation
│   ├── statemachine/            # State Machine Framework
│   ├── config/                  # Configuration Service
│   ├── ota/                     # OTA Manager
│   ├── hardware/
│   │   ├── hal/                 # Hardware Abstraction Layer (Interfaces)
│   │   └── drivers/             # Concrete Drivers (PCA9685, L298N, VL53L0X, etc.)
│   └── firmware/                # ESP-IDF Firmware per 6 nodi
├── config/                      # File di configurazione JSON per nodo
├── docs/                        # Documentazione completa (obbligatoria per ogni PR)
│   ├── adr/                     # Architecture Decision Records
│   ├── architecture/
│   ├── api/
│   ├── configuration/
│   ├── hardware/
│   ├── electronics/
│   ├── firmware/
│   ├── mechanics/
│   ├── simulation/
│   ├── tests/
│   ├── deployment/
│   └── security/
├── cad/
│   ├── freecad/                 # FreeCAD parametrico (macro, parti, assiemi, spreadsheet)
│   ├── stl_output/              # STL generati parametricamente
│   └── urdf_export/             # URDF/XACRO esportati da FreeCAD
├── electronics/
│   ├── kicad/                   # Schemi e PCB KiCad per 6 nodi
│   ├── bom/                     # BOM automatico
│   └── harness/                 # Cablaggio documentato
├── simulation/
│   ├── gazebo/                  # Gazebo Garden / Harmonic models
│   ├── isaac_sim/               # NVIDIA Isaac Sim
│   ├── webots/                  # Webots
│   ├── mujoco/                  # MuJoCo
│   └── digital_twin/            # Digital Twin Bridge
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── hardware/
│   └── simulation/
├── scripts/
│   ├── build/
│   ├── deploy/
│   ├── test/
│   └── generate/
├── .github/workflows/           # CI/CD Pipeline
└── .vscode/                     # Configurazione VS Code
```

---

## 🚀 Quick Start

### Prerequisiti

- **Raspberry Pi 4 8GB** con Raspberry Pi OS Lite 64-bit (Bookworm) — ADR-016 — boot da NVMe USB3 consigliato
- **5× ESP32-S3/ESP32** (DevKit o custom PCB)
- **Docker** + **Docker Compose**
- **Python 3.11+** (per SDK e tooling)
- **FreeCAD 0.21+** (per CAD parametrico)
- **KiCad 8.0+** (per elettronica)

### Setup Robot Core (Nodo 1 - Raspberry Pi)

```bash
# Guida completa: docs/deployment/DEPLOYMENT.md
# Automazione: scripts/deploy/bootstrap_rpi4.sh

git clone https://github.com/matteogiovagnini-bit/openj5.git
cd openj5/firmware/node1_robot_core/docker

bash secrets/generate.sh          # password db/grafana + chiave OTA
bash certs/generate.sh --quiet    # CA + certificati mTLS
docker compose up -d

# Verifica servizi
curl -fk https://localhost:8080/health
```

### Setup Firmware ESP32 (Nodi 2-6)

```bash
# Installa ESP-IDF v5.2+
cd firmware/common
./install_esp_idf.sh

# Configura ogni nodo
cd ../node2_head
idf.py menuconfig  # Imposta WiFi, MQTT broker, node ID
idf.py build flash monitor
```

### Genera STL da FreeCAD (Parametrico)

```bash
cd cad/freecad
freecadcmd macros/generate_all_stl.py --config spreadsheets/openj5_params.FCStd
# Output in ../stl_output/
```

### Simulazione (Digital Twin)

```bash
cd simulation/gazebo
./launch_sim.sh --robot-config config/sim_robot.json
# Stesso SDK controlla simulatore e robot reale
```

---

## 🤖 Robot SDK - Esempi

```python
from openj5.sdk import Robot

# Inizializzazione (config determina: reale vs simulato)
robot = Robot.from_config("config/robot.json")

# API Alto Livello - Mai topic MQTT diretti!
robot.head.look_at(x=0.5, y=0.0, z=1.2)      # Guarda punto nello spazio 3D
robot.head.home()                             # Posizione home
robot.head.nod()                              # Annuisce
robot.head.shake()                            # Scuote testa
robot.head.blink()                            # Ammicca

robot.right_arm.wave()                        # Saluta
robot.right_arm.grab()                        # Chiudi pinza
robot.right_arm.release()                     # Apri pinza
robot.right_arm.reach(x=0.3, y=0.2, z=0.5)    # Raggiungi punto (IK base)

robot.left_arm.point_at(x=1.0, y=0.0, z=1.5)  # Indica

robot.tracks.move_forward(speed=0.5)          # Avanti
robot.tracks.rotate(angular_vel=0.3)          # Ruota
robot.tracks.move_to(x=2.0, y=1.0, theta=0.0) # Naviga a posa (richiede Navigation Plugin)

robot.speech.say("Ciao! Sono OpenJ5.")        # TTS
robot.speech.listen()                         # STT → restituisce testo

robot.behavior.idle()                         # Comportamento idle
robot.behavior.follow_person()                # Segui persona (richiede Vision Plugin)
```

```cpp
// C++ SDK (per firmware/performance)
#include <openj5/sdk/Robot.hpp>

auto robot = openj5::sdk::Robot::fromConfig("config/robot.json");

robot.head().lookAt({0.5, 0.0, 1.2});
robot.rightArm().wave();
robot.tracks().moveForward(0.5);
```

---

## 🔌 Plugin System

Tutto è un plugin. Il core fornisce solo infrastruttura.

| Categoria | Plugin Core | Plugin Esterni (Esempi) |
|-----------|-------------|-------------------------|
| **Vision** | `CameraPlugin` | `YoloDetectionPlugin`, `FaceRecognitionPlugin`, `DepthEstimationPlugin` |
| **Speech** | `AudioInputPlugin`, `AudioOutputPlugin` | `WhisperSttPlugin`, `PiperTtsPlugin`, `WakeWordPlugin` |
| **AI** | `InferenceEnginePlugin` | `LlmPlugin`, `VlmPlugin`, `BehaviorTreePlugin` |
| **Navigation** | `OdometryPlugin` | `SlamToolboxPlugin`, `Nav2Plugin`, `GlobalPlannerPlugin` |
| **Motion** | `MotionPrimitivesPlugin` | `MoveIt2Plugin`, `GraspPlanningPlugin`, `IkSolverPlugin` |
| **Hardware** | `ServoDriverPlugin`, `MotorDriverPlugin` | `DynamixelDriverPlugin`, `OdriveDriverPlugin` |
| **Communication** | `MqttGatewayPlugin` | `Ros2GatewayPlugin`, `ZenohGatewayPlugin`, `WebSocketGatewayPlugin` |

```json
// config/plugins.json - Abilita/disabilita via config
{
  "plugins": {
    "vision": { "enabled": true, "implementation": "YoloDetectionPlugin", "version": "1.2.0" },
    "speech_stt": { "enabled": true, "implementation": "WhisperCppPlugin" },
    "navigation": { "enabled": false },
    "ai_llm": { "enabled": true, "implementation": "LlamaCppPlugin", "model": "models/llama-3-8b-q4.gguf" }
  }
}
```

---

## 📐 CAD Parametrico (FreeCAD)

Tutto il CAD è generato parametricamente. Cambi un parametro → rigeneri tutto.

```python
# cad/freecad/spreadsheets/openj5_params.FCStd (Spreadsheet FreeCAD)
# Parametri principali:
# - RobotHeight, TorsoHeight, ArmLength, HeadSize
# - ServoModels (modello per ogni giunto)
# - WallThickness, PrintOrientation, Tolerance
# - BatteryType, ElectronicsLayout
```

```bash
# Genera tutto: STL, BOM, URDF, Cablaggi
cd cad/freecad
freecadcmd macros/generate_all.py
# Output:
# ../stl_output/          # STL per stampa 3D
# ../urdf_export/         # URDF/XACRO per ROS2/Gazebo
# ../../electronics/bom/  # BOM con costi e link fornitori
# ../../electronics/harness/ # Diagrammi cablaggio
```

---

## ⚡ Comunicazione

### Communication Gateway Pattern

```python
# Il codice applicativo USA SOLO l'interfaccia
from openj5.gateway import CommunicationGateway

gateway = CommunicationGateway.get_instance()

# Pubblica comando logico (non angoli servo!)
gateway.publish("openj5/v1/head/cmd", {
    "command": "look_at",
    "target": {"x": 0.5, "y": 0.0, "z": 1.2},
    "speed": 0.8
})

# Sottoscrivi eventi
gateway.subscribe("openj5/v1/head/events", handle_head_event)
```

### Implementazioni Supportate

| Protocollo | Implementazione | Uso |
|------------|-----------------|-----|
| **MQTT** | `MqttGateway` (Mosquitto/EMQX) | Default, basso overhead |
| **ROS 2** | `Ros2Gateway` (Fast DDS/Cyclone) | Integrazione ecosistema ROS |
| **WebSocket** | `WebSocketGateway` | Web UI, teleop remoto |
| **Serial** | `SerialGateway` | Debug, bootstrap |
| **BLE** | `BleGateway` | Provisioning, mobile app |
| **CAN** | `CanGateway` | Real-time, automotive |
| **Zenoh** | `ZenohGateway` | Edge computing, low latency |
| **gRPC** | `GrpcGateway` | Service-to-service, streaming |

**Cambio protocollo = 1 riga in config JSON. Zero cambi nel codice.**

---

## 🔄 State Machine (Ogni Nodo)

```
BOOT → INIT → READY → RUNNING ↔ ERROR → RECOVERY → SHUTDOWN
                    ↓              ↑
                  FAULT ──────────┘
```

Ogni nodo implementa questa macchina a stati con:
- **Health checks** periodici
- **Watchdog** hardware + software
- **Graceful degradation** (es. servo fallito → home position, continua operazione ridotta)
- **Event sourcing** per state transitions (audit trail completo)

---

## 🔧 Configurazione (JSON Only)

```json
// config/node2_head/servos.json
{
  "servos": {
    "neck_yaw": {
      "channel": 0,
      "min_pulse": 500,
      "max_pulse": 2500,
      "min_angle": -90,
      "max_angle": 90,
      "home_angle": 0,
      "speed": 60,
      "acceleration": 30,
      "offset": 0,
      "reversed": false,
      "calibration": { "raw_min": 102, "raw_max": 512 }
    },
    "neck_pitch": { ... },
    "eyes_horizontal": { ... }
  }
}
```

**Zero valori hardcoded. Tutto configurabile a runtime con hot-reload.**

---

## 📦 OTA (Over-The-Air Updates)

- **Tutti gli ESP32** aggiornabili da remoto via Robot Core
- **Firmware firmato** (ECDSA P-256), verifica signature su flash
- **Rollback automatico** se boot fallisce 3 volte
- **Delta updates** per banda limitata
- **Staged rollout** (canary → fleet)

```bash
# Da CLI o UI Web
openj5 ota deploy --node node2_head --firmware builds/node2_head_v1.2.3.bin --sign-key keys/ota_private.pem
```

---

## 🧪 Testing Strategy

| Livello | Framework | Target | CI/CD |
|---------|-----------|--------|-------|
| **Unit** | pytest (Py), Unity (C), Catch2 (C++) | >90% coverage core | Ogni commit |
| **Integration** | pytest + testcontainers | Plugin + Gateway + EventBus | Ogni PR |
| **Hardware-in-Loop** | Custom runner su Pi + ESP32 | Driver reali, comunicazione reale | Nightly |
| **Simulation** | Gazebo + pytest | Digital Twin parity | Ogni PR |

```bash
# Esegui tutti i test
./scripts/test/run_all.sh

# Solo unit
./scripts/test/unit.sh

# Hardware-in-loop (richiede HW connesso)
./scripts/test/hardware.sh --node node2_head
```

---

## 📚 Documentazione Obbligatoria

Ogni PR **deve** aggiornare:

| Documento | Descrizione |
|-----------|-------------|
| `README.md` | Overview progetto |
| `CHANGELOG.md` | Keep a Changelog format |
| `ROADMAP.md` | Roadmap per release |
| `PROJECT_STATUS.md` | Stato completamento per area |
| `ARCHITECTURE.md` | Diagrammi Mermaid, decisioni architetturali |
| `DECISIONS.md` / `docs/adr/ADR-XXX.md` | ADR per decisioni architetturali |
| `API.md` | Documentazione API pubblica (OpenAPI/Swagger) |
| `CONFIGURATION.md` | Tutti i file config con schema JSON |
| `HARDWARE.md` / `MECHANICS.md` / `ELECTRONICS.md` | Docs HW |
| `FIRMWARE.md` / `SIMULATION.md` / `TESTS.md` | Guide tecniche |
| `DEPLOYMENT.md` / `SECURITY.md` / `OTA.md` / `NETWORK.md` | Ops |

**CI fallisce se mancano aggiornamenti doc per file modificati.**

---

## 🛡️ Sicurezza

- **mTLS** su tutte le comunicazioni MQTT/ROS2/gRPC
- **JWT** per REST API + WebSocket
- **OTA firmato** con verifica signature su dispositivo
- **Input validation** su tutti i comandi (range, rate limit, auth)
- **Fail-safe**: Servi → home, Motori → brake, LED → error pattern su fault
- **Emergency Stop** hardwired su ogni nodo motori + SW watchdog

---

## 🤝 Contribuire

1. Leggi `DEVELOPMENT.md` (workflow obbligatorio: Analisi → Progettazione → Docs → Implementazione → Test → Refactor → Docs Finali → Roadmap → Changelog → Project Status → ADR)
2. Leggi `CONTRIBUTING.md` e `CODE_OF_CONDUCT.md`
3. **Ogni PR richiede**: Tests, Docs aggiornate, ADR se architetturale, Zero warning lint
4. Apri issue per discutere feature grandi prima di implementare

---

## 📋 Roadmap Anno 1 (MoSCoW)

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
| Unit + Integration >80% | CI/CD pipeline | Simulation test in CI | Multi-robot |

---

## 📄 Licenza

**MIT License** per software | **CERN-OHL-S v2** per hardware (CAD, schemi, PCB)

Vedi `LICENSE.md` e `LICENSE_HARDWARE.md` per dettagli.

---

## 🔗 Link Utili

- **Documentazione**: https://docs.openj5.org
- **Community Forum**: https://forum.openj5.org
- **Plugin Registry**: https://plugins.openj5.org
- **Hardware Certification**: https://hardware.openj5.org
- **Discord**: https://discord.gg/openj5
- **Issue Tracker**: https://github.com/openj5/openj5/issues

---

## 🙏 Crediti

OpenJ5 è ispirato a **Johnny 5** (Corto Circuito, 1986) — il robot che voleva "input, input, input!" e imparava ad essere vivo.

Costruito con ❤️ dalla community OpenJ5 per democratizzare la robotica embodiment professionale.

---

> **"Input! Input! Input!"** — Johnny 5