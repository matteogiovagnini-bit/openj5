# OpenJ5 Firmware — ESP-IDF (C++20)

Firmware dei nodi ESP32-S3 secondo **ADR-014** (ESP-IDF v5.2+, C++20,
`-Wall -Wextra -Wpedantic -Werror`), **ADR-017** (Node 7 Balance) e **ADR-019**
(tutti i nodi ESP32-S3; il Raspberry Pi è solo cervello).

## Stato reale (2026-10-09)

| Progetto | Target | Stato |
|----------|--------|-------|
| `node7_balance/` | ESP32-S3 | ✅ completo — buildato in CI (`firmware-node7-build`) |
| `node6_tracks/` | ESP32-S3 | 🟡 bring-up motori (ADR-019 / T-022): L298N + comandi MQTT + watchdog/fail-safe; build ESP-IDF **non ancora in CI**, validazione on-device = **T-033** |
| `node2_head/` | ESP32-S3 | 🔴 `src/main.cpp` esiste ma include `head_controller.hpp`, che manca → non compilabile → **T-014** (sblocca T-007) |
| `node3` … `node5` | ESP32-S3 | ⬜ non iniziati (T-014, T-022); le rispettive cartelle non esistono ancora |
| `node1_robot_core/` | — | non è firmware: contiene Docker/Python del Nodo 1 (il Nodo 1 è il Raspberry Pi, solo cervello) |

## Struttura

```
firmware/
├── common/                 # Componente ESP-IDF condiviso (REQUIRES reale)
│   ├── CMakeLists.txt      # elenca SOLO file esistenti (v. nota sotto)
│   ├── include/
│   │   ├── hal/            # stepper_logic + stepper_driver (port); motor_logic + motor_driver (port, ADR-018/019)
│   │   ├── drivers/        # A4988Driver, Mpu6050Driver, L298NDriver (ESP32-S3, ADR-019)
│   │   ├── imu/            # Madgwick 9 assi (puro)
│   │   ├── statemachine/   # FSM ADR-009 (tabella, pura)
│   │   └── comms/          # WifiStation, MqttClient (esp-mqtt, mTLS opzionale)
│   ├── drivers/  imu/  statemachine/  comms/   # .cpp corrispondenti
│   └── test/host_test.cpp  # unit test host (g++, nessun ESP-IDF)
├── node7_balance/          # ✅ progetto ESP-IDF completo (vedi il suo README)
├── node6_tracks/           # 🟡 bring-up motori ESP32-S3 (ADR-019, vedi il suo README)
├── node2_head/             # skeleton (src/main.cpp con header mancante, T-014)
└── node1_robot_core/       # Robot Core (Docker/Python sul Pi, non firmware)
```

> **Regola (KNOWLEDGE_BASE §1-sexies)**: `common/CMakeLists.txt` elencava 19
> sorgenti inesistenti → nessun nodo che lo usava era compilabile (causa alla
> radice di T-007/T-014). Ora elenca solo file reali: chi implementa un nodo
> aggiunge i propri sorgenti qui (o in un suo componente), mai riferimenti
> "fantasma".

## Build

### Node 7 (progetto completo)

**A — VSCode + PlatformIO (consigliata)** — v. `node7_balance/README.md`
§"Procedimento di caricamento":

```bash
cd firmware/node7_balance
pio run                       # build (prima volta: scarica IDF v5.5, ~1 GB)
pio run -t upload -t monitor  # flash + monitor (porta autodetect)
```

**B — ESP-IDF classico (`idf.py`)**:

```bash
. $IDF_PATH/export.sh          # ESP-IDF v5.2+ (https://docs.espressif.com)
cd firmware/node7_balance
idf.py set-target esp32s3
idf.py flash monitor
```

WiFi/MQTT locali in `sdkconfig.local` (gitignored) — v. `node7_balance/README.md`.
Le due versioni di IDF (5.5 via PlatformIO, 5.2.2 via idf.py/CI) devono
restare entrambe supportate: vincolo annotato in `platformio.ini` e verificato
da `tests/unit/test_node7_config_sync.py`.

### Node 6 Tracks (bring-up motori, ADR-019)

Progetto ESP-IDF/PlatformIO completo per il bring-up motori (env `node6`);
dettagli in `node6_tracks/README.md`. **La build non è ancora in CI** (T-033
copre la validazione on-device).

```bash
cd firmware/node6_tracks
pio run -e node6 -t upload -t monitor   # PlatformIO (IDF v5.5)
# oppure: idf.py set-target esp32s3 && idf.py build flash monitor
```

### Logica pura su host (senza ESP-IDF)

```bash
scripts/test/host_firmware.sh   # g++/clang: rampa motori DC, rampa, Madgwick, PID, FSM — 53 check
```

### CI (`.github/workflows/ci.yml`)

- `firmware-host-tests`: esegue lo script host a ogni commit/PR;
- `firmware-node7-build`: `idf.py set-target esp32s3 && idf.py build` dentro il
  container `espressif/idf:v5.2.2`.

Verifica locale aggiuntiva (non in CI): `pio run` in `node7_balance/` compila
con ESP-IDF v5.5 (piattaforma `espressif32` 6.12.x) — stesso codice, IDF
diversa dalla CI: se una delle due sale, aggiornare insieme `platformio.ini`
e `ci.yml`.

## Configurazione comune

`sdkconfig.defaults` di ogni progetto (es. `node7_balance/`):

- `CONFIG_FREERTOS_HZ=1000`
- `CONFIG_COMPILER_OPTIMIZATION_PERFORMANCE=y`
- `CONFIG_MQTT_PROTOCOL_311=y`
- `CONFIG_PARTITION_TABLE_TWO_OTA=y`
- `CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192`

Tutte le costanti di dominio (pin, limiti, PID, rete) vivono in
`main/Kconfig.projbuild` e devono restare in sincronia con
`config/<node>/node.json` — verificato da
`tests/unit/test_node7_config_sync.py`.
