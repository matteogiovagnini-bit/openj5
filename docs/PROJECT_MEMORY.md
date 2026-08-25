# PROJECT_MEMORY — Memoria Permanente OpenJ5

> **Questo documento è la memoria permanente del progetto. Mai perderlo.**
> Aggiornare a ogni cambiamento significativo. Ultimo aggiornamento: 2026-08-25

---

## 1. Visione Generale

OpenJ5 è una **piattaforma robotica professionale open source** ispirata a Johnny 5 (Corto Circuito, 1986). Non si costruisce "un robot": si costruisce **la piattaforma che rende banale costruire robot**.

Requisiti fondanti:
- Completamente stampabile in 3D, completamente parametrico, completamente documentato.
- Durata di progetto 10+ anni senza riscritture architetturali.
- Ogni componente/protocollo/driver/MCU sostituibile senza toccare la logica applicativa.
- Local-first: il robot funziona interamente offline.
- La documentazione è parte integrante del codice: un'implementazione senza doc aggiornata è incompleta.

---

## 2. Architettura

### Distribuita a 6 nodi
| Nodo | Hardware | Ruolo |
|------|----------|-------|
| 1 | Raspberry Pi 4 8GB (Ubuntu + Docker) | Robot Core: AI, Vision, Speech, Planning, Behavior, broker MQTT, REST/WebSocket API, DB, Event Bus, Plugin Manager, OTA Manager, Digital Twin |
| 2 | ESP32-S3 | Head: 6 servi (neck Y/P/R, eyes H/V, eyelids), LED, display, mic I2S |
| 3 | ESP32-S3 | Braccio destro: 6 servi (shoulder P/R/Rot, elbow, wrist, gripper) |
| 4 | ESP32-S3 | Braccio sinistro (mirror del 3) |
| 5 | ESP32 | Torso: 4 servi, LED, fan, INA219 + DS18B20, sensori |
| 6 | ESP32 | Cingoli: L298N + 2 motori DC con encoder, IMU, ToF, bumper |

### Layered (Hexagonal / Ports & Adapters)
```
Applicazioni → Robot SDK (facciata unica)
    ↓ CommandBus/QueryBus (CQRS)
Application Layer → Domain Layer (zero dipendenze esterne)
    ↑ implementate da
Infrastructure adapters: MqttGateway, RedisEventBus, repositories,
HAL drivers (PCA9685, L298N, Gazebo...), config service
```

Flusso tipico: `SDK → CommandBus → Gateway → MQTT → ESP32 (traduce comando logico in traiettorie servo) → evento su evt topic → Event Bus → consumer`.

---

## 3. Decisioni Principali (vedi docs/adr/ per i dettagli)

| ADR | Decisione |
|-----|-----------|
| ADR-001 | Hexagonal Architecture per il core domain |
| ADR-002 | Architettura distribuita a 6 nodi (RPi4 + 5× ESP32) |
| ADR-003 | Communication Gateway pattern multi-protocollo |
| ADR-004 | Event-driven con Event Bus centrale (Redis Streams, DLQ, replay) |
| ADR-005 | HAL totale per tutti i driver hardware |
| ADR-006 | Robot SDK come unica facciata pubblica |
| ADR-007 | Tutto è plugin (core = solo infrastruttura) |
| ADR-008 | Configuration-driven: zero numeri hardcoded |
| ADR-009 | State machine per nodo BOOT→INIT→READY→RUNNING↔ERROR→RECOVERY→SHUTDOWN |
| ADR-010 | Digital Twin nativo (stesse API per reale e simulato) |
| ADR-011 | OTA firmato ECDSA P-256 con rollback automatico |
| ADR-012 | CAD parametrico FreeCAD con spreadsheet unico |
| ADR-013 | Sicurezza: mTLS, JWT, OTA firmato, fail-safe |
| ADR-014 | Python per Robot Core, C++20 per firmware |
| ADR-015 | MQTT (Mosquitto) transport primario |

Regola: gli ADR sono immutabili; una decisione che li supera genera un nuovo ADR "Superseded by".

---

## 4. Hardware Utilizzato (reference)

- Raspberry Pi 4 8GB, Ubuntu Server 22.04/24.04 LTS, Docker Compose.
- 3× ESP32-S3 + 2× ESP32, ESP-IDF 5.2+, FreeRTOS @1kHz.
- PCA9685 (I2C 0x40–0x43 per nodi 2–5), servi hobby standard.
- L298N + 2 motori DC con encoder (nodo 6), MPU6050/ICM20948, VL53L0X ×2.
- Mosquitto 2.0, Redis 7 (Streams), PostgreSQL 16, FastAPI/Uvicorn, structlog.
- Osservabilità: Prometheus, Grafana, Loki+Promtail, OpenTelemetry Collector.
- Simulazione: Gazebo Harmonic headless (immagine OCI ufficiale arm64).

