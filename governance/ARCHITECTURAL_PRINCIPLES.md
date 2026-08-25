# ARCHITECTURAL_PRINCIPLES

## Principi Architetturali Non Negoziabili

Questi principi sono le "leggi costituzionali" del progetto. Ogni modifica al codice, al firmware, al CAD o all'elettronica deve rispettarli. Una violazione non giustificata da un ADR (Architecture Decision Record) blocca il merge.

---

### P1 - Hexagonal Architecture (Ports & Adapters)

Il core domain non dipende da nulla di esterno: nessun import di MQTT, Redis, SQLAlchemy, FastAPI, PCA9685 nel domain code. Le dipendenze puntano **sempre verso il centro**:

```
Applicazioni / Plugin / SDK
        ↓
   Application Layer (Use Cases, Command Bus, Query Bus)
        ↓
   Domain Layer (Entities, Value Objects, Events, Policies)
        ↑
   Infrastructure Layer (Adapters: MQTT, Redis, DB, Drivers)
```

**Verifica**: l'import checker in CI deve fallire su qualsiasi import esterno dal dominio.

---

### P2 - Dependency Injection Totale

Zero `new` di servizi dentro il domain/application code. Le dipendenze vengono iniettate dai costruttori; la composizione avviene solo nel composition root (`__main__.py` o equivalente).

- Vietato: variabili globali per servizi, Service Locator sparsi nel codice.
- Consentito: Service Locator **solo** nel composition root.

---

### P3 - Event-Driven Architecture

I componenti comunicano tramite l'Event Bus centrale con eventi tipizzati. Esempio obbligato:

```
Camera → FaceDetected → EventBus → BehaviorEngine → MotionPlanner → HeadController
```

Mai chiamate dirette tra moduli che vivono in contesti diversi. Ogni evento ha: `event_id`, `event_type`, `timestamp`, `source_node`, `correlation_id`, payload tipizzato.

---

### P4 - Hardware Abstraction Layer (HAL) Totale

Nessun codice applicativo tocca direttamente PCA9685, L298N, VL53L0X, MPU6050, I2S, I2C, SPI. Solo interfacce:

`IServoDriver`, `IMotorDriver`, `IDistanceSensor`, `IIMU`, `ICameraDriver`, `IAudioInput`, `IDisplay`, `ILedStrip`.

Sostituire un chip = scrivere un nuovo driver, zero modifiche al codice applicativo.

---

### P5 - Communication Gateway Pattern

Nessun modulo usa MQTT (o ROS 2, o WebSocket) direttamente. Solo `ICommunicationGateway`. Il protocollo è una scelta di configurazione, non di codice:

> Cambiare protocollo = 1 riga in config JSON. Zero cambi nel codice.

---

### P6 - Robot SDK come Facciata Unica

Tutte le applicazioni usano API ad alto livello:

```python
robot.head.look_at(x, y, z)
robot.right_arm.wave()
robot.tracks.move_forward(speed=0.5)
robot.speech.say("Ciao")
robot.behavior.idle()
```

Mai topic MQTT, mai angoli servo, mai comandi raw nel codice applicativo. Il Raspberry invia **comandi logici** (`Wave`, `LookLeft`, `FollowPerson`), gli ESP32 li traducono in traiettorie servo.

---

### P7 - Plugin Architecture

Vision, Speech, AI, Navigation, Battery, Face Recognition, Camera, Lidar, Motion, Hardware, Communication = plugin caricabili dinamicamente, con dipendenze dichiarate e permessi. Il core fornisce solo infrastruttura. Nuovo modello AI o nuovo sensore = nuovo plugin, zero touch al core.

---

### P8 - Configuration-Driven Everything

Ogni valore (velocità servo, PID, limiti, topic, IP, porte, pin GPIO, soglie sensori) proviene da JSON/YAML/DB/Config Service.

