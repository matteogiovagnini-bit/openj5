# PROJECT_MEMORY — Memoria Permanente OpenJ5

> **Questo documento è la memoria permanente del progetto. Mai perderlo.**
> Aggiornare a ogni cambiamento significativo. Ultimo aggiornamento: 2026-10-13

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

### Distribuita a 7 nodi
| Nodo | Hardware | Ruolo |
|------|----------|-------|
| 1 | Raspberry Pi 4 8GB (Ubuntu + Docker) | Robot Core: AI, Vision, Speech, Planning, Behavior, broker MQTT, REST/WebSocket API, DB, Event Bus, Plugin Manager, OTA Manager, Digital Twin |
| 2 | ESP32-S3 | Head: 6 servi (neck Y/P/R, eyes H/V, eyelids), LED, display, mic I2S |
| 3 | ESP32-S3 | Braccio destro: 6 servi (shoulder P/R/Rot, elbow, wrist, gripper) |
| 4 | ESP32-S3 | Braccio sinistro (mirror del 3) |
| 5 | ESP32-S3 | Torso: 4 servi, LED, fan, INA219 + DS18B20, sensori |
| 6 | ESP32-S3 | Cingoli: L298N + 2 motori DC con encoder, IMU, ToF, bumper (firmware ESP32-S3; **ADR-019**) |
| 7 | ESP32-S3 | Balance Controller (ADR-017): NEMA17 + A4988 + IMU MPU6050 sul corpo, livellamento attivo del corpo vs gravità |

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
| ADR-002 | Architettura distribuita a 6 nodi (RPi4 + 5× ESP32) — **MCU table superato da ADR-019** |
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
| ADR-016 | Pi OS Lite 64-bit Bookworm + NVMe USB3 per Node 1 |
| ADR-017 | Node 7 Balance Controller: NEMA17+A4988+MPU6050 su ESP32-S3, corpo livellato vs gravità |
| ADR-018 | Motor HAL Port (`IMotorDriver`): shape del contratto, collocazione in `src/hardware/hal/`, parità Python↔C++ |
| ADR-019 | Tutti i nodi attuatori su **ESP32-S3**; il Raspberry Pi (Node 1) è **solo cervello**; l'attuazione motori passa dal firmware Node 6, non dal Pi |
| ADR-020 | **Satellite vocale** esterno (Note 10): Home Assistant + Wyoming (Piper TTS / faster-whisper STT) + app HA Companion con wake word on-device; non è un nodo, l'accessorio vocale parla col robot via MQTT |

Regola: gli ADR sono immutabili; una decisione che li supera genera un nuovo ADR "Superseded by".

---

## 4. Hardware Utilizzato (reference)

- Raspberry Pi 4 8GB, **Raspberry Pi OS Lite 64-bit (Bookworm)** (ADR-016, sostituisce la spec Ubuntu iniziale), boot da NVMe USB3 (~300-400 MB/s), Docker Compose; cgroup memory abilitati via cmdline.txt per i limiti dei container.
- 6× ESP32-S3, ESP-IDF 5.2+, FreeRTOS @1kHz (ADR-019: tutti i nodi attuatori sullo stesso MCU).
- PCA9685 (I2C 0x40–0x43 per nodi 2–5), servi hobby standard.
- L298N + 2 motori DC con encoder (nodo 6), MPU6050/ICM20948, VL53L0X ×2.
- NEMA17 + A4988 (STEP/DIR/ENABLE) + 2× MPU6050 (nodo 7, ADR-017); IMU sul corpo per il livellamento attivo.
- Mosquitto 2.0, Redis 7 (Streams), PostgreSQL 16, FastAPI/Uvicorn, structlog.
- Osservabilità: Prometheus, Grafana, Loki+Promtail, OpenTelemetry Collector.
- Simulazione: Gazebo Harmonic headless (immagine OCI ufficiale arm64).
- **Satellite vocale — accessorio esterno (ADR-020)**: Samsung Galaxy Note 10 (SM-N970F, Exynos 9825, 8 GB RAM, Android 12/API 31, schermo rotto → headless). Termux + `proot-distro` con container `python:3.14-slim` che ospita **Home Assistant Core 2026.10.1** + **wyoming-piper** (TTS `it_IT-serena-medium`) + **wyoming-faster-whisper** (STT `small`, `it`); app **HA Companion** come assistente Android con wake word **on-device** "Okay Nabu". Non è un nodo del robot (ADR-019): è il terminale voce verso Node 1 via MQTT/REST. Codice, script e asset: `voice_satellite/`.

