# OpenJ5 Node 7 — Balance Controller (ESP32-S3 + A4988 + NEMA17 + MPU6050)

Firmware del nodo 7 secondo **ADR-017**: mantiene il corpo orizzontale
rispetto alla gravità indipendentemente dall'inclinazione dei cingoli.

- Cablaggio pin, alimentazione e procedura di bench: **`docs/hardware/BENCH_BALANCE.md`**
- Config sincronizzata: `config/node7_balance/node.json` ↔ `main/Kconfig.projbuild`
  (verificata da `tests/unit/test_node7_config_sync.py`)
- Logica pura testata su host: `scripts/test/host_firmware.sh`

## Struttura

```
node7_balance/
├── CMakeLists.txt          # progetto ESP-IDF (+ componente ../common)
├── platformio.ini          # VSCode + PlatformIO (board esp32-s3, IDF 5.5)
├── sdkconfig.defaults      # FREERTOS_HZ=1000, -O2, partizioni OTA, ...
├── .gitignore              # build/, sdkconfig, sdkconfig.local
└── main/
    ├── app_main.cpp        # boot, task (imu 200 Hz, balance 100 Hz), monitor
    ├── balance_pid.hpp     # PID puro, parità 1:1 con src/hardware/sim/leveling.py
    ├── balance_controller.*# comandi/fail-safe/state machine (ADR-009)
    ├── command_handler.*   # parser JSON dei comandi logici
    ├── Kconfig.projbuild   # tutte le costanti (pin, limiti, PID, rete)
    └── certs/              # mTLS (ca.crt, node7.crt, node7.key) - non committati
```

Condiviso: `firmware/common/` → `A4988Driver` (impulsi STEP/DIR + rampa),
`Mpu6050` + `Madgwick`, `WifiStation`, `MqttClient`, state machine.

## Procedimento di caricamento (flash) su ESP32-S3

Due strade equivalenti (stessi file di progetto, stesso `sdkconfig.local`):

- **A — VSCode + PlatformIO (consigliata)**: niente clone manuale di ESP-IDF,
  build/flash/monitor dai pulsanti di VSCode. V. §A subito sotto.
- **B — ESP-IDF classico (`idf.py`)**: prerequisiti e passi 0–6 sotto.

La boot log attesa (§4), il riflash (§5) e il troubleshooting (§6) sono
comuni a entrambe:

| Operazione | A: PlatformIO | B: idf.py |
|------------|---------------|-----------|
| build | `pio run` | `idf.py build` |
| flash | `pio run -t upload` | `idf.py -p PORT flash` |
| monitor | `pio device monitor` (uscita `Ctrl+]`) | `idf.py monitor` (uscita `Ctrl+]`) |
| menuconfig | `pio run -t menuconfig` | `idf.py menuconfig` |
| IDF usata | v5.5.x (scaricata da PlatformIO) | v5.2.2 (clone) |

Le due IDF diverse non sono un problema: il codice resta buildabile su
entrambe (CI = container `espressif/idf:v5.2.2`) — il vincolo è annotato in
`platformio.ini`.

### A. VSCode + PlatformIO

1. Installa l'estensione **PlatformIO IDE** da VSCode (o solo CLI:
   `pip install platformio` → comandi `pio`).
2. **File → Open Folder → `firmware/node7_balance`**: VSCode riconosce
   `platformio.ini`, genera l'IntelliSense e la status bar PIO espone
   **Build / Upload / Monitor**.
3. Crea `sdkconfig.local` (v. §WiFi sotto, rete **2.4 GHz**) **prima** del build.
4. Prima build: `pio run` nel terminale integrato (o pulsante **Build**).
   La prima volta scarica piattaforma + toolchain + ESP-IDF in `~/.platformio`
   (~1 GB, una tantum): niente clone manuale di `esp-idf`.
5. Flash: `pio run -t upload` (o pulsante **Upload**): la porta viene
   autodetect; se ce n'è più di una, decommenta `upload_port` in
   `platformio.ini`.