**Vietato scrivere**: `speed = 120;`
**Obbligatorio**: `speed = config.get("servo.neck_yaw.speed")`

Priorità sorgenti: `ENV > Database > YAML > JSON`. Hot reload dove possibile. Zero magic numbers (`grep -r "= [0-9]" src/` → 0 risultati, eccettuate costanti matematiche π/180/360).

---

### P9 - State Machine per Nodo

Ogni nodo implementa la stessa macchina a stati:

```
BOOT → INIT → READY → RUNNING ↔ ERROR → RECOVERY → SHUTDOWN
```

con health check periodici, watchdog hardware+software, graceful degradation ed event sourcing delle transizioni.

---

### P10 - Digital Twin Nativo

Il simulatore usa le identiche API del robot reale. Stesso SDK, stesso HAL, stesso Event Bus. Switch reale ↔ simulato = 1 riga di configurazione. Il software non deve mai sapere se controlla il robot reale o la simulazione.

---

### P11 - OTA Firmato e Sicuro

Tutti gli ESP32 aggiornabili da remoto: firmware firmato (ECDSA P-256), verifica signature su flash, rollback automatico dopo 3 boot falliti, staged rollout.

---

### P12 - Fail-Safe e Safety

Emergency stop hardwired su ogni nodo motori + watchdog software. Su fault: servi → home, motori → brake, LED → error pattern. Input validation su tutti i comandi (range, rate limit, auth). mTLS sulle comunicazioni, JWT sulle API.

---

### P13 - Continuous Documentation

Documentazione = parte integrante del codice. Una funzionalità senza documentazione aggiornata è incompleta. Ogni implementazione aggiorna: README, CHANGELOG, ROADMAP, PROJECT_STATUS, ARCHITECTURE/API/CONFIGURATION docs, ADR se architetturale, diagrammi Mermaid se cambia l'architettura.

---

### P14 - Continuità del Progetto

Il progetto deve poter essere chiuso oggi e riaperto tra due anni, o continuato da un'altra IA o sviluppatore, senza perdere informazione tecnica. Memoria persistente, session report, continuation prompt e decision log (ADR) sono requisiti funzionali, non opzioni.

---

## Regole di Dipendenza (Mai Violare)

```
Vision / Speech / AI (Plugin)
        ↓
Robot Core (Application + Domain)
        ↓
HAL / Gateway / EventBus (Infrastructure ports)
        ↓
Hardware (drivers, MCU)
```

La direzione può essere solo dall'alto verso il basso. Mai `Hardware → Vision`, mai un plugin che importa un altro plugin direttamente (passare dall'Event Bus), mai il domain layer che importa l'infrastructure layer.

---

## Design Authority

Nessun file significativo viene modificato senza verifica di coerenza con l'intera architettura. Prima di considerare completata una funzionalità, controllo finale obbligatorio:

- ✔ Compatibilità con l'architettura generale e i principi P1–P14
- ✔ Compatibilità con i documenti ADR
- ✔ Compatibilità con il Robot SDK
- ✔ Compatibilità con il Digital Twin
- ✔ Compatibilità con il sistema di configurazione
- ✔ Compatibilità con la roadmap
- ✔ Compatibilità con i test
- ✔ Compatibilità con il firmware ESP32
- ✔ Compatibilità con CAD ed elettronica
- ✔ Nessuna violazione della Project Constitution

Solo se tutti i controlli passano la funzionalità è completata.

---

## Riferimenti

- `Development_Constitution.md` — governance delle decisioni (Livelli A/B/C)
- `governance/CODING_STANDARD.md` — regole di scrittura del codice
- `governance/NAMING_CONVENTIONS.md` — convenzioni di denominazione
- `governance/NON_GOALS.md` — cosa OpenJ5 NON fa
- `docs/architecture/ARCHITECTURE.md` — diagrammi C4 e dettagli
- `docs/adr/INDEX.md` — registro delle decisioni architetturali
