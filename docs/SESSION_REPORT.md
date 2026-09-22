# SESSION_REPORT — Report di Sessione

> Creare/aggiornare a FINE di ogni sessione secondo PERSISTENT_PROJECT_MEMORY.md.

---

## Sessione: 2026-09-22 — T-003 Suite unit test core domain (100% coverage)

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-09-22 |
| Versione progetto | v0.2.0+ (Robot Core operativo su RPi4); v0.3.0 in corso |
| Obiettivo | T-003: suite pytest su `src/core/domain/` con target ≥90% coverage; obiettivo secondario dichiarato: correggere i bug latenti scoperti dai test nella stessa sessione |

### Decisioni
1. **Copertura target raggiunta al 100%** su `src/core/domain/` (1383 stmt, 0 miss) — target formale ≥90%.
2. Bug latenti emersi dai test → **corretti immediatamente** nello stesso commit di sessione (stesso pattern della sessione T-015 2026-08-25), documentati in CHANGELOG e KNOWLEDGE_BASE §1-quinquies.
3. Le 3 copie duplicate di `DomainEvent` **non** sono state refactorate (fuori scope di T-003): creato debito **T-028**.
4. Gate coverage fissato a ≥90% in CI (sotto il 100% realizzato: margine per refactoring futuri senza rompere la pipeline).

### Attività completate
1. **Ambiente**: uv + `.venv` (CPython 3.11.16), pytest 9.1.1, pytest-cov 7.1.0, ruff 0.16.8.
2. **Suite test creata**: `tests/unit/conftest.py` (fixture robot/make_node) + 6 moduli — `test_domain_value_objects.py`, `test_domain_events.py`, `test_domain_commands.py`, `test_domain_entities.py`, `test_domain_services.py`, `test_domain_repositories.py`. **149 test verdi, 100% coverage `core.domain`**.
3. **Fix sorgente scoperti dai test**:
   - `commands.py`: `Command.__post_init__` era `@abstractmethod` → 9 comandi inistanziabili (~50 siti SDK, incl. `emergency_stop()`); ora hook concreto no-op.
   - `events.py`: `EVENT_CATEGORIES` restituiva sempre BUSINESS; `to_dict()` serializzava solo i campi base (payload sottoclassi persi); `from_dict()` ora filtra chiavi sconosciute e costringe i tipi dal wire.
   - `entities.py`: `Robot` completato con `state: Optional[NodeState]`, `battery`, `errors`, `get_errors()`.
   - `services.py`: rimosso blocco morto `robot.tracks_odometry`; **bug matriciale IK DLS** (`J·Jᵀ` sulle righe → `JᵀJ` sui giunti, con test di convergenza <1 mm); backtracking line search (`IK_MIN_STEP_ALPHA = 1/16`) + cap `IK_MAX_STEP_RAD = 0.5`; **overshoot profilo triangolare** unificato in `_rest_to_rest_profile()`.
   - `redis_event_bus.py`: 3 siti da `DomainEvent.from_dict` a `deserialize_event`.
4. **Config**: `pyproject.toml` — `[tool.pytest.ini_options]` (testpaths, pythonpath) e `[tool.coverage.*]` (source core.domain, show_missing, exclude_also).
5. **CI**: nuovo job `python-tests` (pytest `--cov=core.domain --cov-fail-under=90`) in `.github/workflows/ci.yml`; job lint esteso a `tests/`. `ruff check` e `./scripts/check_docs.sh` verdi.
6. **Docs**: CHANGELOG (Fixed/Added), PROJECT_STATUS, PROJECT_MEMORY (§8/§10), NEXT_TASK (T-003 ✅, T-002 aggiornato, T-004/T-005 sbloccati, nuovo **T-028**), KNOWLEDGE_BASE (§1-quinquies), SESSION_REPORT (questo), CONTINUATION_PROMPT rigenerato.

### Lezioni (→ KNOWLEDGE_BASE §1-quinquies)
`@abstractmethod` su `__post_init__` di un dataclass non-ABC rende i subclass inistanziabili in silenzio fino al primo uso. Serializzazione eventi sempre derivata da `dataclasses.fields()`, mai enumerata a mano. In DLS la matrice è `JᵀJ` (n×n sui giunti), non `J·Jᵀ` (3×3 sulle righe): dimensioni sbagliate = zigzag. Line search con cap per giunto difende dalle singolarità. Il ramo corto del profilo rest-to-rest deve condividere l'helper del ramo lungo. Il coverage è uno scopritore di bug.

