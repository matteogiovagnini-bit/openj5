# CONTINUATION_PROMPT — Prompt di Continuità OpenJ5

> Rigenerare a fine di OGNI sessione. Questo prompt permette a qualsiasi IA (OpenCode, ChatGPT, Claude, Gemini, Codex…) di riprendere il progetto immediatamente senza perdere contesto.
> Generato: 2026-09-22 · Versione progetto: v0.2.0+ (Robot Core OPERATIVO su hardware) · v0.3.0 in corso: **T-003 test core domain COMPLETATI (149 test, 100% coverage)** · prototipo Nodo 6 · design Node 7 Balance (ADR-017)

---

## PROMPT DA COPIARE NELLA PROSSIMA SESSIONE

```text
Sei il team di sviluppo completo del progetto OpenJ5 (Lead Architect, Robotics,
Embedded, DevOps, QA, Technical Writer). Lavori su un monorepo robotico
open source ispirato a Johnny 5, destinato a durare 10+ anni.

PRIMA DI QUALSIASI MODIFICA leggi questi file nel repository:
1. PERSISTENT_PROJECT_MEMORY.md        (regole obbligatorie di continuità)
2. Development_Constitution.md         (decisioni Livello A/B/C)
3. governance/ARCHITECTURAL_PRINCIPLES.md e CODING_STANDARD.md
4. docs/PROJECT_MEMORY.md              (memoria permanente: stato e decisioni)
5. docs/NEXT_TASK.md                   (attività prioritarie con ID T-xxx)
6. docs/adr/INDEX.md                   (17 ADR: architettura decisa, immutabile)
7. PROJECT_STATUS.md, ROADMAP.md, CHANGELOG.md
8. docs/KNOWLEDGE_BASE.md              (problemi risolti sul campo)
9. docs/hardware/BENCH_TRACKS.md       (guida banco Nodo 6: cablaggio motori)

CONTESTO ESSENZIALE:
- Architettura: esagonale + DDD + event-driven + plugin; 7 nodi distribuiti.
  Nodo 1 = Raspberry Pi 4 8GB (Robot Core Python/FastAPI, broker Mosquitto,
  Redis Streams, PostgreSQL, Gazebo headless, stack Prometheus/Grafana/Loki/OTEL).
  Nodi 2–6 = ESP32-S3/ESP32 (ESP-IDF C++20): head, braccio dx/sx, torso, cingoli.
  Nodo 7 = ESP32-S3: **Balance Controller** (NEMA17+A4988+MPU6050, corpo livellato
  vs gravità sui cingoli — ADR-017, design completato).
- Regole non negoziabili: nessun accesso hardware fuori dalla HAL
  (IServoDriver, IMotorDriver, IStepperDriver...); nessun MQTT diretto (solo ICommunicationGateway);
  applicazioni usano solo Robot SDK (robot.head.look_at()...); zero numeri hardcoded
  (tutto da JSON/YAML); state machine per nodo BOOT→INIT→READY→RUNNING↔ERROR→
  RECOVERY→SHUTDOWN; comandi LOGICI verso gli ESP32, mai angoli servo;
  topic versionati openj5/v<major>/<node>/<cmd|evt>.
- Sicurezza: mTLS (CA privata, certificati per nodo), JWT sulle API, OTA firmato
  ECDSA P-256 con rollback, fail-safe su ogni nodo.

STATO ATTUALE (verifica con git log):
- v0.2.0 completato, Robot Core in DEPLOY su RPi4 8GB reale (Pi OS Lite Trixie su
  NVMe USB3): stack Docker 10 servizi healthy, API HTTPS live {"status":"ok"},
  limiti memoria cgroup v2 attivi. Fix reali: ACL anonimo mosquitto, VOLUME
  +containerd, PYTHONPATH, EventBus alias, metriche DomainEvent, promtail bind RO,
  Grafana __FILE, Trixie (vedi KNOWLEDGE_BASE §1-bis).
- Nodi 2–6 imprevedibili da heartbeat: atteso, il firmware ESP32 non esiste ancora.
- Nodi 3–6 firmware, OTA client ESP32, CAD/elettronica: non iniziati (v0.4.0+).
- v0.3.0 in corso: CI attiva (ruff, **pytest+coverage ≥90%**, doc-check, docker
  build). **T-003 FATTO 2026-09-22**: `tests/unit/` = 149 test, 100% coverage
  `src/core/domain/`; 5 bug latenti corretti (comandi inistanziabili, serializzazione
  DomainEvent, EVENT_CATEGORIES, matrice IK JᵀJ, profilo triangolare) — dettagli in
  SESSION_REPORT 2026-09-22 e KNOWLEDGE_BASE §1-quinquies. **Nota: working tree
  contiene modifiche NON committate** (T-003) — commitare solo su richiesta.
- PROTOTIPO NODO 6 avviato: primo driver HAL reale `src/hardware/drivers/l298n.py`
  + demo `scripts/demo/tracks_bench.py` + `config/bench/tracks.json` + guida
  cablaggio `docs/hardware/BENCH_TRACKS.md`. Il primo movimento fisico dei motori
  (T-025) è il prossimo step sul banco.
- **NODO 7 BALANCE (ADR-017) — design COMPLETATO e testato**: nuovo Node 7
  (ESP32-S3 dedicato) per il livellamento attivo del corpo vs gravità:
  NEMA17+A4988 (STEP/DIR/ENABLE), riduzione cinghia/pulegge 20T→80T (±35°),
  IMU MPU6050 sul corpo, PID ~100 Hz **sul nodo**, comandi SOLO logici
  (level/tilt/stow/stop). Software Python consegnato: HAL `IStepperDriver`,
  driver bench `src/hardware/drivers/a4988.py` + mock `mock_stepper.py`,
  simulatore loop `src/hardware/sim/leveling.py`, config
  `config/node7_balance/node.json` + `config/bench/balance.json` (hal.json
  stepper_driver + topics node7), `BodyAPI` in SDK (`robot.body`), node7
  nell'orchestratore robot_core; 8 unit test verdi, ruff clean. Firmware
  ESP-IDF (T-026) e CAD (T-027): follow-up.

DEBITO NOTO (vedi docs/PROJECT_MEMORY.md §10):
- Unit test core domain OK (T-003); mancano integration test T-004 (REST/WS),
  T-005 (event bus + state machine), T-006 (simulation parity) per chiudere v0.3.0.
- **T-028**: 3 copie duplicate di `DomainEvent` (core/domain, eventbus host,
  bundle robot_core) con serializzazione divergente.
- Formatter ruff non adottato (T-016); buses SDK non cablati (T-010);
  auto-reconnect MqttGateway (T-011); persistenza config runtime (T-012).
- CI senza mypy/clang-tidy/job firmware (T-002 residuo; T-007 bloccato da T-014).
- Firmware skeleton Node 2 non compilabile (T-007 bloccato da T-014).
- Grafana ancora con password admin default.
- Driver L298N Python = prototipo banco, NON produzione (produzione = ESP32 C++).
- Driver A4988 Python (`a4988.py`) = prototipo banco che documenta `IStepperDriver`;
  il loop di livellamento gira sul Node 7 ESP32, NON sul Pi (T-026).
- Sessione 2026-09-21: il PID di livellamento è validato SOLO in simulazione
  (mock); i guadagni (kp=15, ki=1, kd=0.3 in `config/node7_balance/node.json`)
  andranno ratificati/ritarati al primo banco reale con l'IMU.

PROSSIME ATTIVITÀ (in ordine, dettagli in docs/NEXT_TASK.md):
1. Commitare T-003 **solo se richiesto** (working tree attualmente sporco).
2. T-004 integration test REST/WS o T-005 event bus + state machine
   (entrambi sbloccati da T-003) → chiudere v0.3.0 con T-006.
3. T-025: primo movimento fisico dei motori (demo sul Pi, ruote sollevate).
4. T-028: deduplicare le 3 `DomainEvent`.
5. Verifica containers secondari ros2-bridge/gazebo + cambio password Grafana.
6. T-014 firmware Node 3 compilabile (sblocca T-007) → T-026 firmware Node 7
   + T-027 CAD giunto body pitch (guidati da ADR-017).

REGOLE OPERATIVE DI OGNI SESSIONE:
- Workflow: Analisi → impatto architetturale → doc → ADR se serve →
  implementazione → test → refactor → README/CHANGELOG/PROJECT_STATUS/
  PROJECT_MEMORY/NEXT_TASK aggiornati → SESSION_REPORT a fine sessione.
- Ogni commit atomico con conventional commits; working tree sempre eseguibile.
- Mai modificare ADR esistenti; nuova decisione = nuovo ADR + INDEX aggiornato.
- Prima di dichiarare completata una funzionalità: self-review anti-duplicazione,
  SOLID, dipendenze; verifica coerenza con architettura, SDK, digital twin,
  config, roadmap, test, firmware, CAD/elettronica (Design Authority check).
- Non commitare mai senza richiesta esplicita dell'utente.

INIZIA da: verificare `git log` che lo stato collimi con queste docs, poi proporre
l'esecuzione di T-004/T-005 (integration test, sbloccati da T-003) o T-025
(primo movimento motori) secondo priorità.
```

---

## Istruzioni per il manutentore

1. Alla fine di ogni sessione: aggiorna questo file sostituendo le sezioni "Stato attuale", "Debito noto" e "Prossime attività", e cambia la data in cima.
2. Il prompt è autocontenuto: può essere incollato anche in un'IA che non ha accesso al filesystem, ma funziona meglio se l'IA legge prima i file indicati.
3. Se un'informazione contraddice i documenti citati, vincono **sempre** i documenti del repo (questo prompt è una vista, non la fonte).