6. Monitor: `pio device monitor` (uscita `Ctrl+]`) oppure
   `pio run -t upload -t monitor` in un colpo solo.

VMOT può restare **spento**: la logica è alimentata dall'USB. Se il flash non
parte: tasto **BOOT** premuto durante l'upload (v. troubleshooting §6).

### B. ESP-IDF classico (idf.py)

#### 0. Prerequisiti (una tantum)

1. **ESP-IDF v5.2+** installato — su macOS/Linux:

   ```bash
   mkdir -p ~/esp && cd ~/esp
   git clone -b v5.2.2 --recursive https://github.com/espressif/esp-idf.git
   cd esp-idf && ./install.sh esp32s3      # scarica toolchain + driver seriali
   ```

2. **Cavo USB con dati** (non il cavo da sola ricarica) collegato al DevKit:
   al plug deve comparire un nuovo device seriale. Su macOS:

   ```bash
   ls /dev/cu.*
   # es. /dev/cu.usbmodem1101 (USB-JTAG nativo) o /dev/cu.usbserial-0001 (bridge CH340/CP210x)
   ```

   Se non compare: cavo da sola riccarica, manca il driver CH340/CP210x, oppure
   porta/scheda guasta.

#### 1. Attivare l'ambiente (ogni terminale nuovo)

```bash
. ~/esp/esp-idf/export.sh     # $IDF_PATH + idf.py + toolchain nel PATH
```

#### 2. Configurazione locale (mai committata)

