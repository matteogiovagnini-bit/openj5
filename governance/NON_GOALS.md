# NON-GOALS

## Cosa OpenJ5 NON Farà (Esplicitamente)

Questa lista esiste per **evitare scope creep**, mantenere il focus e dire "no" con sicurezza alle richieste che non allineano con la visione.

---

### 1. Non È Un Prodotto Hardware Commerciale

| Non Faremo | Perché |
|------------|--------|
| Vendere kit hardware completi | Core mission = piattaforma open, non e-commerce |
| Certificare CE/FCC il robot completo | Responsabilità di chi produce/integra |
| Offrire garanzia hardware | Open source hardware = "as is", community support |
| Fare manufacturing a volume | Chi vuole produrre forka il CAD e si arrangia |

> **Chiarimento:** Forniamo CAD, BOM, schemi, PCB, guide assemblaggio. Chiunque può produrre e vendere kit derivati (licenza MIT/Apache 2.0 / CERN-OHL).

---

### 2. Non È Un Framework ROS 2

| Non Faremo | Perché |
|------------|--------|
| Wrapper ROS 2 su tutto | ROS 2 è *un* protocollo. Il Communication Gateway supporta MQTT, ROS 2, WebSocket, Serial, BLE, CAN, Zenoh, gRPC. |
| Obbligare ROS 2 per sviluppo | L'SDK astrae il protocollo. `robot.head.lookAt()` funziona identico su MQTT, ROS 2, Sim. |
| Usare ROS 2 come Event Bus | Abbiamo il nostro Event Bus (Redis Streams / NATS / custom). ROS 2 è solo un trasporto. |
| Dipendere da `rclcpp` / `rclpy` in core | Core domain = zero dipendenze esterne. ROS 2 solo in adapter plugin. |

---

### 3. Non È Un Progetto "Solo Software" o "Solo Hardware"

| Non Faremo | Perché |
|------------|--------|
| Solo firmware / solo software / solo CAD | La forza è l'**integrazione co-progettata**. HW/SW/FW/CAD evolvono insieme. |
| Separare repo per HW/SW/FW | Monorepo (o repo strettamente sincronizzati) per atomicità: 1 commit = HW+FW+SW+Docs+ADR. |

---

### 4. Non Supportiamo Tutto l'Hardware Esistente

| Non Supportiamo (Anno 1) | Alternativa |
|--------------------------|-------------|
| Raspberry Pi 5 / CM4 / Jetson / Orange Pi | RPi 4 8GB è reference. Altri = PR benvenuti come plugin HAL. |
| Arduino / Teensy / STM32 / RP2040 | ESP32/ESP32-S3 è reference. Altri = implementazione `IMicrocontrollerHal`. |
| Dynamixel / Feetech / HerkuleX servos | PCA9685 + servos hobby/standard è reference. Serial bus servos = plugin `IServoDriver`. |
| ODrive / TMC5160 / Trinamic / BLDC | L298N (poi TB6612/BTS7960) è reference. Altri = plugin `IMotorDriver`. |
| RealSense / ZED / OAK-D / Kinect | Camera generica `ICameraDriver` + plugin specifici. |
| LIDAR (RPLIDAR, Velodyne, Ouster, Livox) | `ILidarDriver` plugin. Non in core. |

> **Regola:** L'hardware di reference è **documentato, testato, supportato in CI**. Tutto il resto è **plugin esterno** mantenuto da chi lo usa.

---

### 5. Non Implementiamo Funzionalità AI "Finale" nel Core

| Non Nel Core (Anno 1) | Dove Va |
|------------------------|---------|
| Face Recognition | Plugin `FaceRecognitionPlugin` |
| Object Detection (YOLO) | Plugin `VisionPlugin` → `ObjectDetectionPlugin` |
| Speech Recognition (Whisper) | Plugin `SpeechPlugin` → `SttPlugin` |
| Speech Synthesis (Piper) | Plugin `SpeechPlugin` → `TtsPlugin` |
| LLM / VLM / Agentic AI | Plugin `AiPlugin` / `BehaviorPlugin` |
| Navigation / SLAM / Nav2 | Plugin `NavigationPlugin` |
| Grasp Planning / MoveIt | Plugin `ManipulationPlugin` |
| Behavior Trees | Plugin `BehaviorEnginePlugin` |

