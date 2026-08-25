# NEXT_TASK — Prossime Attività per Priorità

> Aggiornare a ogni sessione. Formato: ID, Titolo, Descrizione, Priorità, Dipendenze, Stima, Stato.
> Ultimo aggiornamento: 2026-08-25

---

## Priorità Alta — Bloccanti v0.3.0 (CI/CD & Testing)

| ID | Titolo | Descrizione | Priorità | Dipendenze | Stima | Stato |
|----|--------|-------------|----------|------------|-------|-------|
| T-001 | Correggere CHANGELOG "Unreleased" | La sezione Unreleased dichiara CI/CD e test non esistenti nel repo. Spostare le voci in "Planned" o rimuoverle finché non reali | Alta | — | 0.5h | ⬜ Da fare |
| T-002 | Pipeline GitHub Actions base | `.github/workflows/ci.yml`: ruff + mypy su Python, build Docker robot-core, check doc (doc esiste per file modificati), lint C++ clang-tidy su firmware | Alta | — | 1g | ⬜ Da fare |
| T-003 | Suite unit test core domain | pytest su `src/core/domain/` (value objects, events, commands, entities): target ≥90% coverage; usare InMemory adapters già presenti | Alta | T-002 | 2g | ⬜ Da fare |
| T-004 | Integration test REST API + WebSocket | Test endpoint `robot_core/api/rest.py` con httpx/Testcontainers (postgres+redis); test WS bidirezionale | Alta | T-003 | 2g | ⬜ Da fare |
| T-005 | Integration test event bus + state machine | Round-trip RedisEventBus con consumer groups/DLQ; test tabella transizioni e fault propagation orchestratore | Alta | T-003 | 1.5g | ⬜ Da fare |
| T-006 | Simulation parity tests | Stessa suite gira contro mock driver e Gazebo headless in CI (base per GOALS G3) | Alta | T-005 | 3g | ⬜ Da fare |
| T-007 | Build firmware ESP-IDF in CI | Job che compila `firmware/node2_head` con container ESP-IDF 5.2 (valida CMakeLists attuali) | Alta | T-002 | 1g | ⬜ Da fare |

## Priorità Media — Chiusura Debiti Codice

| ID | Titolo | Descrizione | Priorità | Dipendenze | Stima | Stato |
|----|--------|-------------|----------|------------|-------|-------|
| T-010 | Cablare i bus reali nell'SDK | `src/sdk/robot.py` TODO: inizializzare CommandBus/QueryBus da config invece di stub | Media | T-003 | 1g | ⬜ Da fare |
| T-011 | Auto-reconnect MqttGateway | Riconnessione con backoff esponenziale + risubscribe (`src/gateway/communication.py:261`) | Media | — | 0.5g | ⬜ Da fare |
| T-012 | Persistenza config runtime | `config.py`/`service.py` TODO: persistere set() su file/DB con validazione schema | Media | — | 1g | ⬜ Da fare |
| T-013 | Firma artefatti plugin | Implementare verifica firma crittografica e permission proxy in `src/plugins/manager.py` (stubi a righe ~408/431) | Media | ADR-007 | 2g | ⬜ Da fare |
| T-014 | Firmware Node 3 (Right Arm) | Controllo 6 servi con interpolazione traiettorie, gripper, collision detection base; riusare componenti `firmware/common` | Media | T-007 | 5g | ⬜ Da fare |

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