### Debito emerso
- **T-028**: 3 copie di `DomainEvent` (`core/domain/events.py`, `eventbus/event_bus.py`, `firmware/.../robot_core/eventbus.py`) con serializzazione divergente.
- Redis `xadd` con valori non-stringa (attenzione in T-005).
- 3 righe IK coperte solo da casi degenere (DH a link zero): tornarci con test di convergenza in T-006.
- `PluginMetadata` non re-exportata da `core.domain` (scelta T-015, intenzionale).

### Prossimi passi consigliati
**T-004** (integration test REST/WS) o **T-005** (event bus + state machine) — entrambi sbloccati da T-003; oppure **T-025** (primo movimento fisico, banco).

### Comandi di verifica
```bash
.venv/bin/python -m pytest tests/unit -q --cov=core.domain --cov-report=term-missing
.venv/bin/ruff check src/ firmware/node1_robot_core/docker/src/ tests/
./scripts/check_docs.sh
```

---

## Sessione: 2026-09-21 — Design Node 7 Balance Controller (ADR-017)

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-09-21 |
| Versione progetto | v0.2.0+ (Robot Core operativo); prototipo Nodo 6 avviato; **ADR-017 accettato** |
| Obiettivo | Aggiungere al robot il mantenimento del corpo in equilibrio rispetto ai cingoli: NEMA17 + A4988 + IMU su nuovo Node 7 (ESP32-S3) |

### Decisioni (Level C, approvate)
1. **Nuovo Node 7 dedicato ESP32-S3** "Balance Controller" (estende ADR-002 da 6 a 7 nodi).
2. Driver stepper **A4988 (STEP/DIR/ENABLE)**; richiesto dall'owner come "A488" — interpretato A4988, da confermare.
3. IMU **MPU6050** sul corpo (Madgwick, 200 Hz).
4. Riduzione meccanica **cinghia/pulegge 20T→80T (1:4)**, corsa ±35° (4445 jsteps).
5. Scope consegnato: **ADR-017 + design + software Python testabile**. Firmware ESP-IDF (T-026) e CAD/meccanica (T-027) = follow-up.

### Attività completate
1. **ADR-017** (`docs/adr/ADR-017-node7-balance-controller.md`) + `docs/adr/INDEX.md`: estende ADR-002 e ADR-005; 5 alternative valutate e rifiutate; topic MQTT `openj5/v1/balance/{cmd,evt,telemetry,state}`; il PID vive sul nodo, il Pi invia comandi logici.
2. **HAL Python** `src/hardware/hal/stepper.py`: `IStepperDriver` (port puro), `StepperMove`, `StepperState`, `trapezoid_velocity` (helper di rampa senza I/O, testabile).
3. **Driver bench** `src/hardware/drivers/a4988.py` (gpiozero/lgpio, move accel-limitati) + `config/bench/balance.json`; demo `scripts/demo/balance_bench.py`.
4. **Mock CI-safe** `src/hardware/drivers/mock_stepper.py` (nessuna dipendenza GPIO) — semantica di integrazione della velocity separata dalla rampa (`step(dt)` vs `set_position_steps`).
5. **Simulatore livellamento** `src/hardware/sim/leveling.py`: loop PID 100 Hz, deadband 0,5°, profilo di pendenza del cingolo; guadagni validati (convergenza e ramp tracking ~0,5° di lag).
6. **Domain**: `StepperConfig` (`steps_per_joint_rev` = 12800, `steps_per_deg` = 35,556), `BalanceConfig`, `BodyCommand` (level/tilt/stow/stop), `GetBodyTiltQuery`/`GetBalanceStateQuery`, `BodyCommandEvent`/`BodyTelemetryEvent`/`BalanceStateChangedEvent`, entità `Stepper`, `NodeType.BALANCE`; export package aggiornati.
7. **SDK**: `BodyAPI` + `robot.body` (level/tilt/stow/stop/get_tilt/get_balance_state).
8. **Config**: `config/node7_balance/node.json` (complete), entry `stepper_driver` in `config/common/hal.json`, node7 in `config/common/topics.json`.
9. **Orchestratore robot_core**: node7 in statemachine node_types, health node list, API models target_node, digital_twin joint body_pitch.
10. **Test**: `tests/unit/test_balance_control.py` — 8 test verdi su Python 3.11 (venv uv); `ruff check` pulito (incluso fix F401 preesistente in `l298n.py`).
11. **Docs**: README, ARCHITECTURE (C4 + HAL diagram con IStepperDriver), API (Body API), CONFIGURATION (Node 7), PROJECT_MEMORY, PROJECT_STATUS, ROADMAP, CHANGELOG (Unreleased), NEXT_TASK (T-026/T-027), KNOWLEDGE_BASE (§1-quater), CONTINUATION_PROMPT.