**Banco Nodo 6 (storico, T-019/T-025)**: 2× motoriduttore DC **12V 300rpm XD-37GB520** + modulo **L298N** + batteria **LiPo 3S** (11,1-12,6V). Il driver host `src/hardware/drivers/l298n.py` (config `config/bench/tracks.json`, demo `scripts/demo/tracks_bench.py`) è stato il primo driver HAL reale del progetto, ma per **ADR-019** è **ritirato**: il Pi non attua i motori. La produzione è il firmware Node 6 su **ESP32-S3** (`firmware/node6_tracks/`); il port host `IMotorDriver` + `MockMotorDriver` restano come astrazione/Digital Twin e contratto di parità Python↔C++. Cablaggio e procedure: `docs/hardware/BENCH_TRACKS.md` e `docs/hardware/NODE6_ESP32_WIRING.md` (ESP32-S3).

**Nodo 7 Balance (ADR-017, design 2026-09-21)**: NEMA17 + A4988 + MPU6050 su **ESP32-S3 dedicato**; riduzione cinghia/pulegge **20T→80T** (1:4, ~−35..+35°, 12800 jsteps/giro → 35,56 jsteps/°). Il PID di livellamento gira **sul nodo** a 100 Hz (reference vs gravità); il Pi invia solo comandi logici (`level/tilt/stow/stop`). Software Python già pronto: `IStepperDriver` (HAL), driver benchmark `a4988.py`, mock `mock_stepper.py`, simulatore loop `src/hardware/sim/leveling.py`, config `config/node7_balance/node.json` + `config/bench/balance.json`, `BodyAPI` in SDK (`robot.body`). Firmware ESP-IDF e CAD = follow-up (T-026/T-027).

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
- Sessione 2026-08-25 (4): **ADR-016** — OS di riferimento Nodo 1 passa a Raspberry Pi OS Lite 64-bit + storage NVMe USB3; DEPLOYMENT/bootstrap riscritti; ROS confermato container-only.
- Sessione 2026-08-26: **PRIMO BOOT REALE del Robot Core su RPi4 8GB** (T-018): Pi OS Lite Trixie su NVMe, boot USB nativo, stack Docker completo healthy, API HTTPS live con {"status":"ok"}, limiti memoria cgroup v2 attivi. 10 fix reali documentati in KNOWLEDGE_BASE §1-bis (ACL anonimo mosquitto, VOLUME+containerd image store, PYTHONPATH, EventBus alias, DomainEvent metriche...). Robot Core = **OPERATIVO**.
- Sessione 2026-08-26 (banco Nodo 6): **primo driver HAL reale** `L298NDriver` (`src/hardware/drivers/l298n.py`, velocià normalizzata -1..+1 con rampe), demo interattiva `scripts/demo/tracks_bench.py` (w/s/a/d/x/q + velocità), config GPIO in `config/bench/tracks.json` (zero numeri magici), guida cablaggio completa `docs/hardware/BENCH_TRACKS.md` (L298N+2 motori DC 12V
[truncated] 300rpm+LiPo 3S), procedure spegnimento/riaccensione in DEPLOYMENT §11. **Il primo movimento fisico dei motori è ancora da eseguire** (cablaggio pronto, demo da lanciare).
- Sessione 2026-09-21 (design Nodo 7 Balance): **ADR-017** — nuovo Node 7 (ESP32-S3 dedicato) con NEMA17+A4988+MPU6050 per il livellamento attivo del corpo vs gravità sui cingoli (±35°, riduzione 1:4 cinghia/pulegge, PID 100 Hz sul nodo, comandi logici). Software Python consegnato e testato: `IStepperDriver` (HAL), `A4988StepperDriver` bench + `MockStepperDriver`, simulatore `src/hardware/sim/leveling.py`, config (`node7_balance/node.json`, `bench/balance.json`, `hal.json`, `topics.json` node7), `BodyAPI` in SDK (`robot.body.level/tilt/stow/stop`), nodo 7 nell'orchestratore robot_core; 8 unit test verdi (ruff clean). Firmware ESP-IDF Node 7 (T-026) e CAD/meccanica (T-027): follow-up design Lifecycle B/C.
- Sessione 2026-09-22 (**T-003 — suite unit test core domain**): `tests/unit/` creato (conftest + 6 moduli: value objects, events, commands, entities, services, repositories) con **149 test e 100% coverage su `src/core/domain/`** (gate CI ≥90%); config pytest/coverage in `pyproject.toml`; job `python-tests` aggiunto a CI (ruff ora linta anche `tests/`). I test hanno scoprerto e fatto emergere **5 bug latenti tutti corretti nella stessa sessione**: (1) `Command.__post_init__` abstract → 9 comandi istanziabili (incl. `emergency_stop()`); (2) `to_dict()` perdeva i campi delle sottoclassi + `from_dict()` fragile; (3) `EVENT_CATEGORIES` sempre BUSINESS; (4) IK DLS con `J·Jᵀ` sbagliato (righe) invece di `JᵀJ` (giunti) → zigzag senza convergenza, + line search backtracking e cap `IK_MAX_STEP_RAD`; (5) profilo triangolare overshoot → helper `_rest_to_rest_profile()`. Debito emerso: **3 copie duplicate di `DomainEvent`** (dominio, eventbus host, bundle robot_core) → nuovo task **T-028**.
- Sessione 2026-09-23 (**T-026 — firmware Node 7 Balance, ADR-017**): consegnati schema di collegamento (`docs/hardware/BENCH_BALANCE.md`: pin STEP/DIR/EN GPIO4/5/6, I2C GPIO8/9, ponti A4988, alimentazione+Vref, safety, bring-up), logica pura in `firmware/common/` (stepper ramp/slew/brake, Madgwick, FSM ADR-009, PID parità sim — **36 check host** via `scripts/test/host_firmware.sh`), glue ESP (A4988 esp_timer, MPU6050, WiFi, MQTT mTLS opzionale) e progetto ESP-IDF completo `firmware/node7_balance/` (task 100 Hz + IMU 200 Hz, comandi logici level/tilt/stow/stop, fail-safe deadman 250 ms/watchdog/limite ±1244 jsteps, bobine off al boot, Kconfig↔node.json sincronizzato). CI: job `firmware-host-tests` + `firmware-node7-build` (container `espressif/idf:v5.2.2`); test parità `tests/unit/test_node7_config_sync.py` (8 test). Fix latenti emersi: (1) limiti viaggio **±4445 jsteps = ±125°** (commento diceva 35°) → ±1244; (2) ACL mosquitto con vecchi topic `openj5/nodeN/#` (nessun match con `openj5/v1/...`) e senza user `node7`; (3) `generate.sh` senza cert node7; (4) README firmware/documentavano file fantasma (19 sorgenti inesistenti in `common/CMakeLists.txt`, `install_esp_idf.sh`) — causa radice di T-007/T-014. Nuovo debito **T-029** (`trapezoid_velocity` Python stateless + derivative kick PID Python). Test bench motori T-025/T-004/T-005 saltati su richiesta utente. Follow-up stessa sessione: caricamento da **VSCode+PlatformIO** → `firmware/node7_balance/platformio.ini` (piattaforma `espressif32` 6.12.0 = ESP-IDF **v5.5**, board `esp32-s3-devkitc-1`, `src_dir = main`, riusa intatti CMake/Kconfig/`sdkconfig.defaults`), procedura flash riscritta a due strade nel README Node 7 (**A** PlatformIO consigliata / **B** `idf.py`), vincolo IDF 5.5-locale ↔ 5.2.2-CI annotato nel file + presidiato dal nuovo test `test_platformio_ini_matches_project`; legacy `driver/i2c.h` verificato sui tag target (v5.2.2 e v5.5): presente e non deprecato → nessuna migrazione MPU6050. Prima `pio run` reale in 4 tentativi: (1) configure `esp_mqtt` → il componente IDF si chiama **`mqtt`** (corretto in 3 CMakeLists); (2) `-Wpedantic -Werror` sugli header IDF passati come `-I` + simboli Kconfig assenti quando `n`/`APP_PROJECT_VER` → loop `-isystem` sul CMakeLists condiviso dopo `project()` (esclusi `main`/`common`), `#ifdef` sui 3 bool, versione da `esp_app_get_description()` (+`esp_app_format`), `CONFIG_ESPTOOLPY_FLASHSIZE_8MB` + gitignore `sdkconfig.*`; (3) 4 errori API nel mai-compilato `firmware/common/` (`std::strlcpy`→`snprintf`, member `i2c_config_t` scambiati, `esp_timer_start`→`_start_periodic`, `ESP_EVENT_ANY_ID`→`MQTT_EVENT_ANY`, tutti rivisti su entrambi i tag) → **`pio run` verde: SUCCESS 137,9 s** (RAM 11,2%, flash 88,8% slot factory 1 M, immagine a 8 MB). KNOWLEDGE_BASE §1-sexies. Working tree NON committato (commit solo su richiesta).
- Sessione 2026-10-07 (**T-029 — parità Python↔firmware Node 7**): `src/hardware/hal/stepper.py` ora espone `slew`/`brake_bound`/`position_velocity_target` come mirror 1:1 di `firmware/common/include/hal/stepper_logic.hpp` e `trapezoid_velocity(v_now, steps_remaining, vmax, accel, dt)` con lo stato `v_now` nel chiamante (`a4988.py`, `mock_stepper.py`) — da fermo prima riceveva un colpo a 1410 steps/s; `sim/leveling.py` con guardia `first_` (specchio di `balance_pid.hpp:49`, reset al re-enable) + clamp output ±1600 che il C++ aveva. Test: `test_balance_control.py` 8→11, nuovo `test_stepper_parity.py` (9 test sui vettori di `host_test.cpp`); gate **170 test, 100% coverage `core.domain`**, ruff pulito, host firmware invariati (nessun ADR nuovo: confermati ADR-005/014/017). Debito emerso → nuovo **T-030**: loop `while abs(target-pos) > 0` su float in `a4988.py:120` **non termina mai** (preesistente, non introdotto da T-029; il C++ usa `position_snap_steps` in `a4988_driver.cpp:112`) — impatta `scripts/demo/balance_bench.py`.
- Sessione 2026-10-09 (**T-025 Fase 1 — port HAL motori cingoli Node 6**): consegnata la parte offline del primo movimento fisico. Nuovo **port puro `IMotorDriver`** (`src/hardware/hal/motor.py`: `motor_names`/`initialize`/`set_velocity`/`get_velocity`/`stop_all`/`brake_all`/`shutdown`, velocità signed normalizzata −1..+1) con helper condivisi `clamp_velocity`/`motor_levels`/`ramp_schedule` (ri-esportati da `hal/__init__.py`); **ADR-018** (Accepted 2026-10-09) registra shape, collocazione in `src/hardware/hal/` e parità Python↔C++ futura. Refactor `src/hardware/drivers/l298n.py`: import gpiozero **lazy** (modulo importabile e testabile senza lib GPIO), `channel_factory` iniettabile, `pwm_frequency_hz`/`ramp_step`/`ramp_seconds` da config, `shutdown()` idempotente, più fix di un bug di percorso (`parents[2]`→`parents[3]`). Nuovo `MockMotorDriver` CI-safe (`mock_motor.py`, rampe analitiche senza sleep) = Digital Twin del banco, registrato in `config/common/hal.json`. `config/bench/tracks.json` guadagna `pwm_frequency_hz` (1000), `ramp_step` (0.1) e la sezione `demo` (speed/min_speed/max_speed/speed_step); `scripts/demo/tracks_bench.py` ora con `--selftest` (sequenza scriptata non interattiva, SSH-safe, niente tty) e `--mock`, più `--seconds`/`--speed`. Test: 4 nuovi moduli (`test_motor_hal.py`, `test_l298n_driver.py`, `test_mock_motor.py`, `test_tracks_demo.py`) → **213 test, 100% coverage `core.domain`**, ruff pulito, doc gate OK. Debiti collaterali: **T-031** (path default `a4988.load_driver` → `parents[3]`, 0.25h) e **T-032** (port C++ `motor_driver.hpp`/`motor_logic.hpp` + parity test, legato a T-022). **Resta il bench fisico sul Pi** (ruote sollevate). *(Superato dalla sessione successiva, **ADR-019** → vedi voce sotto: il percorso host Pi e il bench `tracks_bench.py` sono ritirati; il bench fisico passa al firmware Node 6 ESP32-S3.)*
- Sessione 2026-10-09 (2) (**ADR-019 — tutti i nodi ESP32-S3, Pi solo cervello**): decisione **Level C** dell'owner. Il Pi (Node 1) non attua più i motori: ritirato il percorso host `src/hardware/drivers/l298n.py` + `scripts/demo/tracks_bench.py` + `config/bench/tracks.json` (+ test `test_l298n_driver.py`/`test_tracks_demo.py`). L'attuazione reale è il firmware Node 6 **ESP32-S3** (`firmware/node6_tracks/`: env `node6`, comandi logici `forward/backward/spin_left/spin_right/stop`, topic `openj5/v1/tracks/{cmd,evt,telemetry,state}`, watchdog 1000 ms, pin map approvata in ADR-019 §3) + HAL motori C++ in `firmware/common/` (`hal/motor_driver.hpp`, `hal/motor_logic.hpp`, `drivers/l298n_driver.cpp`). `IMotorDriver` + `MockMotorDriver` **restano** come astrazione host/Digital Twin e contratto di parità Python↔C++ (ADR-005/010/018). Nuove/aggiornate doc: `docs/adr/ADR-019-all-nodes-esp32-s3.md`, `docs/hardware/NODE6_ESP32_WIRING.md`, `docs/hardware/BENCH_TRACKS.md` (riscritto su ESP32-S3). Conteggi reali: **197 test unit** (100% coverage `core.domain`; −16 per i 2 moduli motori host rimossi) e **53 check host firmware** (da 36, +17 motori Node 6). Nuovo task **T-033** (validazione on-device Node 6, ruote sollevate); **T-022/T-032** restano **Parziali** (bring-up motori consegnato; encoder/PID/odometria/IMU/ToF/bumper e il modulo di parità Python↔C++ dedicato ancora mancanti). Annotati come storici (non riscritti) ADR-002 (MCU table), ADR-018 (body) e KNOWLEDGE_BASE §1-ter.
- Sessione 2026-10-13 (**ADR-020 — satellite vocale Note 10, Fasi 0–5**): realizzato il front-end vocale esterno di OpenJ5 su un Samsung Note 10 headless (schermo rotto). Stack: **Termux + proot-distro** (container OCI `python:3.14-slim`, Debian 13, Python 3.14.8) con **Home Assistant Core 2026.10.1** in `/opt/ha`; **wyoming-piper** (TTS `it_IT-serena-medium`, TCP 10200) e **wyoming-faster-whisper** (STT `small`, `it`, TCP 10300); integrazioni Wyoming in HA, pipeline Assist **"Assistente Locale"** (`01m4tje8tnx44erdd0v45fqtm1`); **HA Companion 2026.8.4** impostata come **assistente Android predefinito** con **wake word on-device "Okay Nabu"** (microWakeWord); whitelist batteria via `dumpsys deviceidle`. **Test end-to-end superato** (foreground e background): wake word → STT → intent → TTS dallo speaker; logcat conferma `assist_pipeline/run ... wake_word_phrase=Okay Nabu`. Bug reali risolti (v. KNOWLEDGE_BASE §6): patch **faster-whisper/PyAV 19** (`metadata_errors`), `wyoming` mancante nel venv HA (risposta vuota), lingua TTS esatta `it_IT`, `assist_pipeline/run` = subscription WS, raggiungimento impostazioni native Assist, caveat **`am force-stop`** (resetta l'assistente predefinito + spegne la wake word). Pulizia device: 425 app rimosse (217 GB liberi). Tutto il materiale in **`voice_satellite/`** + **ADR-020**; follow-up in **T-034…T-037** (comandi robot via MQTT, LLM cloud, hardening/autostart, opzioni wake word). *(Nota: il satellite è un accessorio esterno, non un nodo — ADR-019 resta valido.)*
- v0.3.0: testing — **in corso** (T-003 ✅; T-004…T-006 da fare).
- Firmware nodi 3–7, OTA client ESP32, CAD/elettronica: non iniziati (v0.4.0+).

Stato dettagliato: `PROJECT_STATUS.md`. Prossime attività: `docs/NEXT_TASK.md`.

---

## 9. Obiettivi Futuri

Roadmap completa in `ROADMAP.md`; idee in `future/future.md`: riconoscimento facciale, inseguimento persone, braccia 7 DoF, LIDAR, SLAM, manipolazione oggetti, docking automatico, ricarica autonoma. Post-MVP (GOALS §Obiettivi Futuri): fleet management, marketplace plugin, WebRTC teleop, certificazioni ISO 13482/CE.

---

## 10. Rischi Noti e Debito Tecnico

| Area | Debito/Rischio | Mitigazione prevista |
|------|----------------|---------------------|
| Testing | ✅ T-003 fatto 2026-09-22 (100% coverage `core.domain`); aggiornato 2026-10-09 (ADR-019): **197 test unit totali** (141 domain + 11 balance + 9 config-sync + 9 stepper parity + 27 motori/mock T-025); `check_docs.sh` OK; host firmware **53 check**. Restano integration/simulation | v0.3.0: T-004 (REST/WS), T-005 (event bus), T-006 (simulation parity) — saltati su richiesta 2026-09-23 |
| CI | Pipeline attiva (ruff, pytest+coverage ≥90%, doc-check, docker build, **firmware-host-tests + firmware-node7-build**); mancano mypy, clang-tidy, job firmware node2 | T-002 completamento + T-007 (ancora bloccato da T-014 per node2; node7 indipendente) |
| Duplicazione `DomainEvent` | 3 copie indipendenti: `src/core/domain/events.py`, `src/eventbus/event_bus.py`, `firmware/.../robot_core/eventbus.py` — serializzazione divergente (il bug to_dict/from_dict era in tutte e 3) | T-028: unificare sul dominio `core.domain` |
| Plugin framework `src/plugins/` | ✅ Riparato 2026-08-25: contratti unici in `base.py`, package importabile, lifecycle verificato end-to-end | — |
| Formatter | `ruff format` non adottato (36 file da riformattare) | T-016 |
| SDK | Buses reali non cablati (`TODO` in `src/sdk/robot.py`) | Integrazione con command bus esistente |
| Gateway | Auto-reconnect MQTT assente | Resilienza rete (GOALS T5) |
| Event Bus | NATS non implementato (`NotImplementedError`) | Alternativa futura, non bloccante |
| Config | set() runtime non persistito su file/DB | Hot-reload completo |
| Firmware | ✅ Node 7 completo 2026-09-23 (`node7_balance/` + `firmware/common/`, **build locale verde** con VSCode+PlatformIO via `platformio.ini`, IDF 5.5 — `pio run` SUCCESS 137,9 s; CI `firmware-node7-build` su IDF 5.2.2 **verde alla prima run** — CI #21, 2026-09-27, tutti e 6 i job green); **Node 6 bring-up motori su ESP32-S3** consegnato 2026-10-09 (`node6_tracks/`, env `node6`); Node 2 resta NON compilabile (T-014 → T-007): `firmware/node2_head/src/main.cpp` include `head_controller.hpp` **assente** (nessuna dir `include/`) — non solo `CMakeLists`; OTA client parziale | T-014 poi ROADMAP v0.4.0 |
| Sim/PID Python (Node 7) | ✅ **T-029 fatto 2026-10-07**: `trapezoid_velocity` ora a 5 argomenti con stato `v_now` nel chiamante (mirror di `slew`/`brake_bound`/`position_velocity_target`), PID Python con guardia `first_` + clamp ±1600; parità coperta da `tests/unit/test_stepper_parity.py` (9 test) | — |
| Driver A4988 Python (`set_position_steps`) | **T-030 (preesistente, scoperto durante T-029)**: loop `while abs(target - pos) > 0` su float → non termina mai; il C++ usa la soglia `position_snap_steps` (`a4988_driver.cpp:112`). Mock al sicuro; il demo `balance_bench.py` resterebbe appeso | T-030: soglia/snap come nel C++ (0.5g) |
| Driver A4988 Python (path default) | **T-031 (preesistente, scoperto durante T-025 Fase 1)**: `a4988.load_driver` (`src/hardware/drivers/a4988.py:157`) risolve il default con `parents[2]` invece di `parents[3]` → senza `--config` il demo `balance_bench.py` punta a un file inesistente (a differenza di `l298n.py`, già corretto) | T-031: una riga (0.25h) |
| Port motori C++ | **T-032 (Parziale, 2026-10-09)**: `motor_driver.hpp` + `motor_logic.hpp` + `L298NDriver` (`firmware/common/`) e 17 check host consegnati; **manca** il modulo di parità Python↔C++ dedicato (stile `test_stepper_parity.py`) | T-032: completare la parità, legata a T-022 (firmware Node 6) |
| Certificati | node7 aggiunto al `generate.sh` 2026-09-23 (prima solo node1..node6) | Rinnovo automatico: ROADMAP v0.4.0 (T-021) |
| Driver Nodo 6 Python | **ADR-019 (2026-10-09): `L298NDriver` host `src/hardware/drivers/l298n.py` RITIRATO** (il Pi è solo cervello). Resta il port puro `IMotorDriver` (`src/hardware/hal/motor.py`) + `MockMotorDriver` come astrazione/Digital Twin e contratto di parità Python↔C++; la produzione è il firmware ESP32-S3 Node 6 (T-022/T-032) | Solo riferimento/parità; produzione = firmware ESP32-S3 |
| Driver Nodo 7 Python | Stessa regola: `A4988StepperDriver`/`MockStepperDriver` = prototipo da banco/simulatore (documentano `IStepperDriver`); produzione = firmware ESP32 Node 7 (**T-026 ✅ 2026-09-23**). Il loop PID di livello gira sul nodo, non sul Pi | Solo riferimento prototipale; produzione = firmware ESP32 (bench di validazione = prossimo step) |
| Satellite vocale (Note 10) | **ADR-020, operativo 2026-10-13**: punto singolo di guasto; batteria/salute ≈79% → serve caricatore a muro ≥5V/2A; wake word solo in inglese ("Okay Nabu"); patch manuale faster-whisper/PyAV 19; `am force-stop` dell'app Companion resetta l'assistente predefinito e spegne la wake word; container proot da irrobustire (autostart/watchdog/backup) | T-036 (hardening: Termux:Boot, watchdog, IP statico, backup `voice_satellite/`); T-035 (LLM cloud); T-037 (opzioni wake word/lingua) |

---

## 11. Satellite Vocale (accessorio esterno, ADR-020)

**Cos'è.** Un Samsung Galaxy Note 10 (schermo rotto, headless via ADB/SSH/scrcpy) usato come **terminale vocale** di OpenJ5. **Non è un nodo** (ADR-019): parla col robot via Node 1 → MQTT/REST. Realizza in concreto il `SpeechAPI` previsto dall'SDK (ADR-006/ADR-007).

**Stack.** Termux + `proot-distro` (container OCI `python:3.14-slim`, Debian 13, Python 3.14.8). Dentro il container:
- **Home Assistant Core 2026.10.1** (`/opt/ha`, venv con `wyoming`).
- **wyoming-faster-whisper** — STT `small`, `it` (TCP 10300). *Richiede patch PyAV 19.*
- **wyoming-piper** — TTS `it_IT-serena-medium` (TCP 10200).

**Front-end.** App ufficiale **Home Assistant Companion 2026.8.4** impostata come **assistente Android predefinito**, con **wake word on-device "Okay Nabu"** (microWakeWord, nessun audio inviato fuori per il rilevamento). Pipeline **"Assistente Locale"** (`01m4tje8tnx44erdd0v45fqtm1`, `tts_language: it_IT`).

**Flusso.** wake word (on-device) → `assist_pipeline/run` → STT (Whisper) → intent → TTS (Piper) → speaker. In futuro: intent → **MQTT `openj5/v1/...`** → Node 1 → nodi (T-034).

**Stato.** ✅ End-to-end verificato (foreground e background), 2026-10-13.

**Materiale.** `voice_satellite/` (README, architettura, report device, script HA/Wyoming, asset audio, APK). Dettagli di setup e problemi risolti: `voice_satellite/docs/voice_assistant_architecture.md` (Fasi 0–5) e `docs/KNOWLEDGE_BASE.md` §6. Decisione: `docs/adr/ADR-020-note10-voice-satellite.md`.

**Debito/limiti.** Wake word solo in inglese; batteria/calore (serve caricatore adeguato); punto singolo di guasto; hardening (autostart/watchdog/backup) e LLM cloud ancora da fare (T-035/T-036/T-037).

