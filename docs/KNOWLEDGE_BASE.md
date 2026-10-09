# KNOWLEDGE_BASE — Base di Conoscenza OpenJ5

> Problemi risolti, procedure, best practice, errori da evitare. Alimentare a ogni sessione.
> Ultimo aggiornamento: 2026-09-22

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
| Test di livello non convergono e poi **hang infinito** nel mock | Il mock integrava sia "velocity comandata" sia la rampa trapezoidale verso il target: nella zona di decelerazione il branch conservativo ricalcolava v con vmax=|v_prev| → non decelera mai e la posizione diverge | Separazione della semantica: `set_velocity_steps_s()` + `step(dt)` integrano la velocità comandata (il chiamante possiede il profilo); `set_position_steps()` rampa internamente con `trapezoid_velocity` fino al raggiungimento (dal 2026-10-07 con stato `v_now` nel chiamante, mirror del firmware — v. T-029) |
| `trapezoid_velocity` non testabile nei test | Risiedeva in `a4988.py` che importa gpiozero al top-level → i test CI senza GPIO fallivano al collection | Helper **puro** spostato nell'HAL (`src/hardware/hal/stepper.py`); il driver A4988 e il mock lo importano da lì. Regola: logica di moto ≠ I/O. La firma ora è a 5 argomenti `(v_now, steps_remaining, vmax, accel, dt)`, allineata al firmware da **T-029** (2026-10-07) |
| Lag di tracking nel loop di livellamento (4,3° su rampa 2°/s) | La velocity è comandata in **steps/s** e proporzionale all'errore con kp piccolo: servono ~71 step/s per 2°/s, quindi l'errore di regime = 71/kp | Guadagni validati in simulazione (kp=120 per la rampa di test); in config node7 il PID parte da kp=15, ki=1, kd=0.3 da ritarare al primo banco con IMU |
| ASCII/step math: 200 step/giro × 16 µstep × 4 (20T→80T) = **12800 jsteps/giro = 35,556 jsteps/°** | Convenzioni tra motore/microstepping/riduttore confuse nei commenti | Formula centralizzata nel value object `StepperConfig.steps_per_joint_rev`/`steps_per_deg` + test dedicato; stesso calcolo in `config/node7_balance/node.json` e demo bench |

---

## 1-quinquies. Problemi Risolti (T-003 unit test core domain, 2026-09-22)

Lezioni dalla creazione della prima vera suite pytest (`tests/unit/`, 149 test, 100% coverage `core.domain`). Pattern: **lo scopritore di coverage è anche scopritore di bug** — 5 difetti latenti emersi e corretti nella stessa sessione.

