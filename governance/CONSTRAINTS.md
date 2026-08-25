# CONSTRAINTS

## Vincoli del Progetto OpenJ5

Vincoli fisici, tecnici, economici e organizzativi che limitano le scelte di progetto. Ogni proposta che viola un vincolo richiede un ADR.

---

## 1. Vincoli Hardware

| Componente | Vincolo | Implicazioni |
|------------|---------|--------------|
| **Nodo 1** | Raspberry Pi 4 8GB, Ubuntu Server 22.04/24.04 LTS, ARM64 | Python 3.11+ performante solo con async; modelli AI quantizzati; Docker obbligatorio |
| **Nodi 2–4** | ESP32-S3 (PSRAM consigliato), ESP-IDF 5.2+ | RAM/flash limitate: driver modulari, no librerie pesanti, C++20 |
| **Nodi 5–6** | ESP32 classico | Ancora più limitato di S3: firmware minimale |
| **Servi** | PCA9685 + servi hobby standard (no serial bus servo in Anno 1) | Alimentazione separata dai logic; budget PWM 16 canali/nodo |
| **Motori** | L298N + 2 DC motori con encoder (prima versione) | Driver inefficiente (drop tensione): power budget critico |
| **Rete** | WiFi 2.4 GHz per gli ESP32, Ethernet per RPi | Latenza/banda variabili: QoS MQTT, messaggi compatti, retry |
| **Alimentazione** | Batteria singola a bordo, autonomia target ≥ 2h | Power budget calcolato e verificato prima dell'assemblaggio |

**Non supportati in Anno 1** (vedi NON_GOALS): RPi 5/Jetson, Arduino/Teensy/STM32/RP2040, Dynamixel/Feetech, ODrive/TMC, RealSense/ZED/LIDAR.

---

## 2. Vincoli Software

- **Python 3.11+** per Robot Core/SDK; **C++20** per firmware. Nessun altro linguaggio nel core.
- **Zero dipendenze esterne nel domain layer** (Hexagonal).
- **MQTT (Mosquitto) transport primario**; ROS 2 solo come bridge adapter opzionale.
- **Redis Streams** event bus primario (NATS alternativa futura); PostgreSQL 16 persistenza; SQLite ammesso solo in dev.
- **Docker Compose** come deployment reference su RPi; Kubernetes fuori scope Anno 1.
- Tutti i topic MQTT versionati: `openj5/v1/<node>/<cmd|evt>`.
- Config interamente JSON/YAML; validazione JSON Schema/Pydantic.

---

## 3. Vincoli Meccanici / CAD

- Tutto il CAD **parametrico in FreeCAD** (spreadsheet unico `openj5_params`); STL sempre rigenerabili da parametri.
- Parti stampabili in 3D con stampanti FDM consumer (vano ≥ 220×220×250 mm, no supporti dove evitabile).
- Tolleranze standard FDM documentate nel spreadsheet (wall thickness, clearance).
- URDF/XACRO esportato dal CAD — mai scritto a mano separatamente (single source of truth = FreeCAD).

---

## 4. Vincoli Elettronici

- Schemi e PCB in **KiCad 8+**; BOM generato automaticamente.
- E-stop hardwired su ogni nodo motori (indipendente dal firmware).
- Livelli logici 3.3V; alimentazione servi/motori separata dalla logica; misurazione corrente (INA219) su torso.
- Certificazioni CE/FCC **non perseguite in Anno 1** (responsabilità di chi integra).

---

## 5. Vincoli di Processo (Constitution)

- Decisioni Livello C (architettura, hardware, protocolli, rimozione funzionalità) **richiedono ADR approvato dalla Design Authority**.
- ADR immutabili: superseded, mai modificati.
- Nessun merge senza: test, doc aggiornate, zero warning critici.
- Memoria di progetto obbligatoria: SESSION_REPORT, PROJECT_MEMORY, NEXT_TASK, CONTINUATION_PROMPT aggiornati ogni sessione.
- SemVer rigoroso; nessuna breaking change su API pubbliche post-1.0 senza major bump e migration guide.

---

## 6. Vincoli Economici / Organizzativi

- Progetto open source (MIT software, CERN-OHL-S hardware): nessun componente proprietario imprescindibile.
- Hardware consumer reperibile (RPi, ESP32, PCA9685, L298N, VL53L0X, MPU6050): costo totale robot target < ~1000 €.
- Team ridotto (singolo sviluppatore + IA): priorità alla manutenibilità e alla documentazione che permette continuità, non alla velocità.
- Nessun servizio cloud obbligatorio: il robot deve funzionare completamente offline/local-first.

---

## 7. Vincoli di Sicurezza / Safety

- mTLS obbligatorio sulle comunicazioni MQTT verso gli ESP32; JWT sulle REST/WebSocket API.
- OTA firmato ECDSA P-256, rollback automatico.
- Fail-safe comportamentale su ogni nodo (home position, brake, pattern LED).
- Nessuna funzionalità che muova il robot fisicamente può bypassare la state machine e i safety check.

---

## Riferimenti

- `governance/NON_GOALS.md`
- `governance/CONSTRAINTS.md` (questo file)
- `docs/architecture/ARCHITECTURE.md`
- `Development_Constitution.md`
