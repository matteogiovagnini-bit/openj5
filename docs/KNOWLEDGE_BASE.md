# KNOWLEDGE_BASE — Base di Conoscenza OpenJ5

> Problemi risolti, procedure, best practice, errori da evitare. Alimentare a ogni sessione.
> Ultimo aggiornamento: 2026-08-25

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