| Problema | Causa reale | Soluzione |
|----------|-------------|-----------|
| Ogni comando concreto (`MoveHeadCommand`, `EmergencyStopCommand`…, ~50 siti SDK) risultava inistanziabile: `TypeError: Can't instantiate abstract class` | `Command.__post_init__` era dichiarato `@abstractmethod` su un dataclass non-ABC: Python lo risolve come astratto e rifiuta l'istanziazione | Hook **concreto** no-op in `Command`; i subclass che devono validare lo sovrascrivono. Lezione: `@abstractmethod` su metodi di un dataclass di supporto (non dell'interfaccia) è una trappola silenziosa — nessuno li aveva mai istanziati nei test |
| `DomainEvent.to_dict()` restituiva solo `event_type/source_node/timestamp...` della base: il payload delle sottoclassi **spariva** (le metriche pubblicavano eventi vuoti) | Implementazione scritta a mano sui campi base, non generica | `to_dict()` itera `dataclasses.fields(self)`; `from_dict()` filtra le chiavi sconosciute e costringe i tipi dal wire (`category` stringa → Enum, `timestamp` ISO → float, `event_version` → int). Lezione: serializzazione sempre **derivata dallo schema**, mai enumerata a mano |
| `EVENT_CATEGORIES[event_type]` dava sempre BUSINESS | Lookup costruito male (chiave costante/copiata) | Mappa da dizionario testata per ogni tipo registrato |
| IK DLS non convergeva: oscillava a zigzag verso il target senza mai arrivarci | `dq = (J·Jᵀ + λI)⁻¹ Jᵀ e` calcolava il prodotto **sulle 3 righe cartesiane** (matrice 3×3) invece di `JᵀJ` **sui giunti** (n×n): dimensioni sbagliate = passi in direzioni errate | Gram matrix `A[i][j] = Σ_k J[k][i]·J[k][j]` (colonne·colonne). Lezione: in DLS la moltiplicazione è `JᵀJ` (n×n, uno per giunto); verificare sempre che `len(A) == len(joint_names)` |
| Anche con la matrice giusta, near-singolarità (braccio esteso) facevano esplodere il passo → ciclo limite | DLS non limitato: un passo completo può **aumentare** l'errore | (a) cap per giunto `IK_MAX_STEP_RAD = 0.5`; (b) **backtracking line search**: accettare il passo solo se riduce l'errore, altrimenti `alpha *= 0.5` fino a `IK_MIN_STEP_ALPHA`, poi arretrare alla migliore soluzione. Test: catena DH a link zero (J=0) copre esattamente i rami "matrice singolare" e "nessun miglioramento" |
| Il ramo **triangolare** del profilo rest-to-rest (mosse corte) terminava oltre il target | Accelerazione e decelerazione calcolate con formule diverse nel branch corto → discontinuità di posizione | Helper unico `_rest_to_rest_profile(distance, v_max, a_max)` → `(t_total, t_accel, accel_distance)` usato da entrambi i planner; il ramo trapezoidale ricalcola `accel_distance` dopo il clamp |
| `RedisEventBus` ricostruiva eventi con `DomainEvent.from_dict` | 3 call site: usavano la classe base → il tipo concreto andava perso in pipeline/dlq | `deserialize_event` (registry) nei 3 siti |

### Infrastruttura test (riuso per T-004/T-005)
- Config in `pyproject.toml`: `[tool.pytest.ini_options]` con `testpaths=["tests"]` e `pythonpath=["src"]` (niente `sys.path` manuali), `[tool.coverage.*]` con `source=["core.domain"]` e `exclude_also` su `TYPE_CHECKING`/`NotImplementedError`.
- Gate CI: `pytest tests/unit -q --cov=core.domain --cov-fail-under=90` (job `python-tests`).
- Python 3.11: `typing.is_protocol` non esiste (3.12+) → helper locale; `pytest.approx` usa `abs=`, non `abs_tol=`.
- Comandi: `python -m pytest tests/unit -q --cov=core.domain --cov-report=term-missing` (venv `.venv`, uv su `~/Library/Python/3.9/bin`).

---

## 1-sexies. Problemi Risolti (T-026 firmware Node 7, 2026-09-23)

Lezioni dalla consegna del primo firmware ESP-IDF realmente completo e buildato in CI.

