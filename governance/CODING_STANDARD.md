# CODING_STANDARD

## Regole di Scrittura del Codice OpenJ5

Queste regole valgono per tutto il software (Python, C++ firmware) e sono verificate in code review e, dove possibile, da CI. Una violazione senza ADR che la giustifichi blocca il merge.

---

## 1. Principi Generali

| Regola | Dettaglio |
|--------|-----------|
| **SOLID** | Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion applicati ovunque |
| **Clean Code** | Nomi che raccontano l'intento, funzioni piccole (max ~30 righe), zero side effects nascosti |
| **Clean Architecture** | Dipendenze solo verso il dominio; infrastruttura isolata negli adapter |
| **DDD** | Ubiquitous language: i nomi del codice coincidono con quelli del dominio (`ServoMoved`, `NodeStateChanged`, `MotionPlanner`) |
| **Composizione > Ereditarietà** | Preferire composizione e protocolli; ereditarietà solo per gerarchie di interfacce |
| **Dependency Injection** | Sempre via costruttore; composizione solo nel composition root |
| **DRY** | Mai duplicare codice: estrai in utility/base class/shared library |
| **YAGNI con visione** | Nessuna funzionalità speculativa, ma ogni scelta pensata per durare anni |

---

## 2. Vietato Assolutamente

1. **Numeri magici**: ogni valore da configurazione. `speed = Config.get("servo.neck_yaw.speed")`, mai `speed = 120`.
2. **Variabili globali** per stato o servizi.
3. **Dipendenze dirette dal transport**: mai `import mqtt` / topic MQTT nel codice applicativo — solo `ICommunicationGateway`.
4. **Accesso diretto all'hardware** fuori dagli adapter HAL: mai PCA9685/L298N/VL53L0X fuori dai driver.
5. **TODO senza descrizione**: ogni TODO deve avere ID, descrizione, owner, link a issue. Un TODO orfano non si mergea.
6. **Codice di esempio/pseudo-codice/temporaneo** nei sorgenti: ogni file deve essere realmente utilizzabile e compilabile.
7. **Classi troppo grandi**: se una classe supera ~300 righe è candidata alla scomposizione.
8. **Copy-paste tra nodi firmware**: il codice comune va in `firmware/common/`.

---

## 3. Convenzioni Python (Robot Core, SDK, Plugin)

- **Versione**: Python 3.11+, type hints obbligatori su tutte le firme pubbliche.
- **Stile**: PEP 8; formattazione con `ruff format` (o black), lint con `ruff`, type check con `mypy` (strict sul core domain).
- **Async**: I/O (MQTT, DB, Redis, HTTP) sempre async; API sincrone fornite solo come wrapper nell'SDK.
- **Error handling**: nessun `except:` nudo; errori di dominio come tipi dedicati; `Result` pattern dove già adottato.
- **Logging**: solo structlog JSON con correlation ID; mai `print()`.
- **Config**: accesso tramite `IConfigProvider`; validazione Pydantic/JSON Schema ai bordi.
- **Test**: pytest, copertura ≥90% core domain, ≥80% plugin; unit test senza I/O reale (InMemory adapters).
- **Docstring**: obbligatorie su classi e funzioni pubbliche (Google style).

---

## 4. Convenzioni C++ (Firmware ESP-IDF)

- **Standard**: C++20; warning `-Wall -Wextra -Wpedantic -Werror`.
- **Interfacce HAL**: classi astratte pure in `firmware/common/include/hal/`; implementazioni nei driver.
- **FreeRTOS**: task dedicate per loop critici; code per comunicazione tra task; mai busy-wait.
- **Memoria**: no allocazioni dinamiche nel loop realtime; PSRAM per buffer grandi su ESP32-S3.
- **Config**: tutti i parametri da NVS/JSON caricati al boot, mai costanti sparse.
- **State machine**: ogni nodo implementa BOOT→INIT→READY→RUNNING→ERROR→RECOVERY→SHUTDOWN.
- **Fail-safe**: watchdog attivo, posi di sicurezza su loss of comms.
- **Log**: `ESP_LOGx` con tag per modulo, livelli da sdkconfig.

---

## 5. Gestione degli Errori e Fail-Safe

- Ogni comando esterno validato prima dell'esecuzione: range, rate limit, auth.
- Su fault: servi → home position, motori → brake, LED → pattern errore, evento su Event Bus.
- Transizioni anomale → stato ERROR → RECOVERY automatico dove possibile.
- Ogni fault produce un evento persistito (audit trail).

---

## 6. Sicurezza nel Codice

- Mai segreti/chiavi nel repository (usare `docker/secrets/`, ENV, NVS).
- Nessun log di credenziali o payload sensibili.
- Input validation ai confini (REST handler, gateway, firmware command parser).
- OTA: solo firmware firmato; verifica signature prima del flash.

---

## 7. Commit e Branch

- Commit **atomici**: una modifica logica per commit.
- Messaggi: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`) con scope quando utile, es. `fix(docker): ...`.
- Ogni commit che tocca codice aggiorna anche CHANGELOG (e doc collegate); il working tree dopo ogni commit deve essere eseguibile.
- Mai push diretto su main per feature significative: PR + quality gate.

---

## 8. Definition of Done (per ogni funzionalità)

1. Analisi e verifica impatto architetturale
2. Documentazione aggiornata (prima/durante)
3. ADR creato se decisione significativa
4. Implementazione
5. Unit test + integration test
6. Refactoring + self review (duplicazioni? SOLID? dipendenze inutili? valido tra 3 anni?)
7. README, CHANGELOG, PROJECT_STATUS, PROJECT_MEMORY, NEXT_TASK aggiornati
8. SESSION_REPORT generato a fine sessione

Se manca un punto, la funzionalità NON è considerata terminata.

---

## Riferimenti

- `Development_Constitution.md`
- `governance/NAMING_CONVENTIONS.md`
- `governance/ARCHITECTURAL_PRINCIPLES.md`
- `PERSISTENT_PROJECT_MEMORY.md`
