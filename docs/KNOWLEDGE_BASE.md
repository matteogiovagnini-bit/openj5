# KNOWLEDGE_BASE — Base di Conoscenza OpenJ5

> Problemi risolti, procedure, best practice, errori da evitare. Alimentare a ogni sessione.
> Ultimo aggiornamento: 2026-09-21

---

## 1. Problemi Risolti (sessione stabilizzazione Docker, 2026-08-13)

Lezioni dal debug dello stack `docker-compose` (10 servizi) su host Linux:

### Mosquitto
| Problema | Soluzione |
|----------|-----------|
| Healthcheck falliva: `$SYS/broker/version` non popolato se nessun client pubblica statistiche | Pubblicare periodicamente topic `$SYS/...` (o usare sottoscrizione al broker con `-W 5`) e healthcheck su `mosquitto_sub -t '$SYS/broker/version' -C 1` |
| Opzione inesistente `websockets_heartbeat_interval` faceva crashare il config | Rimuoverla: non esiste in Mosquitto 2.0 |
| `max_packet_size` vs nomi alternativi | Usare il nome opzione corretto della versione 2.0 (`max_packet_size`, non `message_size_limit` per listener) |
| `password_file` puntato ma file mancante → broker non parte | Generare i segreti sull'host PRIMA dell'up, oppure commentare l'autenticazione finché non serve |
| Chiavi TLS non leggibili dal container | Allineare uid/gid del container all'ownership dei certificati bind-mounted (`user: "1883:1000"`, permessi 640 sul gruppo host `openj5`) |

### Loki / OTEL Collector / Porte
| Problema | Soluzione |
|----------|-----------|
| Loki crasha scrivendo fuori dal volume | `common.path_prefix` deve stare sotto il path del volume writable dichiarato; dichiarare `VOLUME` per la dir log |
| Exporter `opentelemetry-exporter-prometheus` deprecato nel collector | Esportare metriche via endpoint HTTP interno del collector (porta 8888), senza dipendenza Python deprecata |
| Conflitto porta host 8888 (collector exporter) | Non mapparla sull'host o spostare il binding |
| Conflitto porta host 9090 (rosbridge) | Rimuovere il mapping host se il bridge è solo interno |

### Docker Compose generale
- Il campo top-level `version:` è obsoleto: rimuoverlo.
- Password DB via secret file (`POSTGRES_PASSWORD_FILE` + `.env` per `DB_PASSWORD`), mai inline nel compose.
- Build context corretto per robot-core; le dipendenze ROS **non** servono nell'immagine Python (il bridge ROS è un container separato).
- Gazebo: usare l'immagine OCI ufficiale con supporto arm64 invece di build custom.

---

## 1-bis. Problemi Risolti (primo deployment reale su RPi4, 2026-08-26)

Primo boot storico del Robot Core su hardware fisso (T-018). Sezione alimentata dalle lezioni del giorno:

