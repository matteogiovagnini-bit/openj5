# OpenJ5 Bench Bring-Up — Nodo 6 Cingoli (ESP32-S3 + L298N + 2× DC Gear Motor)

> Guida di banco del **Nodo 6 (Tracks)** secondo **ADR-019**: i motori sono
> pilotati **dall'ESP32-S3** via L298N, con comandi logici MQTT. Il Raspberry Pi
> (Nodo 1) è **solo cervello** e non tocca mai il PWM.
> Schema di collegamento fisico pin-per-pin: **`docs/hardware/NODE6_ESP32_WIRING.md`**.
> Firmware: `firmware/node6_tracks/` (PlatformIO env `node6`).
> Ultimo aggiornamento: 2026-10-09

> ⚠️ **Il vecchio banco “Pi → GPIO → L298N” è ritirato.** Fino alla Fase 1 di T-025
> il Raspberry Pi pilotava i motori con `src/hardware/drivers/l298n.py` + demo
> `scripts/demo/tracks_bench.py` + `config/bench/tracks.json`: quei file **non
> esistono più** (ADR-019). L'attuale catena di attuazione è l'ESP32-S3 di Node 6.
> Le lezioni elettriche acquisite su quel banco restano valide e confluiscono qui.

---

## 1. Materiale

| Componente | Note |
|------------|------|
| ESP32-S3 DevKitC-1 (o compatibile) | Nodo 6, WiFi nativo |
| Modulo L298N dual H-bridge | Versione blu con heatsink e jumper |
| 2× motoriduttore DC 12 V (XD-37GB520 300 rpm) | Uno sinistro, uno destro |
| Batteria LiPo 3S (11,1–12,6 V) o alimentatore 12 V ≥2 A | Potenza **solo** ai motori |
| Fusibile inline 5 A (consigliato) sul + batteria | Protezione cortocircuiti |
| Cavetti dupont + portafusibili | Segnali e massa |

---

## 2. Collegamenti

Lo **schema completo** (tabella pin ESP32-S3 → L298N, diagramma Mermaid dei
collegamenti con batteria e motori, note elettriche, mappa encoder/I2C/ToF/bumper)
è in **`docs/hardware/NODE6_ESP32_WIRING.md`**. In sintesi:

| Segnale | GPIO ESP32-S3 |
|---------|---------------|
| ENA / IN1 / IN2 (motore sinistro) | 4 / 5 / 6 |
| ENB / IN3 / IN4 (motore destro) | 7 / 15 / 16 |
| GND | GND (massa comune) |
| +5V logica L298N | 5V (VBUS) |

### 2.1 Alimentazione (riepilogo)

```
   BATTERIA 3S ──┬── (fusibile 5A) ── VMS (L298N)     POTENZA MOTORI (mai dall'ESP!)
                 └── GND ──┬── GND (L298N)
                           └── GND (ESP32-S3)         ← STESSA MASSA ⚠️
   ESP32-S3 5V (VBUS) ──── +5V (L298N, jumper regolatore rimosso)
   ESP32-S3 GPIO ───────── ENA/IN1..IN4               ← SOLO SEGNALI
```

- **Massa comune obbligatoria**: batteria − ↔ GND L298N ↔ GND ESP32-S3.
- Con **LiPo piena 12,6 V** rimuovere il **jumper del regolatore 5 V** di bordo e
  alimentare la logica del modulo dal 5 V dell'ESP32-S3 (dettagli in
  `NODE6_ESP32_WIRING.md` §4).
- **Jumper ENA/ENB rimossi**: sostituiti dal PWM sui GPIO 4/7.
- **Fusibile inline** sul + batteria.

### 2.2 Checklist pre-test

1. Jumper ENA/ENB rimossi ✅
2. Jumper regolatore 5 V rimosso (con LiPo 3S piena) ✅
3. Massa comune verificata (continuità GND batteria ↔ modulo ↔ ESP32-S3) ✅
4. **Ruote sollevate da terra** ✅
5. Fusibile inline inserito ✅
6. La **batteria si collega PER ULTIMA**, tutto già cablato ✅

---

## 3. Software (firmware ESP32-S3)

Il driver reale è il **firmware del Node 6** (`firmware/node6_tracks/`), che
implementa il port `IMotorDriver` (ADR-005/ADR-018) lato ESP32-S3 tramite il
componente condiviso `firmware/common/`:

- `firmware/common/drivers/l298n_driver.{hpp,cpp}` — L298N su ESP32-S3, PWM LEDC
  1000 Hz / 10 bit, rampa avanzata dal task di controllo (nessuno sleep bloccante);
- `firmware/common/include/hal/motor_logic.hpp` — matematica pura
  (`clamp_velocity`/`motor_levels`/`ramp_schedule`), **specchio 1:1** di
  `src/hardware/hal/motor.py` (ADR-018, T-032);
- `firmware/node6_tracks/main/` — parser comandi, state machine (ADR-009),
  watchdog/fail-safe, task controllo 50 Hz, telemetria 1 Hz.

I pin **non sono nel codice**: vivono in `config/node6_tracks/node.json` e
`firmware/node6_tracks/main/Kconfig.projbuild` (zero numeri magici, ADR-008).

