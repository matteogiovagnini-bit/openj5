# CONTINUATION_PROMPT — Prompt di Continuità OpenJ5

> Rigenerare a fine di OGNI sessione. Questo prompt permette a qualsiasi IA (OpenCode, ChatGPT, Claude, Gemini, Codex…) di riprendere il progetto immediatamente senza perdere contesto.
> Generato: 2026-10-07 · Versione progetto: v0.2.0+ (Robot Core OPERATIVO su hardware) · v0.3.0 in corso: **T-003 test core + T-026 firmware Node 7 Balance (2026-09-23) + T-029 parità Python↔firmware Node 7 (2026-10-07, 170 test, 100% coverage)** · prototipo Nodo 6 · design+firmware Node 7 (ADR-017)

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
10. docs/hardware/BENCH_BALANCE.md     (guida banco Nodo 7: cablaggio NEMA17/MPU6050)
11. firmware/node7_balance/README.md   (build/comandi/fail-safe firmware Node 7)

CONTESTO ESSENZIALE:
- Architettura: esagonale + DDD + event-driven + plugin; 7 nodi distribuiti.
  Nodo 1 = Raspberry Pi 4 8GB (Robot Core Python/FastAPI, broker Mosquitto,
  Redis Streams, PostgreSQL, Gazebo headless, stack Prometheus/Grafana/Loki/OTEL).
  Nodi 2–6 = ESP32-S3/ESP32 (ESP-IDF C++20): head, braccio dx/sx, torso, cingoli.
  Nodo 7 = ESP32-S3: **Balance Controller** (NEMA17+A4988+MPU6050, corpo livellato
  vs gravità sui cingoli — ADR-017; design + FIRMWARE consegnati, bench pending).
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
  build, **firmware-host-tests + firmware-node7-build**). **T-003 FATTO
  2026-09-22**: `tests/unit/` = **170 test** (dal 2026-10-07), 100% coverage
  `src/core/domain/`; 5 bug latenti corretti — SESSION_REPORT 2026-09-22 e
  KNOWLEDGE_BASE §1-quinquies.