| Problema | Causa reale | Soluzione |
|----------|-------------|-----------|
| Container mosquitto unhealthy: healthcheck timeout su `$SYS/broker/version` | **La sezione `user anonymous` nell'ACL NON viene applicata ai client senza username**: anonimo = zero permessi (deny-by-default), nessuna consegna messaggi nemmeno su topic normali | Regole globali PRIMA di qualsiasi blocco `user` nel file ACL (`topic read $SYS/broker/version` + topic healthcheck) |
| Healthcheck `$SYS` fragile tra build mosquitto | `$SYS` non pubblicato da tutte le build/configurazioni | Healthcheck deterministico: `mosquitto_pub retained` + `mosquitto_sub` readback su `openj5/healthcheck/probe` |
| robot-core: mount volume `/var/log/openj5` → "read-only file system" al create | Docker moderno (containerd image store): `VOLUME` dichiarato nel Dockerfile + volume nominato compose sullo stesso path = conflitto | Rimuovere `VOLUME` dal Dockerfile; la persistenza la gestisce solo compose |
| Dopo rebuild il container vecchio continua a crashare | Compose non ricrea se cambia solo l'immagine sotto lo stesso tag | `docker compose up -d --force-recreate <servizio>` dopo un rebuild |
| `ModuleNotFoundError: No module named 'robot_core'` | Codice copiato in `/app/src/`, entrypoint `python -m robot_core.__main__` gira da `/app` senza PYTHONPATH | `ENV PYTHONPATH=/app/src` nel Dockerfile |
| `ImportError: cannot import name 'EventBus'` | Sette moduli usano il nome `EventBus`; il modulo definisce `IEventBus` | Alias `EventBus = IEventBus` in `eventbus.py` |
| `publish() takes 2 positional arguments but 3 were given` (metriche) | Chiamata `(topic, payload)` invece di `DomainEvent` | Pubblicare `DomainEvent(event_type=..., source_node=..., payload=...)` |
| Limiti memoria compose "non applicati" (falso allarme) | `free` dentro il container mostra SEMPRE la RAM host (`/proc/meminfo` non virtualizzato senza lxcfs); i parametri `cgroup_enable/disable=memory` sono knob cgroup **v1**, ignorati in v2 | Verificare con `docker stats` (LIMIT colonna) o OOM test: `docker run --rm --memory=256m alpine sh -c "tail /dev/zero"` → exit 137 |
| Container con mount annidati: "mkdirat ... read-only file system" sul mountpoint del volume | Una bind **read-only** del parent (`/var/log:/var/log:ro`) copre il path prima della creazione del mountpoint del volume annidato; se la dir non esiste sull'host → EROFS | Non montare in RO un parent di un volume annidato, oppure pre-creare la dir sull'host (`sudo mkdir -p /var/log/openj5`) |
| Bootstrap falliva su checkout rsync senza `.git` | Script tentava `git clone` in directory esistente | Gestione branch: clone solo se dir assente |
| Pi OS corrente è Debian 13 (Trixie), non Bookworm | L'Imager distribuisce già Trixie (kernel 6.18) | Procedure accettano 12|13; ADR-016 aggiornato |

---

## 1-ter. Problemi Risolti (banco Nodo 6 — motori, 2026-08-26)

Lezioni dal bring-up prototipale L298N + 2 motoriduttori DC 12V + LiPo 3S:

### Alimentazione e potenza (lezione principale)
| Problema | Causa reale | Soluzione |
|----------|-------------|-----------|
| Regolatore 5V di bordo del L298N rischia di bruciarsi | Con tensione motori >12V (es. LiPo 3S pieno a 12,6V) il 78M05 a bordo abbatterebbe troppa tensione | **Rimuovere il jumper del regolatore 5V** e alimentare la logica del modulo dall'uscita 5V del Pi (pin 4). Con 12V fissi il jumper si può lasciare messo e NON serve il filo dal Pi |
| Il Pi si riavvia/instabilizza quando parte il motore | Alimentazione di potenza presa dal 5V del Pi, o massa non comune | Potenza SEMPRE da fonte esterna (LiPo 3S/alim. 12V), masse GND comuni (batteria ↔ modulo ↔ Pi pin 6) |
| Velocità a macchinetta, ignora il PWM | Jumper ENA/ENB ancora montati: tengono l'abilitazione sempre HIGH | **Rimuovere i jumper ENA ed ENB** e pilotare i pin ENA/ENB via GPIO PWM |