### Lezioni (→ KNOWLEDGE_BASE §1-quater)
Separare la logica di moto (rampe) dall'I/O (GPIO): il mock non deve importare gpiozero; helper nel port HAL. Nel mock, "velocity comandata" e "posizione tramite rampa" sono due semantiche distinte (errore → hang infinito). Il lag di tracking dipende da kp in step/s per grado: ~71 step/s per 2°/s. Math: 200×16×4/360 = 35,556 jsteps/°.

### Debito emerso
- "A488" ≠ componente commerciale noto (interpretato A4988): conferma in T-026.
- PID configurato (kp=15, ki=1, kd=0.3) validato solo in simulazione; ratifica al primo banco con IMU.
- Driver Python = prototipo banco (regola come Nodo 6); produzione = firmware ESP32 (T-026).
- `src/hardware/__init__.py` creato: `hardware` ora package reale (import `hardware.drivers.*` invariato).

### Prossimi passi consigliati
**T-025** (primo movimento cingoli) o **T-026** (firmware Node 7); secondo priorità v0.3.0 (T-003 test domain).

---

## Sessione: 2026-08-26 — Banco Nodo 6: driver motori L298N + guida cablaggio

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-08-26 (seconda parte, banco hardware) |
| Versione progetto | v0.2.0+ (Robot Core operativo); prototipo Nodo 6 avviato |
| Obiettivo | Capire come collegare i motori (Nodo 6) e predisporre il primo movimento fisico |

### Attività completate
1. **Hardware identificato dall'owner**: 2× motoriduttore DC **12V 300rpm XD-37GB520** + modulo **L298N** + pacco **LiPo 3S** (11,1-12,6V).
2. **Decisione architetturale operativa**: primo driver HAL reale del progetto — `L298NDriver` con interfaccia `IMotorDriver` (initialize/set_velocity/get_velocity/brake/shutdown), come da ADR-005 e NAMING_CONVENTIONS Python.
3. **Zero numeri magici (ADR-008)**: GPIO in `config/bench/tracks.json` (ENA=GPIO18/PWM0, IN1=GPIO23, IN2=GPIO24; ENB=GPIO13/PWM1, IN3=GPIO22, IN4=GPIO27; GND comune). PWM hardware sui pin 18/13; GPIO14/15 evitati (console UART).
4. **Demo interattiva** `scripts/demo/tracks_bench.py`: w/s avanti/indietro, a/d sterzo sul posto, +/− velocità, x stop, q uscita con brake automatico; reading tastiera raw senza premere invio.
5. **Cablaggio documentato** `docs/hardware/BENCH_TRACKS.md`: tabelle L298N↔Pi, potenza (batteria per ultima, masse comuni, fusibile 5A), jumper ENA/ENB e regolatore 5V, checklist safety, troubleshooting.
6. **Procedure spegnimento/riaccensione** in DEPLOYMENT §11 (poweroff, attesa LED ACT, LiPo storage; boot automatico NVMe, risalita stack `unless-stopped`, verifica health).
7. Doc gate CI aggiornata con BENCH_TRACKS.md.

### Lezioni (→ KNOWLEDGE_BASE §1-ter)
Alimentazione mai dal Pi; jumper 5V rimosso con LiPo 12,6V (78M05 al limite); jumper ENA/ENB rimossi per PWM; GPIO PWM hardware 18/13; driver su host non in container; gpiozero+lgpio da installare.

### Debito emerso
- Il driver Python è un prototipo da banco: la produzione del Nodo 6 sarà firmware ESP32 (C++). Documentato in PROJECT_MEMORY §10.
- `.env`, secrets e certs non viaggiano nel repo/clone: vanno rigenerati sul dispositivo.

### Prossimi passi consigliati
**T-025**: primo movimento fisico (demo sul Pi); poi T-003 unit test core domain.

---