- **T-026 FATTO 2026-09-23**: firmware Node 7 consegnato — schema di cablaggio
  `docs/hardware/BENCH_BALANCE.md`, logica pura in `firmware/common/` (rampa
  A4988, Madgwick, FSM ADR-009, PID parità sim → **36 check host** via
  `scripts/test/host_firmware.sh`), progetto ESP-IDF `firmware/node7_balance/`
  (task 100 Hz + IMU 200 Hz, comandi logici level/tilt/stow/stop su
  `openj5/v1/balance/cmd`, fail-safe deadman/watchdog/limite ±1244 jsteps,
  bobine off al boot, mTLS opzionale), test parità config (8 test → **156
  totali**), fix latenti (limiti ±4445→±1244 = erano ±125°, ACL mosquitto su
  topic v1 + user node7, cert node7, README firmware fantasma). Debito emerso:
  **T-029, chiuso il 2026-10-07** (nuovo debito residuo: **T-030**). Prima
  build CI del firmware verificata verde (CI #21, 2026-09-27).
- **Nota: working tree contiene modifiche NON committate** (T-029 + doc) —
  commitare/pushare solo su richiesta esplicita.
- PROTOTIPO NODO 6 avviato: primo driver HAL reale `src/hardware/drivers/l298n.py`
  + demo `scripts/demo/tracks_bench.py` + `config/bench/tracks.json` + guida
  cablaggio `docs/hardware/BENCH_TRACKS.md`. Il primo movimento fisico dei motori
  (T-025) è il prossimo step sul banco.
- **NODO 7 BALANCE (ADR-017) — design E FIRMWARE consegnati**: Node 7 (ESP32-S3
  dedicato) per il livellamento attivo del corpo vs gravità: NEMA17+A4988
  (STEP/DIR/ENABLE GPIO4/5/6), riduzione cinghia 20T→80T (±35° = ±1244 jsteps),
  IMU MPU6050 sul corpo (I2C GPIO8/9, 0x68), PID 100 Hz **sul nodo**, comandi
  SOLO logici (level/tilt/stow/stop). Consegnato: software Python (HAL, driver
  bench, simulatore, config, BodyAPI, 8 test) + **firmware ESP-IDF completo
  (T-026 ✅)** con guida cablaggio `docs/hardware/BENCH_BALANCE.md`, host tests
  e build CI. CAD meccanico (T-027): follow-up. Resta il banco reale (primi
  impulsi, Vref, ratifica PID).

DEBITO NOTO (vedi docs/PROJECT_MEMORY.md §10):
- Unit test core domain OK (T-003); mancano integration test T-004 (REST/WS),
  T-005 (event bus + state machine), T-006 (simulation parity) per chiudere v0.3.0
  — T-004/T-005 **saltati su richiesta** 2026-09-23.
- ~~**T-029**~~ **CHIUSO 2026-10-07**: `trapezoid_velocity` ora è a 5
  argomenti con stato `v_now` nel chiamante (mirror di `slew`/`brake_bound`/
  `position_velocity_target`), PID Python con guardia `first_` + clamp ±1600;
  9 test di parità in `tests/unit/test_stepper_parity.py`.
- **T-030 (nuovo, preesistente)**: `A4988StepperDriver.set_position_steps`
  (`src/hardware/drivers/a4988.py:120`) confronta float con
  `while abs(target - pos) > 0` e **non termina mai** (il C++ usa la soglia
  `position_snap_steps`) — da correggere prima del bench `balance_bench.py`.
- **T-028**: 3 copie duplicate di `DomainEvent` (core/domain, eventbus host,
  bundle robot_core) con serializzazione divergente.
- Formatter ruff non adottato (T-016); buses SDK non cablati (T-010);
  auto-reconnect MqttGateway (T-011); persistenza config runtime (T-012).
- CI senza mypy/clang-tidy (T-002 residuo); job firmware attivi ma la prima
  build reale di `firmware-node7-build` è da verificare; T-007 (node2) bloccato
  da T-014 — il modello CI è già pronto.
- Grafana ancora con password admin default.
- Driver L298N/A4988 Python = prototipi banco, NON produzione (produzione =
  firmware ESP32; Node 7 ora esiste, bench reale pending).
- PID livellamento (kp=15, ki=1, kd=0.3) e Vref 550 mA validati solo in
  simulazione: ratificare al primo banco con IMU (T-026 bench).

PROSSIME ATTIVITÀ (in ordine, dettagli in docs/NEXT_TASK.md):
1. **Verificare la prima run CI** di `firmware-node7-build` su GitHub Actions
   e correggere eventuali rossi (campi esp-mqtt, i2c legacy IDF 5.2, EMBED).
2. Commit/push di T-026 **solo se richiesto** (working tree attualmente sporco).
3. T-004 integration test REST/WS o T-005 event bus + state machine
   (sbloccati da T-003; saltati su richiesta 2026-09-23) → chiudere v0.3.0 con T-006.
4. T-025: primo movimento fisico dei motori (saltato su richiesta 2026-09-23) —
   per il Node 7 il primo bench (`BENCH_BALANCE.md`) segue lo stesso momento.
5. T-030: loop infinito di `set_position_steps` (A4988 Python, preesistente).
6. T-028: deduplicare le 3 `DomainEvent`.
7. Verifica containers secondari ros2-bridge/gazebo + cambio password Grafana.
8. T-014 firmware Node 2/3 compilabili (sblocca T-007) → T-027 CAD giunto
   body pitch (guidati da ADR-017).

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

INIZIA da: verificare `git log` che lo stato collimi con queste docs (working
tree = T-029 non committato), controllare la run CI `firmware-node7-build`,
poi proporre: commit/push di T-029 su richiesta, oppure T-004/T-005
(integration test per v0.3.0) o T-030 (loop A4988) secondo priorità.
```

---

## Istruzioni per il manutentore

1. Alla fine di ogni sessione: aggiorna questo file sostituendo le sezioni "Stato attuale", "Debito noto" e "Prossime attività", e cambia la data in cima.
2. Il prompt è autocontenuto: può essere incollato anche in un'IA che non ha accesso al filesystem, ma funziona meglio se l'IA legge prima i file indicati.
3. Se un'informazione contraddice i documenti citati, vincono **sempre** i documenti del repo (questo prompt è una vista, non la fonte).