### Software e cablaggio GPIO
| Problema | Causa reale | Soluzione |
|----------|-------------|-----------|
| Driver servono GPIO PWM hardware | PWM software su Pi è inaffidabile per DC che richiedono 1kHz~ | Usare GPIO18 (PWM0) e GPIO13 (PWM1) per ENA/ENB |
| GPIO14/15 non usabili per il cablaggio | Occupati dalla console seriale UART | Tenerli liberi nei mapping (config `tracks.json`) |
| Il driver deve girare su HOST, non in container | I container Docker non hanno accesso ai GPIO del Pi | Script demo eseguito sulla shell del Pi (`python3 scripts/demo/tracks_bench.py`), non dentro `docker compose exec` |
| Abilitare I²C/GPIO solo con `gpiozero`+`lgpio` | Pi OS Lite Trixie non ha python3-gpiozero preinstallato | `sudo apt install python3-gpiozero python3-libgpiod` |

### Regole da banco (safety-first)
- **Ruote sempre sollevate da terra** al primo test (niente fughe).
- **Batteria collegata PER ULTIMA**, tutto già cablato.
- Fusibile inline (5A) sul + batteria consigliato.
- Un motore che gira al contrario: inverti i DUE fili su OUT1/OUT2 (o OUT3/OUT4).
- Fine sessione: `q` nel demo (brake), stacca la batteria, `sudo poweroff`, attendi che il LED ACT smetta di lampeggiare, poi stacca la USB-C.
- LiPo: se resta fermo a lungo, riportarlo a tensione di storage (~11,4V) col caricabatterie.

### Cambio PC di sviluppo (migrazione)
| Problema | Causa reale | Soluzione |
|----------|-------------|-----------|
| Tutta la conoscenza vive in queste docs, non nelle chat | Le info acquisite sono state riversate in PROJECT_MEMORY, KNOWLEDGE_BASE, NEXT_TASK, SESSION_REPORT, CONTINUATION_PROMPT, CHANGELOG | Sul nuovo PC: `git clone` del repo; l'intero stato è nel repo. `.env`, `secrets/*` e `certs/*` sono gitignored e NON si trasferiscono col clone: vanno rigenerati sul dispositivo con `./secrets/generate.sh` + `certs/generate.sh` |

---

## 2. Procedure

### Rigenerare certificati mTLS
```bash
cd firmware/node1_robot_core/docker/certs
./generate.sh   # CA privata + certificati broker e nodi
```
Verificare permessi: chiavi private 640 gruppo `openj5`; container mosquitto avviato con `user: "1883:1000"`.

### Avviare lo stack completo
```bash
cd firmware/node1_robot_core/docker
echo "DB_PASSWORD=<password>" > .env   # gitignored: mai committare il .env reale
./secrets/generate.sh                  # genera i secret in docker/secrets/
cd certs && ./generate.sh              # genera CA e certificati (vedi sopra)
docker compose up -d
curl http://localhost:8080/health
```

Nota: `.env`, `secrets/*.txt|pem` e `certs/*.crt|key` sono gitignore — vanno generati su ogni installazione.

### Aggiungere un ADR
1. Copiare `docs/adr/TEMPLATE.md` → `ADR-XXX-title-slug.md` (numero sequenziale).
2. Compilare tutte le sezioni (Status, Context, Decision, Alternatives, Consequences, Implementation Notes, Related ADRs).
3. Aggiornare `docs/adr/INDEX.md`.
4. Mai modificare ADR esistenti: si supersede con nuovo ADR.

### Chiusura di una sessione (obbligatoria)
Aggiornare: `docs/SESSION_REPORT.md`, `docs/NEXT_TASK.md`, `docs/PROJECT_MEMORY.md`, `CHANGELOG.md`, `PROJECT_STATUS.md`, rigenerare `docs/CONTINUATION_PROMPT.md`.

---

## 1-quater. Problemi Risolti (design Node 7 Balance, 2026-09-21)