## Sessione: 2026-08-26 — T-018 PRIMO DEPLOYMENT REALE su RPi4 (interattiva)

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-08-26 (sessione guidata passo-passo con l'owner) |
| Versione progetto | v0.2.0+ → Robot Core OPERATIVO su hardware |
| Obiettivo | Preparare fisicamente il Nodo 1 e portare lo stack completo healthy |

### Attività completate
1. **Fase 1**: flash NVMe USB3 con Raspberry Pi Imager (Pi OS Lite 64-bit headless: hostname openj5-core, user openj5 UID 1000, SSH).
2. Boot USB nativo verificato (root su sda2, nessuna SD), EEPROM aggiornata (`rpi-eeprom-update -a`).
3. Codice trasferito via rsync; bootstrap eseguito (Docker, gruppo docker, segreti, certificati mTLS).
4. Scoperta: Pi OS corrente = Debian 13 Trixie (kernel 6.18); script e ADR-016 allineati (12|13).
5. **Fix reali in sequenza** (ognuno committato):
   - bootstrap: checkout rsync senza .git gestito; guardia anti-Ubuntu
   - Dockerfile: rimosso VOLUME (conflitto containerd image store → EROFS)
   - force-recreate dopo rebuild (compose non ricrea al cambio immagine sotto stesso tag)
   - Dockerfile: PYTHONPATH=/app/src (ModuleNotFoundError)
   - eventbus: alias EventBus=IEventBus (7 moduli); OTAManager.shutdown() (non stop)
   - metrics: publish come DomainEvent tipizzato
   - mosquitto ACL: regole GLOBALI per anonimo (user anonymous NON matcha client senza username!) + healthcheck deterministico pub/sub retained
   - promtail: rimosso bind ro /var/log host che rompeva mountpoint annidato (mkdirat EROFS)
   - grafana: GF_SECURITY_ADMIN_PASSWORD__FILE (doppio underscore); login ok admin/admin (password da cambiare)
6. **Risultato finale**: 10/10 servizi configurati e operativi, tutti healthy tranne ros2-bridge/gazebo mai avviati prima (catena dipendenze ora sbloccata, da confermare al prossimo up), API HTTPS live {"status":"ok"}, Swagger accessibile, limiti memoria cgroup v2 attivi (robot-core /3GiB; OOM test exit=137).
7. WiFi seconda sede configurata via NVMe montato sul PC (NetworkManager .nmconnection, permessi 600) — entrambe le reti in autoconnect.

### Lezioni (→ KNOWLEDGE_BASE §1-bis, 11 voci)
ACL anonimo mosquitto · VOLUME+containerd · force-recreate · PYTHONPATH · EventBus alias · DomainEvent metrics · cgroup v2 vs knob v1/free fuorviante · bind RO parent vs mount annidati · grafana __FILE · rsync checkout · Trixie.

### Debito emerso
- ros2-bridge/gazebo: primo avvio reale ancora da verificare (certificati/modelli)
- Password admin Grafana da cambiare (default attivo)
- Heartbeat timeout node2-6 attesi finché firmware ESP32 non esiste (v0.4.0)

### Prossimi passi consigliati
T-003 unit test core domain (v0.3.0) · verifica containers secondari · T-014 firmware Node 2 compilabile.

---

## Sessione: 2026-08-25 (5) — ADR-016: Pi OS Lite 64-bit + NVMe USB3

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-08-25 |
| Versione progetto | 0.2.0 → v0.3.0 in corso |
| Obiettivo | Decisione Livello C sull'OS del Nodo 1 proposta dall'owner (Pi OS invece di Ubuntu) + storage NVMe |

### Attività completate
1. **Analisi comparativa** Ubuntu Server 24.04 vs Pi OS Lite vs Pi OS desktop per il carico OpenJ5: ROS container-only (ADR-015) elimina il vantaggio storico Ubuntu; libcamera/picamera2 (roadmap v0.5.0) favorevole a Pi OS; desktop escluso (headless, risparmio ~0,5-1GB RAM). Owner confermato: **Pi OS Lite 64-bit (Bookworm)**.
2. **ADR-016 creato**: decisione OS + storage NVMe USB3 (~300-400 MB/s vs SD), alternative considerate, conseguenze (finestra supporto Debian, cmdline.txt obbligatorio per cgroup memoria, recovery bootloader via SD), aggiornati INDEX.md e tabella ADR in ARCHITECTURE.md.
3. **DEPLOYMENT.md riscritto** per Pi OS Lite+NVMe: flash diretto NVMe con Imager (customizzazione headless), recovery one-time bootloader USB da SD solo se necessario, §4.1 patch `cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory` su `/boot/firmware/cmdline.txt` con test verifica limite 256MB, watchdog via `dtparam=watchdog=on`, TRIM check enclosure (`lsblk --discard`), benchmark `hdparm`, UFW (non preinstallato su Pi OS), troubleshooting esteso (NVMe sotto carico = alimentazione).
4. **bootstrap_rpi4.sh aggiornato**: guardia anti-Ubuntu (rifiuta con rimando ad ADR-016), rilevazione Bookworm/arm64, patch idempotente cmdline.txt (riga singola verificata) + config.txt watchdog con flag REBOOT_REQUIRED e istruzioni post-reboot.
5. Coerenza repo: README (prerequisiti + quick start path corretto: `firmware/node1_robot_core/docker`), GOALS G1.1, ARCHITECTURE.md (C4 context + deployment diagram), PROJECT_MEMORY §4/timeline, NEXT_TASK T-017/T-018, CHANGELOG.

### File creati (1)
`docs/adr/ADR-016-pios-lite-nvme-node1.md`

### File modificati
`docs/deployment/DEPLOYMENT.md` (rewrite), `scripts/deploy/bootstrap_rpi4.sh` (rewrite),
`README.md`, `governance/GOALS.md`, `docs/architecture/ARCHITECTURE.md`,
`docs/adr/INDEX.md`, `CHANGELOG.md`, `docs/NEXT_TASK.md`, `docs/PROJECT_MEMORY.md`

### Decisioni prese
- **ADR-016** (Livello C, approvato dall'owner): Pi OS Lite 64-bit Bookworm come OS di riferimento Nodo 1; NVMe USB3 storage primario; SD = solo recovery bootloader; variante desktop esclusa (aggiungibile a posteriori senza reflash).
- Ubuntu resta alternativa documentata nell'ADR, non percorso supportato.

### Problemi riscontrati
Nessuno bloccante.

### Debito tecnico
Invariato; T-018 ora include verifica boot USB + test cgroup.

### Prossimi passi consigliati
T-018 validazione su hardware reale (Pi OS Lite su NVMe), oppure T-003 unit test core domain.

---

## Sessione: 2026-08-25 (4) — Preparazione deploy Raspberry Pi 4 (Node 1)

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-08-25 |
| Versione progetto | 0.2.0 → v0.3.0 in corso |
| Obiettivo | Definire come preparare il RPi4 8GB come Nodo 1 (openj5-core) |

### Attività completate
1. **T-017 ✅**: percorso di deploy completo:
   - `docs/deployment/DEPLOYMENT.md`: hardware richiesto (SSD consigliato, PSU, cooling), flash Ubuntu Server 24.04 LTS arm64 headless con Pi Imager, nota UID/GID 1000 per permessi certificati mosquitto, preparazione sistema (timezone, journald volatile per usura SD, watchdog HW), installazione Docker ufficiale, checkout/rsync codice, generazione segreti+certificati sul dispositivo, `docker compose up -d`, tabella verifica (API/Swagger/MQTT/Grafana/Prometheus/Loki), layout porte host + hardening UFW, troubleshooting specifico RPi (da KNOWLEDGE_BASE), prossimi passi (certificati ESP32 già pronti per nodi 2–6).
   - `scripts/deploy/bootstrap_rpi4.sh`: automatizza sezioni 3–7 in modo idempotente (preflight arch/os/spazio disco, apt full-upgrade, journald volatile, Docker via get.docker.com, gruppo docker, clone/pull repo, generate.sh segreti+certs con fix permessi chiavi per uid 1883/gid 1000, compose up --build). Sintassi verificata (`bash -n`).
2. `DEPLOYMENT.md` aggiunto alla doc gate CI (`scripts/check_docs.sh`).

### File creati (2)
`docs/deployment/DEPLOYMENT.md`, `scripts/deploy/bootstrap_rpi4.sh`

### File modificati
`scripts/check_docs.sh`, `CHANGELOG.md`, `docs/NEXT_TASK.md`, `docs/PROJECT_MEMORY.md`

### Decisioni prese
- Ubuntu Server **24.04 LTS arm64** come riferimento operativo (README indicava 22.04/24.04; si standardizza sul 24.04).
- SSD USB3 raccomandato (PostgreSQL+Prometheus su SD = usura); journald volatile di default nel bootstrap.
- Segreti e certificati generati SEMPRE sul dispositivo, mai trasferiti né committati.
- Nuovo task **T-018** (validazione su hardware fisico): il deploy resta "fatto" a livello documentale/script finché non eseguito su un Pi reale.

### Problemi riscontrati
Nessuno bloccante.

### Debito tecnico
Invariato; T-018 aggiunto come dipendenza operativa per dichiarare il Nodo 1 "up".

### Prossimi passi consigliati
Eseguire bootstrap sul Pi reale (T-018) oppure continuare v0.3.0 con T-003 (unit test core domain).

---

## Sessione: 2026-08-25 (3) — T-015 riparazione framework plugin

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-08-25 |
| Versione progetto | 0.2.0 → v0.3.0 in corso |
| Obiettivo | T-015: definire i contratti base del framework plugin e rendere importabile `src/plugins` |

### Attività completate
1. **T-015 ✅**: creato `src/plugins/base.py` con i contratti definiti UNA sola volta (ADR-007): `IPlugin`, `IConfigurablePlugin`, `ILifecyclePlugin`, `IPluginManager`, `IPluginRegistry`, `PluginMetadata/State/Type/Dependency/Permission/ConfigSchema/Health`, `PluginContext` unificato (allineato ai campi effettivamente costruiti da PluginManager). `interfaces.py` ora estende solo contratti specifici; `manager.py` implementa. Import circolare eliminato; per-file-ignores rimossi da pyproject.toml.
2. **Bug latenti a cascata corretti** (emersi rendendo il package importabile — il modulo non era mai stato eseguito):
   - `events.py`: rimosso `slots=True` (rompeva `super()` zero-arg in OGNI sottoclasse evento → ogni istanziazione falliva); `EVENT_SCHEMAS` non legge più attributi di classe tramite member descriptor; aggiunti `FaceRecognizedEvent`/`ObjectGraspedEvent`; export `DockingCompletedEvent` → `DockingCompleteEvent`.
   - `commands.py`: aggiunti `CommandHandler`/`QueryHandler` (contratti usati dai bus) e `GetFirmwareVersionsQuery` mancante.
   - `entities.py`: risolto TypeError dataclass inheritance con campi kw_only; soddisfatti import `CalibrationData`/`PluginMetadata` come value objects di dominio.
   - `services.py`: fix `math.time()` → `time.time()`; implementati `IKinematicsService`+`KinematicsService` (FK via parametri DH, IK numerica damped least squares) e `IMotionPlanner` ABC.
3. **Verifiche**: smoke test FK/IK contro soluzione analitica (residuo 0.9mm su catena 2-link), quaternion yaw-90 corretto, generazione traiettoria ok; lifecycle plugin end-to-end (load→enable→disable→unload→discover) su plugin dummy in temp dir; `ruff check` pulito su tutto; doc-check OK.
4. **Self-review**: durante lo sviluppo il lint ha beccato 2 bug nel nuovo codice cinematica (variabile quaternion sbagliata, formula DLS con indici errati + segno Jacobiano da differenze d'errore): tutti corretti e verificati numericamente.

### File creati (1)
`src/plugins/base.py`

### File modificati
`src/plugins/{interfaces,manager,__init__}.py`, `pyproject.toml`,
`src/core/domain/{events,commands,entities,services,value_objects,__init__}.py`,
`CHANGELOG.md`, `docs/NEXT_TASK.md`, `docs/PROJECT_MEMORY.md`

### Decisioni prese
- Contratti plugin in `base.py` (non in interfaces né manager): direzione dipendenze univoca base ← interfaces ← (nulla), base ← manager.
- `PluginMetadata` esiste in due proiezioni: VO immutabile nel dominio (`value_objects`) per l'aggregato `Plugin`, versione ricca nel framework (`plugins/base`). Il dominio non dipende dal layer plugin (regola P1).
- IK numerica in radianti internamente (damping tarato per rad); API resta in gradi.

### Problemi riscontrati
Nessuno bloccante.

### Debito tecnico
Rimosso: plugin framework contracts (T-015 ✅). Rimane: formatter (T-016), SDK buses (T-010), MQTT reconnect (T-011), persistenza config (T-012), firma plugin (T-013), firmware skeleton (T-014/T-007).

### Prossimi passi consigliati
T-003 unit test core domain (ora che tutto è importabile) → completare v0.3.0.

### Prompt di continuità
`docs/CONTINUATION_PROMPT.md`.

---

## Sessione: 2026-08-25 (2) — T-001 + base pipeline CI

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-08-25, sessione successiva alla conformità governance |
| Versione progetto | 0.2.0 → v0.3.0 iniziata |
| Obiettivo | T-001 (CHANGELOG onesto) + T-002 (pipeline CI base) |

### Attività completate
1. **T-001 ✅**: CHANGELOG "Unreleased" non dichiara più CI/test inesistenti; contiene solo lavoro reale + sezione Planned che rimanda a ROADMAP/NEXT_TASK.
2. **Lint e difetti reali**: installato ruff 0.16.4, analizzati `src/` + `robot_core/`: 174 violazioni E/F. Corrette le meccaniche sicure:
   - 14 classi Query mancanti aggiunte a `src/core/domain/commands.py` (+ export in `__init__`, + import in `sdk/robot.py`) — percorsi SDK che avrebbero sollevato NameError
   - Import mancanti: `Protocol` (event_bus), `Path`/`Any` (database.py), `uuid` (ota.py), `ABC`/`abstractmethod` (robot_core/plugins.py)
   - Sostituiti star-import in `robot_core/api/` con import espliciti
   - 79 auto-fix ruff (unused imports/variables); variabile morta `rs` in rest.py rimossa
   - 4 import `Result` a fine file spostati in testa (config_service, event_bus, communication, state_machine)
3. **T-002 🟡 parziale**: creati `.github/workflows/ci.yml` (job python-lint / doc-check / docker-build) e `scripts/check_docs.sh` (esistenza doc obbligatorie + verifica link ADR nell'INDEX). Verificati localmente: `ruff check` pulito, doc-check OK, YAML valido.
4. **Scoperta debito grave documentata**: framework plugin `src/plugins/` non importabile — `interfaces.py` e `manager.py` si importano a vicenda classi mai definite (IPlugin, IPluginManager, IPluginRegistry, PluginMetadata/State/Type/Dependency/Permission/ConfigSchema/Health). Contenimento statico: per-file-ignores in `pyproject.toml`; riparazione = nuovo task **T-015**.
5. **T-007 bloccato**: skeleton firmware Node 2 non compilabile (manca `head_controller.hpp`, sorgenti elencati nel CMakeLists, direttive `project()`): job ESP-IDF rinviato a dopo T-014.

### File creati (3)
`.github/workflows/ci.yml`, `scripts/check_docs.sh`, `pyproject.toml`

### File modificati
`CHANGELOG.md`, `docs/NEXT_TASK.md`, `PROJECT_STATUS.md`, `docs/PROJECT_MEMORY.md`,
`src/core/domain/commands.py`, `src/core/domain/__init__.py`, `src/sdk/robot.py`,
`src/eventbus/event_bus.py`, `src/gateway/communication.py`,
`src/statemachine/state_machine.py`, `src/config/config_service.py`,
`firmware/node1_robot_core/docker/src/robot_core/{plugins,database,ota}.py`,
`firmware/node1_robot_core/docker/src/robot_core/api/{rest,__init__,websocket}.py`
(websocket.py via auto-fix)

### Decisioni prese
- Ruff baseline pragmatica: regole E4/E7/E9/F; `ruff format` NON adottato ora (36 file) → T-016.
- F821 ignorato solo in `src/plugins/interfaces.py`/`manager.py` come contenimento temporaneo tracciato (T-015).
- Job firmware escluso dalla CI finché lo skeleton non compila (niente build finte verdi).

### Problemi riscontrati
- Docker daemon locale non attivo: build robot-core non rieseguibile in locale (già validata il 13/08 con stesso contesto/Dockerfile).

### Debito tecnico
Vedi `docs/PROJECT_MEMORY.md` §10 aggiornato. Nuovi: plugin framework contracts (T-015), formatter (T-016).

### Prossimi passi consigliati
T-015 (riparare contratti plugin, ~1g) poi T-003 (unit test core domain) per completare v0.3.0.

### Prompt di continuità
`docs/CONTINUATION_PROMPT.md` (aggiornare "Stato attuale" alla prossima chiusura).

---

## Sessione: 2026-08-25 (1) — Conformità alla Project Constitution (Punto 1)

| Campo | Valore |
|-------|--------|
| Data/ora | 2026-08-25 |
| Versione progetto | 0.2.0 (stabilizzata) — nessun bump: attività documentale |
| Obiettivo sessione | Colmare il divario tra le regole interne del progetto e la realtà del repository (punto 1 del piano concordato): documenti di continuità mancanti, file governance vuoti, ADR dichiarati ma assenti, INDEX con link rotto |

### Attività completate
1. Analisi completa del repository (documenti, sorgenti `src/` + `robot_core/`, firmware, docker, git history) e ricostruzione della storia del progetto.
2. Riempiti i 4 file governance vuoti:
   - `governance/ARCHITECTURAL_PRINCIPLES.md` (14 principi P1–P14 + regole dipendenze + Design Authority checklist)
   - `governance/CODING_STANDARD.md` (SOLID/Clean Code, regole Python e C++20, fail-safe, sicurezza, commit, Definition of Done)
   - `governance/CONSTRAINTS.md` (vincoli hardware, software, meccanici, elettronici, processo, economici, safety)
   - `governance/NAMING_CONVENTIONS.md` (lingue, Python, C++, topic MQTT, eventi, config, Docker, Git, nomi documenti)
3. Scritti gli 11 ADR mancanti dichiarati da INDEX.md e ARCHITECTURE.md (inglese, formato TEMPLATE):
   - ADR-005 HAL · ADR-006 Robot SDK facade · ADR-007 Plugin architecture · ADR-008 Configuration-driven · ADR-009 State machine per nodo · ADR-010 Digital Twin nativo · ADR-011 OTA firmato+rollback · ADR-012 FreeCAD parametrico · ADR-013 Security mTLS/JWT/OTA/fail-safe · ADR-014 Python core + C++ firmware · ADR-015 MQTT transport primario.
   - I contenuti derivano esclusivamente da decisioni già documentate nel repo (README, ARCHITECTURE.md, MASTER_PROMPT, codice esistente): nessuna nuova decisione architetturale introdotta → nessun nuovo livello di decisione richiesto.
4. Corretto link rotto in `docs/adr/INDEX.md` (ADR-002: filename reale `ADR-002-six-node-distributed-architecture.md`). Verificato che tutti i 15 link dell'INDEX risolvono.
5. Creati i documenti di continuità obbligatori (finora assenti):
   - `docs/PROJECT_MEMORY.md` — memoria permanente: visione, architettura, 15 decisioni, hardware reference, pattern, regole, convenzioni, stato, debito tecnico.
   - `docs/NEXT_TASK.md` — 15 attività con ID T-001…T-024, priorità, dipendenze, stime, stato.
   - `docs/KNOWLEDGE_BASE.md` — lezioni della sessione Docker 2026-08-13 (healthcheck mosquitto, permessi certificati, Loki/OTEL), procedure (certificati, stack up, nuovo ADR, chiusura sessione), best practice, errori da evitare, FAQ.
   - `docs/CONTINUATION_PROMPT.md` — prompt completo di continuità rigenerabile.
   - `docs/SESSION_REPORT.md` — questo file.

### File creati (18)
`governance/ARCHITECTURAL_PRINCIPLES.md`, `governance/CODING_STANDARD.md`, `governance/CONSTRAINTS.md`, `governance/NAMING_CONVENTIONS.md`,
`docs/adr/ADR-005-hardware-abstraction-layer.md`, `ADR-006-robot-sdk-facade.md`, `ADR-007-plugin-architecture.md`, `ADR-008-configuration-driven.md`, `ADR-009-state-machine-per-node.md`, `ADR-010-digital-twin-native.md`, `ADR-011-ota-signed-firmware.md`, `ADR-012-freecad-parametric-cad.md`, `ADR-013-security-mtls-jwt-signed-ota.md`, `ADR-014-python-core-cpp-firmware.md`, `ADR-015-mqtt-primary-transport.md`,
`docs/PROJECT_MEMORY.md`, `docs/NEXT_TASK.md`, `docs/KNOWLEDGE_BASE.md`, `docs/CONTINUATION_PROMPT.md`, `docs/SESSION_REPORT.md`.

### File modificati (1)
`docs/adr/INDEX.md` (solo fix link ADR-002; gli ADR non sono stati toccati).

### Decisioni prese
- Lingua: governance/memoria in italiano, ADR/doc tecnica in inglese (coerenza con i file esistenti).
- ADR-005→015 scritti come "Accepted" con data 2026-07-15 coerente con ARCHITECTURE.md (le decisioni erano già operative; la sessione ne formalizza solo la registrazione).
- `PROJECT_STATUS.md` resta nella root (come già referenziato ovunque) anziché duplicarlo in `/docs`: deviazione nota dalla PERSISTENT_PROJECT_MEMORY §PROJECT STATUS, accettata per coerenza con i link esistenti.

### ADR creati
11 (elencati sopra). Nessun ADR modificato.

### Problemi riscontrati
- Nessuno bloccante. Nota: `firmware/README.md` è uno script Python con stringhe embeddate, non una vera documentazione (da rivedere in futuro).

### Debito tecnico (invariato in questa sessione)
- Nessun test automatizzato nel repo; CHANGELOG "Unreleased" dichiara CI/test inesistenti (→ T-001).
- Stub codice: firma plugin/sandbox, buses SDK, auto-reconnect MQTT, persistenza config, NATS bus (→ T-010…T-013).
- Firmware nodi 3–6 assenti; OTA client ESP32 parziale; CAD/elettronica assenti.

### Funzionalità incomplete
Nessuna nuova; questa sessione era puramente documentale/governance.

### Prossimi passi consigliati
Vedi `docs/NEXT_TASK.md`: T-001 (correggere CHANGELOG) → T-002/T-007 (CI) → T-003…T-006 (test, rilascio v0.3.0).

### Prompt di continuità per la prossima sessione
Usare `docs/CONTINUATION_PROMPT.md` (sezione "PROMPT DA COPIARE").
