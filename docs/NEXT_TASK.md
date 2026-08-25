# NEXT_TASK — Prossime Attività per Priorità

> Aggiornare a ogni sessione. Formato: ID, Titolo, Descrizione, Priorità, Dipendenze, Stima, Stato.
> Ultimo aggiornamento: 2026-08-25 (sessione 2)

---

## Priorità Alta — Bloccanti v0.3.0 (CI/CD & Testing)

| ID | Titolo | Descrizione | Priorità | Dipendenze | Stima | Stato |
|----|--------|-------------|----------|------------|-------|-------|
| T-001 | Correggere CHANGELOG "Unreleased" | La sezione Unreleased dichiarava CI/CD e test inesistenti. Sistemata: voci rimosse, lavoro reale documentato | Alta | — | 0.5h | ✅ Fatto 2026-08-25 |
| T-002 | Pipeline GitHub Actions base | `.github/workflows/ci.yml` creato con job: python-lint (ruff), doc-check (`scripts/check_docs.sh`), docker-build robot-core. mypy e clang-tidy ancora da aggiungere quando il debito lo consente | Alta | — | 1g | 🟡 Parziale 2026-08-25 |
| T-003 | Suite unit test core domain | pytest su `src/core/domain/` (value objects, events, commands, entities): target ≥90% coverage; usare InMemory adapters già presenti | Alta | T-002 | 2g | ⬜ Da fare |
| T-004 | Integration test REST API + WebSocket | Test endpoint `robot_core/api/rest.py` con httpx/Testcontainers (postgres+redis); test WS bidirezionale | Alta | T-003 | 2g | ⬜ Da fare |
| T-005 | Integration test event bus + state machine | Round-trip RedisEventBus con consumer groups/DLQ; test tabella transizioni e fault propagation orchestratore | Alta | T-003 | 1.5g | ⬜ Da fare |
| T-006 | Simulation parity tests | Stessa suite gira contro mock driver e Gazebo headless in CI (base per GOALS G3) | Alta | T-005 | 3g | ⬜ Da fare |
| T-007 | Build firmware ESP-IDF in CI | Job che compila `firmware/node2_head` con container ESP-IDF 5.2. **Bloccato**: skeleton non compilabile (manca `head_controller.hpp`, sorgenti elencati nel CMakeLists, `include(project.cmake)`/`project()`) — completare prima T-014 | Alta | T-014 | 1g | 🔴 Bloccato |

## Priorità Media — Chiusura Debiti Codice

| ID | Titolo | Descrizione | Priorità | Dipendenze | Stima | Stato |
|----|--------|-------------|----------|------------|-------|-------|
| T-010 | Cablare i bus reali nell'SDK | `src/sdk/robot.py` TODO: inizializzare CommandBus/QueryBus da config invece di stub | Media | T-003 | 1g | ⬜ Da fare |
| T-011 | Auto-reconnect MqttGateway | Riconnessione con backoff esponenziale + risubscribe (`src/gateway/communication.py`) | Media | — | 0.5g | ⬜ Da fare |
| T-012 | Persistenza config runtime | `config.py`/`service.py`: persistere set() su file/DB con validazione schema | Media | — | 1g | ⬜ Da fare |
| T-013 | Firma artefatti plugin | Implementare verifica firma crittografica e permission proxy in `src/plugins/manager.py` | Media | T-015 | 2g | ⬜ Da fare |
| T-014 | Firmware Node 3 (Right Arm) | Controllo 6 servi con interpolazione traiettorie, gripper, collision detection base; riusare componenti `firmware/common`. Include: rendere compilabile lo skeleton Node 2 (CMakeLists valido + header/sorgenti mancanti) per sbloccare T-007 | Media | T-007 | 5g | ⬜ Da fare |
| T-015 | Riparare contratti framework plugin (`src/plugins/`) | Completato: creato `src/plugins/base.py` con contratti unici (IPlugin, IConfigurablePlugin, ILifecyclePlugin, IPluginManager, IPluginRegistry, PluginMetadata/State/Type/Dependency/Permission/ConfigSchema/Health, PluginContext unificato); rimosso l'import circolare; per-file-ignores rimossi da pyproject.toml. Bug latenti emersi e corretti di conseguenza in `src/core/domain/` (events slots/super, schemi eventi, entità dataclass, servizi mancanti KinematicsService/MotionPlanner ABC) | Media | — | 1g | ✅ Fatto 2026-08-25 |
| T-016 | Adottare `ruff format` | Formatter non ancora applicato (36 file da riformattare): decidere baseline, applicare in commit dedicato, aggiungere gate `ruff format --check` in CI | Media | T-015 | 0.5g | ⬜ Da fare |
| T-017 | Deploy RPi4 Node 1 | Guida completa (`docs/deployment/DEPLOYMENT.md`) + bootstrap automatico (`scripts/deploy/bootstrap_rpi4.sh`) — aggiornati ad **ADR-016**: Pi OS Lite 64-bit Bookworm + NVMe USB3, patch cgroup cmdline per limiti memoria, recovery bootloader USB via SD | Alta | — | 2g | ✅ Fatto 2026-08-25 (doc+script; esecuzione fisica sul Pi da validare) |
| T-018 | Validare deploy su hardware reale | Eseguire il bootstrap su un RPi4 8GB reale con Pi OS Lite su NVMe USB3: boot USB funzionante, cgroup attivi (test container 256MB), stack healthy dopo reboot, certificati letti da mosquitto, memoria entro budget (~4GB) | Alta | T-017 | 0.5g | ⬜ Da fare (richiede hardware) |

## Priorità Bassa — Roadmap v0.4.0+

| ID | Titolo | Descrizione | Priorità | Dipendenze | Stima | Stato |
|----|--------|-------------|----------|------------|-------|-------|
| T-020 | OTA client ESP32 completo | Download HTTPS + verifica signature + rollback (completare lato dispositivo di ADR-011) | Bassa | T-014 | 3g | ⬜ Da fare |
| T-021 | Rinnovo automatico certificati mTLS | Script/procedura di rotazione CA e certificati nodi | Bassa | — | 1g | ⬜ Da fare |
| T-022 | Firmware Node 4/5/6 | Mirror braccio SX; torso con BMS INA219/DS18B20; cingoli con PID+odometria+IMU | Bassa | T-014 | 8g | ⬜ Da fare |
| T-023 | Avvio CAD parametrico FreeCAD | Spreadsheet `openj5_params` + prime parti testa secondo ADR-012 | Bassa | — | 5g | ⬜ Da fare |
| T-024 | Vision/Speech plugin MVP | Camera + face detection OpenCV; TTS/STT base (ROADMAP v0.5.0) | Bassa | T-013 | 5g | ⬜ Da fare |

---

## Note

- Le stime sono ore-uomo indicative ("g" = giornata).
- Ogni task completato aggiorna anche: CHANGELOG, PROJECT_STATUS, PROJECT_MEMORY, SESSION_REPORT.
- Regola: nessun nuovo task si considera "chiuso" senza test + documentazione.
