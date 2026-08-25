# NAMING_CONVENTIONS

## Convenzioni di Denominazione OpenJ5

Convenzioni obbligatorie per garantire che il progetto sia leggibile e coerente tra software, firmware, config, topic MQTT e documentazione.

---

## 1. Lingua

- **Codice, identificatori, topic, chiavi di configurazione**: inglese.
- **Documentazione di governance e memoria di progetto**: italiano (VISION, MISSION, SESSION_REPORT...).
- **ADR e documentazione tecnica architetturale**: inglese (seguono i file esistenti).
- Niente abbreviazioni criptiche: `rightArm`, non `ra`; `configuration`, non `cfg` (tranne nei casi già consolidati come `cmd`/`evt` nei topic).

---

## 2. Python (Robot Core, SDK, Plugin)

| Elemento | Convenzione | Esempio |
|----------|-------------|---------|
| Moduli/package | `snake_case` | `event_bus.py`, `robot_core` |
| Classi | `PascalCase` | `MotionPlannerService`, `MqttGateway` |
| Interfacce/protocolli | prefisso `I` + PascalCase | `IServoDriver`, `ICommunicationGateway`, `IEventBus` |
| Funzioni/metodi | `snake_case`, verbo + nome | `look_at()`, `publish_event()` |
| Variabili | `snake_case` | `target_pose` |
| Costanti | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Value Objects | nome del concetto del dominio | `Angle`, `Pose3D`, `JointAngles` |
| Eventi dominio | `PascalCase` al passato/presente descrittivo | `ServoMoved`, `FaceDetected`, `BatteryLow`, `NodeStateChanged` |
| Comandi | `PascalCase` + suffisso `Command` | `MoveHeadCommand`, `SayTextCommand` |
| Query | `PascalCase` + suffisso `Query` | `GetRobotStateQuery` |
| Adapter infrastruttura | Tecnologia + ruolo | `RedisEventBus`, `SqliteRepository`, `PCA9685Driver` |

---

## 3. C++ Firmware (ESP-IDF)

| Elemento | Convenzione | Esempio |
|----------|-------------|---------|
| File header | `snake_case.hpp` | `servo_manager.hpp` |
| Namespace | `openj5::` + nodo/modulo | `openj5::hal`, `openj5::node2` |
| Classi | `PascalCase` | `HeadController`, `ServoManager` |
| Interfacce HAL | `I` + PascalCase, header in `common/include/hal/` | `IServoDriver`, `IMotorDriver` |
| Metodi | `camelCase` (coerenza con SDK) | `setPosition()`, `getOdometry()` |
| Costanti/#define | `UPPER_SNAKE_CASE` con prefisso modulo | `NODE2_MAX_SERVOS` |
| Tag log ESP | stringa breve per modulo | `"node2_head"`, `"servo_mgr"` |

---

## 4. Topic MQTT

Formato obbligatorio, versionato:

```
openj5/v<major>/<node>/<canale>
```

| Segmento | Valori ammessi | Esempio |
|----------|----------------|---------|
| Prefisso | fisso `openj5` | `openj5/v1/head/cmd` |
| Versione | `v1`, `v2`, ... (breaking change = nuovo major) | — |
| Nodo | `head`, `right_arm`, `left_arm`, `torso`, `tracks`, `core` | `openj5/v1/tracks/cmd` |
| Canale | `cmd` (comandi), `evt` (eventi), `telemetry`, `ota`, `status` | `openj5/v1/head/evt` |

Payload comandi: JSON con campo `command` logico (`look_at`, `wave`, `move_forward`) — **mai angoli servo diretti**.

---

## 5. Eventi Event Bus

- Stream prefix Redis: `openj5.events.<categoria>`.
- `event_type`: PascalCase descrittivo (`FaceDetected`).
- Ogni evento: `event_id` (UUID), `source_node` (`node1`…`node6`), `correlation_id`.

---

## 6. Configurazione (JSON/YAML)

- File: `snake_case.json` (`node.json`, `servos.json`, `topics.json`, `safety.json`).
- Chiavi: `dot.notation` in camelCase o snake_case coerente col consumer; accesso via dot-notation dal Config Service.
- Nodi: directory `config/node1_robot_core/` … `config/node6_tracks/` (nome = funzione, non numero alone).
- Servi/motori: nome funzionale (`neck_yaw`, `shoulder_pitch`, `left_motor`) mai canale numerico come identificatore.

---

## 7. Docker / Infrastruttura

| Elemento | Convenzione | Esempio |
|----------|-------------|---------|
| Container | `openj5-<servizio>` | `openj5-mosquitto`, `openj5-robot-core` |
| Volumi | `<servizio>_data` | `postgres_data`, `mosquitto_logs` |
| Network | `robot-internal` | — |
| ENV | prefisso `OPENJ5_` + path config | `OPENJ5_EVENTBUS_REDIS_URL` |
| Secrets | nome funzionale senza estensione | `db_password`, `grafana_admin_password` |

---

## 8. Git

- Branch: `feat/<area>-<descrizione>`, `fix/<area>-<descrizione>` (es. `feat/firmware-node3-arm`).
- Commit: conventional commits con scope opzionale → `fix(docker): ...`, `feat(sdk): ...`.
- ADR: `docs/adr/ADR-XXX-title-slug.md` (kebab-case, titolo corto minuscolo).

---

## 9. Documenti di Progetto

| Documento | Nome fisso |
|-----------|-----------|
| Memoria permanente | `docs/PROJECT_MEMORY.md` |
| Report sessione | `docs/SESSION_REPORT.md` |
| Prossime attività | `docs/NEXT_TASK.md` |
| Knowledge base | `docs/KNOWLEDGE_BASE.md` |
| Prompt di continuità | `docs/CONTINUATION_PROMPT.md` |
| Stato progetto | `PROJECT_STATUS.md` (root) |
| Roadmap | `ROADMAP.md` (root) |
| Changelog | `CHANGELOG.md` (root) |

---

## Riferimenti

- `governance/CODING_STANDARD.md`
- `docs/configuration/CONFIGURATION.md`
- `config/common/topics.json`
