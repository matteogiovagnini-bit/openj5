# AGENTS.md — Istruzioni di progetto per gli agenti

Progetto: **OpenJ5** — piattaforma robotica open source ispirata a Johnny 5.
Stack: Python ≥3.11 (`src/`, hexagonal + Ports & Adapters), firmware C++20 / ESP-IDF v5.2+ (`firmware/`), Docker Compose su Raspberry Pi 4 (Node 1).

Leggi prima di lavorare, in quest'ordine:

1. `governance/` — le "leggi" del progetto (VISION, GOALS, NON_GOALS, CONSTRAINTS, ARCHITECTURAL_PRINCIPLES, CODING_STANDARD, NAMING_CONVENTIONS)
2. `Development_Constitution.md` — regole comportamentali e Design Authority
3. `docs/NEXT_TASK.md` — backlog strutturato (T-001…T-029) con priorità e dipendenze
4. `docs/adr/` — decisioni architetturali già prese (INDEX.md)

## Comandi di verifica (devono restare verdi)

```sh
ruff check src/ firmware/node1_robot_core/docker/src/ tests/        # lint
pytest tests/unit -q --cov=core.domain --cov-fail-under=90          # test (pythonpath=src)
./scripts/check_docs.sh                                             # doc gate (27 file obbligatori + ADR INDEX)
./scripts/test/host_firmware.sh                                     # test firmware host (g++ C++20)
cd firmware/node7_balance && pio run                                # build firmware Node 7 (PlatformIO/IDF 5.5)
```

## Regole non negoziabili

- **Nessun numero magico nel codice.** Ogni valore viene da JSON di `config/`, YAML, DB o Configuration Service. Non `speed = 120`, ma `speed = config.get_motor_speed()`.
- **Mai usare driver concreti nel codice di dominio.** Solo interfacce HAL: `IServoDriver`, `IMotorDriver`, `ILedDriver`, `ICameraDriver`, `IMicrophone`, `IBatteryMonitor`. I chip (PCA9685, L298N, A4988…) vivono solo in `src/hardware/drivers/` o nel firmware.
- **Dependency rules.** Vision → RobotCore → Hardware. Mai l'inverso. Nessun modulo deve invertire questa freccia.
- **Digital Twin.** Il simulatore espone le stesse API del robot reale: il software non sa se controlla hardware o mock.
- **SDK come unica facciata.** Tutto ciò che sta sopra usa `src/sdk/robot.py`, mai moduli interni direttamente.
- **Continuous Documentation.** Ogni nuova funzione aggiorna: README, API (`docs/api/`), diagrammi (Mermaid), ROADMAP, ADR se serve, CHANGELOG, PROJECT_STATUS.
- **Nessun task chiuso senza test + documentazione.**
- **Mai scrivere o modificare certificati, chiavi, credenziali o file `.env`.** Non inventare valori per la sicurezza: segnala e chiedi.

## Livelli di decisione (Development_Constitution)

| Livello | Tipo | Esempi | Azione |
|---|---|---|---|
| A | Automatica | refactoring, rename, commenti, ottimizzazioni | Esegui |
| B | Proposta | nuove librerie, package, driver | Proponi all'utente |
| C | Approvazione obbligatoria | cambio architettura, hardware, protocollo, eliminazione di funzionalità | **Fermati e chiedi** |

## Design Authority (obbligatoria a fine task)

Nessuna funzionalità è "completata" senza aver superato tutti i controlli:
compatibilità con architettura generale, ADR, Robot SDK, Digital Twin, sistema di configurazione, roadmap, test, firmware ESP32, CAD/elettronica, e nessuna violazione della Project Constitution.

## Agenti del team

`orchestrator` (primary) coordina e delega a: `architect`, `python-dev`, `firmware-dev`, `tester`, `tech-writer`.
Avvia un ciclo con `/orchestra`.