> **Core = Infrastruttura.** AI = Plugin. Il core fornisce: Event Bus, SDK, HAL, Config, OTA, State Machine, Plugin Manager. **Basta.**

---

### 6. Non Rompiamo la Compatibilità All'Indietro (Post v1.0)

| Non Faremo Dopo v1.0.0 | Regola |
|------------------------|--------|
| Breaking changes su API pubbliche SDK | SemVer: Major solo se costretti da sicurezza/architettura fondamentale |
| Cambiare formati config senza migrazione | Migration tool + dual support per 1 major version |
| Rimuovere plugin core senza deprecation cycle | 2 versioni minimo deprecazione + migration guide |
| Cambiare protocollo MQTT topic schema senza versioning | Topic versionati: `openj5/v1/head/cmd`, `openj5/v2/head/cmd` |

---

### 7. Non Accettiamo Contributi Senza Qualità Minima

| Requisito Minimo | Perché |
|------------------|--------|
| Tests (unit + integration) | Senza test = non mergeable |
| Docs aggiornate (API, README, ADR se architetturale) | Docs = codice |
| Nessun warning critico (lint, static analysis) | Qualità non negoziabile |
| ADR per decisioni architetturali | Storia decisionale = continuità |
| Aggiornamento CHANGELOG, PROJECT_STATUS, ROADMAP | Visibilità stato progetto |

---

### 8. Non Facciamo "Quick & Dirty"

| Anti-Pattern | Risposta Standard |
|--------------|-------------------|
| "Metto un TODO e lo sistemo dopo" | **Non si merga**. Il TODO deve avere: ID, descrizione, stima, owner, scadenza, link a issue. |
| "Hardcode questo valore per ora" | **Mai**. `Config.Get("servo.neck_yaw.max_angle")` |
| "Copio-incolla questo codice" | **Mai**. Estrai in shared library / base class / utility. |
| "Uso variabile globale per velocità" | **Mai**. Dependency Injection. Service Locator solo in composition root. |
| "Faccio diretto MQTT publish nel codice" | **Mai**. `communicationGateway.publish(topic, payload)` via interface. |

---

### 9. Non Ignoriamo la Sicurezza (Safety & Security)

| Non Ignoriamo | Minimo Richiesto |
|---------------|------------------|
| Emergency Stop (HW + SW) | Hardwired E-stop su ogni nodo motori + SW watchdog |
| mTLS su comunicazioni | MQTT su TLS, cert per nodo, CA privata |
| Signed OTA | Firmware firmato, verifica signature su flash |
| Input validation | Tutti i comandi validati (range, rate limit, auth) |
| Fail-safe behavior | Servi → home position, motori → brake, LED → error pattern su fault |

---

### 10. Non Dimentichiamo la Continuità

| Non Dimentichiamo | Azione Obbligatoria |
|-------------------|---------------------|
| Session Report | Ogni sessione → `docs/SESSION_REPORT.md` |
| Continuation Prompt | Ogni sessione → `docs/CONTINUATION_PROMPT.md` |
| Project Memory | Sempre aggiornato → `docs/PROJECT_MEMORY.md` |
| Next Task | Sempre aggiornato → `docs/NEXT_TASK.md` |
| Decision Log (ADR) | Ogni decisione architetturale → `docs/adr/ADR-XXX.md` |

---

> **Se una richiesta cade in questa lista → Risposta standard: "Questo è un Non-Goal documentato in governance/NON_GOALS.md. Se vuoi proporre un'eccezione, apri un ADR (Architecture Decision Record) con motivazione, alternative, conseguenze. La Design Authority valuterà."**