| Problema | Causa reale | Soluzione |
|----------|-------------|-----------|
| Test di livello non convergono e poi **hang infinito** nel mock | Il mock integrava sia "velocity comandata" sia la rampa trapezoidale verso il target: nella zona di decelerazione il branch conservativo ricalcolava v con vmax=|v_prev| → non decelera mai e la posizione diverge | Separazione della semantica: `set_velocity_steps_s()` + `step(dt)` integrano la velocità comandata (il chiamante possiede il profilo); `set_position_steps()` rampa internamente con `trapezoid_velocity` fino al raggiungimento |
| `trapezoid_velocity` non testabile nei test | Risiedeva in `a4988.py` che importa gpiozero al top-level → i test CI senza GPIO fallivano al collection | Helper **puro** spostato nell'HAL (`src/hardware/hal/stepper.py`); il driver A4988 e il mock lo importano da lì. Regola: logica di moto ≠ I/O |
| Lag di tracking nel loop di livellamento (4,3° su rampa 2°/s) | La velocity è comandata in **steps/s** e proporzionale all'errore con kp piccolo: servono ~71 step/s per 2°/s, quindi l'errore di regime = 71/kp | Guadagni validati in simulazione (kp=120 per la rampa di test); in config node7 il PID parte da kp=15, ki=1, kd=0.3 da ritarare al primo banco con IMU |
| ASCII/step math: 200 step/giro × 16 µstep × 4 (20T→80T) = **12800 jsteps/giro = 35,556 jsteps/°** | Convenzioni tra motore/microstepping/riduttore confuse nei commenti | Formula centralizzata nel value object `StepperConfig.steps_per_joint_rev`/`steps_per_deg` + test dedicato; stesso calcolo in `config/node7_balance/node.json` e demo bench |

---

## 3. Best Practice

- **Prima di implementare**: cercare un componente riutilizzabile esistente (HAL? gateway adapter? value object?) — v. MASTER_PROMPT.
- **Test senza hardware**: usare `InMemoryEventBus` e driver mock; Redis reale solo negli integration test con Testcontainers.
- **Comandi logici sempre**: mai angoli servo nei payload MQTT dal lato RPi; la traiettoria vive sul nodo ESP32.
- **Correlation ID**: propagarlo da SDK → gateway → evento per ricostruire catene comando→effetto.
- **Config prima del codice**: aggiungere la chiave JSON + schema prima di leggere il valore nel codice.
- **Firmware comune**: ogni funzionalità duplicabile tra nodi va in `firmware/common/`, mai copy-paste tra progetti nodo.

---

## 4. Errori da Evitare

- ❌ Modificare un ADR esistente (immutabile per costituzione).
- ❌ Hardcodare valori "solo per ora" (v. NON_GOALS §8).
- ❌ Import MQTT/ROS nel codice applicativo (solo `ICommunicationGateway`).
- ❌ Dichiarare completezza senza test/doc: la funzionalità resta "incomplete".
- ❌ Aggiornare CHANGELOG con funzionalità non ancora esistenti nel repo (errore commesso in v0.3.0 Unreleased — da correggere, v. NEXT_TASK T-001).
- ❌ Commit non atomici che mischiano feature + infrastruttura + doc.
- ❌ Avviare lo stack docker senza aver generato prima segreti e certificati.

---

## 5. FAQ

**D: Come cambio protocollo di comunicazione?**
R: Una riga nella config del gateway (`GatewayFactory`). Zero cambi nel codice (ADR-003).

**D: Come passo dal robot reale alla simulazione?**
R: `"mode": "sim"` nella RobotConfig. Stesso SDK, stessi test (ADR-010).

**D: Dove metto un nuovo sensore?**
R: Interfaccia HAL se manca (es. `ILidarDriver`), driver adapter, selezione via `config/common/hal.json`. Mai tocco diretto I2C/SPI nel codice applicativo.

**D: Posso usare ROS 2?**
R: Sì come transport opzionale tramite bridge/gateway plugin. NON come event bus né come architettura (NON_GOALS §2).

**D: Perché il mio commit non è "completo"?**
R: Manca uno step del Definition of Done (CODING_STANDARD §8): test, doc, changelog, project status, memoria.