| Problema | Causa reale | Soluzione |
|----------|-------------|-----------|
| Limiti viaggio Node 7 = `±4445` jsteps con commento "= 35 deg" (in `node.json`, `balance.json`, CONFIGURATION.md) | 4445 ÷ 35,556 jsteps/° = **±125°**, non 35°: il commento è errato da ADR-017, i configs hanno ereditato il numero | Corretto a **±1244** (= 35 × 12800/360) nei 3 punti + formula nel commento; test `test_step_math_and_travel_limits` con `assert expected == 1244 # the old 4445 must not come back` |
| Nessun nodo `firmware/` era compilabile (T-007/T-014 alla radice) | `common/CMakeLists.txt` elencava **19 sorgenti inesistenti** (servo/pca9685/ota/... aspirazionali) e README/documenti citavano file mai creati (`install_esp_idf.sh`, `head_controller.hpp`) | CMakeLists riscritto con **solo file reali**; README firmware/ riscritto reale. Regola: ogni riferimento di build va verificato con `ls`/glob prima di dichiararlo; docs fantasma = debito mascherato da documentazione |
| `trapezoid_velocity` Python **stateless**: da fermo salta a 1410 steps/s (`+accel*dt` non lega mai, nessun ramp-up) e il PID Python fa derivative kick al primo tick (`last_error=0`) | Profilo calcolato come funzione pura (v, dt, target) senza stato `v_prev`; PID con guardia assente | **✅ Risolto in T-029 (2026-10-07)**: `stepper.py` esporte le tre funzioni pure mirror del C++ (`slew`, `brake_bound`, `position_velocity_target`) e `trapezoid_velocity(v_now, steps_remaining, vmax, accel, dt)` con lo **stato `v_now` nel chiamante** (`a4988.py`, `mock_stepper.py`); `sim/leveling.py` con la **guardia `first_`** (reset anche al re-enable, specchio di `balance_pid.hpp:49`) + clamp output ±1600 che il C++ aveva. Parità fissata da `tests/unit/test_stepper_parity.py` (9 test sui vettori di `host_test.cpp`) |
| ACL Mosquitto per nodi 2–6 su `openj5/nodeN/#` e **nessun user `node7`** | Vecchio schema di topic pre-v1: i path reali sono `openj5/v1/<node>/...` (`config/common/topics.json`) — le regle non matchavano nulla e node7 non avrebbe potuto connettersi in mTLS | ACL riscritta sui path v1 + `topic read openj5/v1/system/#` per ogni nodo (E-stop) + sezione `user node7` (`openj5/v1/balance/#`); nessun nodo era ancora deployato → fix senza impatto |
| `generate.sh` produceva cert solo per `node1..node6` | Lista nodi duplicata in 3 punti (commento, loop generazione `for i in 1..6`, verify loop, summary) | `node7` aggiunto ai loop + commento + summary; test `test_certs_script_generates_node7` |
| Kconfig senza float né interi negativi vs config JSON con `kp=15.0`, `output_min=-1600` | Kconfig supporta solo `int`/`string`/`bool` | Float come **string** + `strtof()`; limiti simmetrici come **magnitudine** (`OPENJ5_PID_OUTPUT_MAX=1600` → `min=-max` uguale al JSON); test di parità Kconfig↔node.json↔bench↔docs |
| Verifica firmware **senza toolchain locale** (nessun `idf.py`, nessun docker) | Ambiente di sviluppo senza ESP-IDF | Due livelli: (1) logica pura separata dai driver ESP → `scripts/test/host_firmware.sh` g++/clang, 36 check, gira subito; (2) job CI `firmware-node7-build` con container `espressif/idf:v5.2.2`. Glue ESP (pulsanti, campi esp-mqtt v5) validato solo dalla prima run CI: iterare su rossi |
| Segno filtro Madgwick non documentato (quando il corpo si alza, quale segno ha `ax`?) | Report IMU ≠ angolo in assenza di convenzione scritta | Test host esplicito: inclinazione naso-**su** +θ legge `ax = −g·sin(θ)`; `pitch = asin(2(q0q2 − q1q3))` (ZYX). Convenzione scritta nel test, usata dal controller (`error = target − pitch`) |
| Possibili bug di periodo nei task FreeRTOS | `pdMS_TO_TICKS(HZ)` (legge "Hz" come "ms") darebbe 100 ms invece di 10 ms | Regola: `pdMS_TO_TICKS(1000 / HZ)` con guardia `period==0 → 1`; a `FREERTOS_HZ=1000` 100 Hz = 10 tick, 200 Hz = 5 tick |
| Caricamento richiesto da **VSCode + PlatformIO** (nessun IDF installato sul Mac) | La piattaforma ufficiale `espressif32` 6.12.x porta **IDF v5.5**, la CI resta sul container **v5.2.2**: due versioni diverse = API che compilano da una parte e non dall'altra | `platformio.ini` con pin esatto + commento che vincola le due versioni a muoversi **insieme**; presidio: `test_platformio_ini_matches_project`. Header legacy `driver/i2c.h` verificato **sul tag target** (v5.2.2 e v5.5, via GitHub API/raw) prima di dichiararlo sicuro — mai fidarsi di master/latest |
| Prima `pio run` fallita: `Failed to resolve component 'esp_mqtt': unknown name` | Il *component* IDF si chiama **`mqtt`** (directory `components/mqtt`, sorgenti dal submodule `esp-mqtt`): `esp_mqtt` non è mai esistito come nome — la CI non era ancora partita, quindi il refuso era latente in `common/`, `node7_balance/main/` e `node2_head/` | Corretto in tutti e 3 i CMakeLists (`REQUIRES mqtt`); verificato sull'IDF 5.5 locale (esempi ufficiali usano `PRIV_REQUIRES mqtt`) e vale anche per 5.2.2; presidio: `test_platformio_ini_matches_project` rifiuta `esp_mqtt` nei CMakeLists del grafo di build Node 7 |
| Seconda `pio run` rossa su decine di header IDF: `#include_next is a GCC extension` (newlib `platform_include/stdio.h`), array a dimensione zero/flexible member (`esp_wifi_types*.h`, `driver/gpio.h`), più `CONFIG_APP_PROJECT_VER`/bool Kconfig "undeclared identifier" | ADR-014 impone `-Wall -Wextra -Wpedantic -Werror`, ma IDF passa i **suoi** header come `-I` normali (`component.cmake:320`, niente SYSTEM): `idf.py`/CI fallirebbe allo stesso modo → il fix stava nel **CMakeLists condiviso**. Inoltre un Kconfig `bool` a default `n` è **assente** da sdkconfig.h (non vale 0) e `APP_PROJECT_VER` richiede `APP_PROJECT_VER_FROM_CONFIG=y` | Dopo `project()`: walk `SUBDIRECTORIES`+`BUILDSYSTEM_TARGETS` (proprietà `BUILTIN_TARGETS` non esiste in CMake) → ridefinire gli `INTERFACE_INCLUDE_DIRECTORIES` di tutti i `__idf_*` come `SYSTEM PRIVATE` su `__idf_main`/`__idf_common` **escludendo i nostri due** (i nostri dir restano `-I` = warnati pienamente); GCC ignora un `-I` sullo stesso dir dato anche con `-isystem` (dedup documentato, verificato con test A0-A4). I 3 bool letti con `#ifdef` → `constexpr bool` (`kDirInverted`/`kEnabledOnBoot`/`kMqttTls`); versione banner da `esp_app_get_description()->version` + `esp_app_format` in `REQUIRES`; `CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y` in `sdkconfig.defaults` |
| Terza `pio run` rossa su `firmware/common/`: `std::strlcpy` non esiste, `i2c_config_t` senza `clk_speed`/`clk_flags`, `esp_timer_start` inesistente, int→`esp_mqtt_event_id_t` | Il glue ESP era scritto ma **mai compilato per il target**: `host_firmware.sh` compila solo la logica pura (host_test/madgwick/state_machine) e la CI non era mai partita; inoltre gli esempi IDF sono **C** (int→enum implicito lecito) mentre il firmware è C++ | Ogni API rivista su **entrambi i tag** (raw v5.2.2 + esp-mqtt@`aa6f889` + locale 5.5) prima di correggere: `std::snprintf` (stessa semantica bounded+NUL, standard C++), member riordinati (`conf.master.clk_speed` + `conf.clk_flags = I2C_SCLK_SRC_FLAG_FOR_NOMAL`), `esp_timer_start_periodic` (e `esp_timer_restart` verificato **dalla sorgente IDF**: su timer periodic mantiene la periodicità), `MQTT_EVENT_ANY`. Esito: **`pio run` SUCCESS 137,9 s** — RAM 11,2%, flash 88,8% dello slot `factory` 1 M, immagine a 8 MB |

### Comandi di verifica firmware (ripetere a ogni sessione firmware)

```bash
scripts/test/host_firmware.sh                                       # 36 check, g++
.venv/bin/python -m pytest tests/unit -q --cov=core.domain --cov-fail-under=90   # 170 (dal 2026-10-07)
.venv/bin/ruff check src/ firmware/node1_robot_core/docker/src/ tests/
./scripts/check_docs.sh                                             # include BENCH_BALANCE.md
# build reale: CI (firmware-node7-build, IDF 5.2.2) o locale:
#   cd firmware/node7_balance && idf.py build   (IDF 5.2.2)
#   cd firmware/node7_balance && pio run         (PlatformIO, IDF 5.5)
```

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