Prima del build creare `firmware/node7_balance/sdkconfig.local` (già
gitignored; template: `cp sdkconfig.local.example sdkconfig.local`) con
WiFi/MQTT — v. sezione sotto. La rete deve essere **2.4 GHz**
(l'ESP32-S3 non vede le reti 5 GHz). Dopo ogni modifica eseguire
`idf.py reconfigure`.

#### 3. Build + flash

```bash
cd firmware/node7_balance
idf.py set-target esp32s3          # SOLO prima volta (o cambiando target)
idf.py build                       # ~1-2 minuti a caldo

idf.py -p /dev/cu.usbmodem1101 flash    # la porta va omessa se c'è un solo device
idf.py monitor                          # uscita: Ctrl+]
# oppure in un colpo solo:
idf.py -p /dev/cu.usbmodem1101 flash monitor
```

VMOT può restare **spento** durante il flash (la logica è alimentata dall'USB).

#### 4. Cosa aspettarsi al primo boot (monitor)

```
OpenJ5 Node 7 - Balance Controller
Firmware 1.0.0, built ...
mpu6050: WHO_AM_I=0x68 OK
jsteps/deg=35.556 | limits +/- 1244 jsteps (+/- 35.0 deg) | pid kp=15.00 ...
wifi: got IP: 192.168.x.x
mqtt: starting ...  /  mqtt: connected
node7: state=ready mode=disabled pitch=0.00 deg pos=0 jsteps heap=...
```

Checklist: `WHO_AM_I=0x68` ✅ (IMU), `got IP` ✅ (WiFi), `connected` ✅ (broker),
`state=ready` ✅ (stato ADR-009), `mode=disabled` ✅ (bobine **non** eccitate al
boot), `pos=0` ✅. Se `state=error` con `fault_reason="imu pitch stale"` → IMU
non risponde (cablato/AD0).

#### 5. Riflash e pulizie

| Situazione | Comando |
|------------|---------|
| Aggiornamento firmware | `idf.py build flash monitor` (niente `set-target`) |
| Cambiato `sdkconfig.local` | `idf.py reconfigure` poi `build flash` |
| Rete MQTT/WiFi "impazzite" o NVS corrotto | `idf.py erase-flash` poi ripartire da set-target |
| Modificate le `sdkconfig.defaults`/Kconfig | cancellare `sdkconfig` e rifare `idf.py build` |
| `idf.py build` fallisce in strano modo | `idf.py fullclean && idf.py build` |

#### 6. Troubleshooting flash

| Sintomo | Causa / rimedio |
|---------|-----------------|
| Nessun `/dev/cu.*` nuovo al plug | cavo solo-riccarica → cavo dati; oppure driver CH340/CP210x mancanti |
| `Failed to connect to ESP32-S3: No serial data received` | tieni premuto il tasto **BOOT** mentre parte il flash (entro ~1s), poi rilascia |
| Doppia porta seriale | usa quella **USB/UART (JTAG)** del DevKit; seleziona con `-p` |
| `A fatal error occurred: Failed to write to device` | porta occupata da un altro monitor → chiudilo; cavo corto/buonguardo |
| Brownout/boot-loop in USB | alimentazione insufficiente: cavo corto/buona porta USB o hub alimentato |
| WiFi non collega | rete 5 GHz? SSID/pass errati in `sdkconfig.local` → `reconfigure` + `erase-flash` |

### WiFi e MQTT locale (mai committati)

Le credenziali non stanno nel repo: crea `sdkconfig.local` (già gitignored)
**prima del build** copiando l'esempio (v. procedura §2, passo 2):

```bash
cp sdkconfig.local.example sdkconfig.local
```

Con l'hotspot del RPi (consigliato: `scripts/deploy/setup_hotspot.sh`, v.
`DEPLOYMENT.md` §11) SSID e pass sono quelli dell'AP e l'host broker resta
`openj5-core` (risolto dal dnsmasq del Pi):

```ini
CONFIG_OPENJ5_WIFI_SSID="openj5"
CONFIG_OPENJ5_WIFI_PASSWORD="la-passphrase-dell-hotspot"
# bench con broker plain (listener locale): disattiva TLS e usa l'host giusto
# CONFIG_OPENJ5_MQTT_HOST="192.168.1.10"
# CONFIG_OPENJ5_MQTT_PORT=1884
```

### Produzione: mTLS (ADR-013)

Il broker in ascolto su **8883 esige TLS1.3 + certificato client**. Genera i
certificati (una sola volta) **prima del build**:

```bash
cd firmware/node1_robot_core/docker/certs && ./generate.sh   # include node7
cp ca.crt node7.crt node7.key ../../../node7_balance/main/certs/
```

poi in `sdkconfig.local`: `CONFIG_OPENJ5_MQTT_TLS=y` (il build fallisce con
messaggio esplicito se i cert mancano).

## Comandi (topic `openj5/v1/balance/cmd`)

| Payload | Effetto |
|---------|---------|
| `{"command":"level","target_pitch_deg":0}` | loop chiuso su IMU: corpo vs gravità |
| `{"command":"tilt","angle_deg":5,"speed":0.5}` | posizione **giunto** aperta (trapezio), ±35°, speed 0.05–1.0 |
| `{"command":"stow"}` | giunto a 0 (parcheggio) |
| `{"command":"stop"}` | brake + hold (priorità, ignora la coda) |

Anche `openj5/v1/system/emergency_stop` (payload qualsiasi) ferma il nodo.

Ack su `.../evt`, stato retained su `.../state` (`boot|init|ready|running|
error|recovery|shutdown`), telemetria 1 Hz su `.../telemetry`.

## Fail-safe (ADR-017)

- bobine **non eccitate al boot** (`enabled_on_boot = n`);
- **deadman IMU 250 ms**: pitch stale → brake + evento `fault`;
- **watchdog loop 1000 ms**: stall → brake + fault; monitor reboot dopo 5×;
- **limite meccanico ±35° (±1244 jsteps)**: comandi fuori range rifiutati,
  overrun oltre +0,5° → fault;
- ogni comando motion esplicito ripristina da `error` (verifica fresh pitch).

## Test

```bash
scripts/test/host_firmware.sh   # logica pura (36 check): rampa, Madgwick, PID, FSM
```

La build reale è verificata in CI (`firmware-node7-build`, container ESP-IDF).