Motivazioni chiave: costi consumer (< ~1000 €/robot), ecosistemi maturi, sostituibilità (NON_GOALS §4 elenca l'hardware NON supportato in Anno 1).

---

## 5. Pattern Utilizzati

Hexagonal Architecture · DDD · CQRS (CommandBus/QueryBus) · Event-Driven · Event Sourcing (transizioni stato) · Repository · Facade (Robot SDK) · Factory (GatewayFactory) · Strategy · Observer · Adapter · Dependency Injection · State Machine · Saga-like orchestrazione fault propagation · Consumer Groups + DLQ (Redis Streams).

---

## 6. Regole di Progettazione (sintesi operativa)

1. Dipendenze sempre verso il dominio; mai infrastruttura nel domain layer.
2. DI via costruttore; composizione solo nel composition root (`__main__.py`).
3. Zero numeri magici: tutto da config JSON/YAML (priorità ENV > DB > YAML > JSON).
4. Nessun modulo usa MQTT direttamente: solo `ICommunicationGateway`.
5. Applicazioni usano solo l'SDK; il RPi invia comandi logici, mai angoli servo.
6. Topic MQTT versionati `openj5/v<major>/<node>/<cmd|evt>`; payload JSON compatti.
7. Ogni nodo implementa la state machine standard; motion solo in RUNNING.
8. Fail-safe su ogni nodo: home servi, brake motori, pattern LED errore, E-stop hardwired.
9. Documentazione aggiornata = parte del Definition of Done (v. CODING_STANDARD §8).
10. Decisione architetturale → nuovo ADR obbligatorio.

Dettagli completi: `governance/ARCHITECTURAL_PRINCIPLES.md`, `governance/CODING_STANDARD.md`, `Development_Constitution.md`.

---

## 7. Convenzioni (sintesi)

- Codice in inglese; governance/memoria in italiano; ADR e doc tecnica in inglese.
- Python: PEP8 + type hints, ruff/mypy, async-first, structlog JSON.
- C++: C++20, `-Wall -Wextra -Wpedantic -Werror`, namespace `openj5::`, metodi camelCase.
- Interfacce: prefisso `I` (`IServoDriver`). Eventi: PascalCase al passato (`ServoMoved`).
- Container `openj5-<servizio>`; ENV prefisso `OPENJ5_`; branch `feat/<area>-<desc>`.
- Dettagli: `governance/NAMING_CONVENTIONS.md`.

---

## 8. Stato di Avanzamento (riferimento rapido)

- v0.0.1 (2026-06-15): scaffolding + governance.
- v0.1.0 (2026-06-30): core domain, plugin, SDK, gateway, event bus, state machine, config, ADR 1–4, scheletro firmware.
- v0.2.0 (2026-07-15): robot_core completo, REST 25+ endpoint, WebSocket, Docker Compose 10 servizi, config infrastruttura.
- Sessione 2026-08-12/13: stabilizzazione operativa dello stack Docker (~18 fix: certificati, healthcheck mosquitto, porte, Loki/OTEL).
- Sessione 2026-08-25 (1): conformità alla constitution (governance completata, ADR 005–015, documenti di continuità).
- Sessione 2026-08-25 (2): CI base attiva (ruff, doc-check, docker build); CHANGELOG corretto; framework plugin riparato (`src/plugins/base.py`), bug latenti del dominio corretti, cinematica DH+IK implementata; `src/` ora importabile al 100%.
- Sessione 2026-08-25 (3): percorso di deploy Node 1 documentato e automatizzato (`docs/deployment/DEPLOYMENT.md` + `scripts/deploy/bootstrap_rpi4.sh`); validazione su hardware reale = T-018.
- v0.3.0: testing — **in corso** (T-003…T-006 da fare).
- Firmware nodi 3–6, OTA client ESP32, CAD/elettronica: non iniziati (v0.4.0+).

Stato dettagliato: `PROJECT_STATUS.md`. Prossime attività: `docs/NEXT_TASK.md`.

---

## 9. Obiettivi Futuri

Roadmap completa in `ROADMAP.md`; idee in `future/future.md`: riconoscimento facciale, inseguimento persone, braccia 7 DoF, LIDAR, SLAM, manipolazione oggetti, docking automatico, ricarica autonoma. Post-MVP (GOALS §Obiettivi Futuri): fleet management, marketplace plugin, WebRTC teleop, certificazioni ISO 13482/CE.

---

## 10. Rischi Noti e Debito Tecnico

| Area | Debito/Rischio | Mitigazione prevista |
|------|----------------|---------------------|
| Testing | Nessun test nel repo; CHANGELOG corretto il 2026-08-25 (non dichiara più lavoro inesistente) | v0.3.0: creare suite reale (T-003…T-006) |
| CI | Pipeline base attiva (ruff, doc-check, docker build); mancano mypy, clang-tidy, job firmware | T-002 completamento + T-007 (bloccato da skeleton firmware) |
| Plugin framework `src/plugins/` | ✅ Riparato 2026-08-25: contratti unici in `base.py`, package importabile, lifecycle verificato end-to-end | — |
| Formatter | `ruff format` non adottato (36 file da riformattare) | T-016 |
| SDK | Buses reali non cablati (`TODO` in `src/sdk/robot.py`) | Integrazione con command bus esistente |
| Gateway | Auto-reconnect MQTT assente | Resilienza rete (GOALS T5) |
| Event Bus | NATS non implementato (`NotImplementedError`) | Alternativa futura, non bloccante |
| Config | set() runtime non persistito su file/DB | Hot-reload completo |
| Firmware | Solo scheletro Node 2, NON compilabile (header/sorgenti/CMakeLists mancanti); OTA client parziale | T-014 poi ROADMAP v0.4.0 |
| Certificati | Rinnovo automatico mancante | ROADMAP v0.4.0 |