### 3.1 Build e flash

```bash
cd firmware/node6_tracks
cp sdkconfig.local.example sdkconfig.local   # WiFi/MQTT (mai committato)
pio run -e node6                 # build (prima volta scarica IDF v5.5, ~1 GB)
pio run -e node6 -t upload       # flash (porta autodetect)
pio device monitor               # log UART0, 115200
```

In alternativa (stesso progetto ESP-IDF): `idf.py set-target esp32s3` (prima volta),
`idf.py build`, `idf.py -p PORT flash monitor`.

Logica pura su host (senza ESP-IDF, g++, include la rampa motori):
```bash
scripts/test/host_firmware.sh
```

### 3.2 Comandi di prova (MQTT)

Topic `openj5/v1/tracks/cmd` (v. `config/common/topics.json`):

| Payload | Effetto |
|---------|---------|
| `{"cmd":"forward","velocity":0.3}` | entrambi i motori avanti |
| `{"cmd":"backward","velocity":0.3}` | entrambi i motori indietro |
| `{"cmd":"spin_left","velocity":0.3}` | sinistro indietro, destro avanti |
| `{"cmd":"spin_right","velocity":0.3}` | sinistro avanti, destro indietro |
| `{"cmd":"stop"}` | short-brake immediato (priorità) |

```bash
mosquitto_pub -h <broker> -t openj5/v1/tracks/cmd -m '{"cmd":"forward","velocity":0.3}'
mosquitto_pub -h <broker> -t openj5/v1/tracks/cmd -m '{"cmd":"stop"}'
```

`velocity` è normalizzata in `[-1, +1]` (default 0.3, clampata ai limiti config).
Telemetria su `openj5/v1/tracks/telemetry`, stato retained su `.../state`, ack su
`.../evt`. E-stop di sistema: `openj5/v1/system/emergency_stop`.

**Procedura sicura**: **ruote sollevate da terra** (checklist §2.2). Osservare che i
due motori girino nel senso atteso in ogni fase e che la velocità vari con
`velocity`; a `stop` devono fermarsi (freno). A fine sessione: comando `stop`,
poi **stacca la batteria**.

### 3.3 Fail-safe (cosa aspettarsi)

- motori **rilasciati al boot** (PWM 0): nessun movimento finché non arriva un comando;
- **watchdog comando 1000 ms**: comandi fermi mentre si marcia → short-brake + fault;
- **link MQTT perso** → short-brake + fault;
- **watchdog loop**: stall del task → brake + fault (monitor reboot dopo 5×);
- **E-stop di sistema** su `openj5/v1/system/emergency_stop`.

---

## 4. Spegnimento fine sessione

1. Invia il comando `stop` (motori frenati).
2. **Stacca la batteria** dal L298N (o apri lo switch di linea se installato).
3. Scollega l'alimentazione dell'ESP32-S3.
4. (Opzionale) ferma lo stack Docker del Nodo 1:
   ```bash
   cd ~/src/openj5/firmware/node1_robot_core/docker
   docker compose stop
   ```
5. Se spegni il Pi: `sudo poweroff`, attendi ~20 s che il LED verde (ACT) smetta di
   lampeggiare, poi stacca l'alimentatore USB-C.

**LiPo**: se resta fermo settimane, riportalo a *storage* (~11,4 V) col caricabatterie.

---

## 5. Riaccensione / riattivazione

1. Collega l'alimentazione dell'ESP32-S3 e, se serve, accendi il Pi (boot da NVMe ~60 s).
2. Attendi che lo stack Docker risalga (policy `unless-stopped`):
   ```bash
   cd ~/src/openj5/firmware/node1_robot_core/docker
   docker compose ps          # tutto Up; robot-core healthy dopo ~90s
   curl -fk https://localhost:8080/health
   ```
3. Per i motori: **collega la batteria dopo** l'accensione, ruote sollevate,
   invia i comandi di prova (§3.2).

---

## 6. Troubleshooting rapido

| Sintomo | Causa / cura |
|---------|--------------|
| Un motore gira al contrario | Inverti i suoi DUE fili su OUTx (o `inverted` in config) |
| Velocità fissa, ignora `velocity` | Jumper ENA/ENB ancora montati |
| L'ESP32-S3 si riavvia quando parte il motore | Massa comune assente o potenza presa dall'USB |
| Il motore non gira (PWM 0) | Nessun comando / watchdog scaduto / nodo in `error` |
| Il nodo va in `error` durante la marcia | Comandi MQTT interrotti > 1000 ms → invia un nuovo comando per ripristinare |
| `Detected size(4096k) smaller than …(8192k)` | Board da 4 MB: `board_upload.flash_size = 4MB` (già in `platformio.ini`) |

---

*Rispetta ADR-019 (tutti i nodi ESP32-S3; il Pi è solo cervello), ADR-005 (HAL),
ADR-008 (zero numeri magici) e ADR-018 (port `IMotorDriver`). Cablaggio dettagliato:
`docs/hardware/NODE6_ESP32_WIRING.md`.*
