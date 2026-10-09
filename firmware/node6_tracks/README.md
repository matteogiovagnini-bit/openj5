# OpenJ5 Node 6 — Tracks Controller (ESP32-S3 + L298N + 2× DC gear motor)

Firmware del nodo 6 secondo **ADR-002 / ADR-019**: pilota i due motori dei
cingoli dell'L298N **dall'ESP32-S3** (il Raspberry Pi è solo cervello, non tocca
mai il PWM).

- Cablaggio pin e procedura di bench: **`docs/hardware/NODE6_ESP32_WIRING.md`** +
  **`docs/hardware/BENCH_TRACKS.md`** (T-022)
- Config sincronizzata a mano con `config/node6_tracks/node.json` ↔
  `main/Kconfig.projbuild`; il test di parità Node 6 è ancora da fare (**T-032**)
- Logica pura testata su host: `scripts/test/host_firmware.sh`
- Mappa pin approvata: ADR-019 §3

Questa fase (bring-up motori) implementa **solo motori + comandi MQTT +
watchdog/fail-safe**. Encoder, IMU, ToF, bumper, PID e odometria restano a
**T-022**: i pin sono già in config/Kconfig ma non ancora usati.

## Struttura

```
node6_tracks/
├── CMakeLists.txt          # progetto ESP-IDF (+ componente ../common)
├── platformio.ini          # VSCode + PlatformIO (board esp32-s3, IDF 5.5)
├── sdkconfig.defaults      # FREERTOS_HZ=1000, -O2, partizioni OTA, ...
├── sdkconfig.local.example # template WiFi/MQTT (credenziali mai committate)
├── .gitignore              # build/, sdkconfig, sdkconfig.local
└── main/
    ├── app_main.cpp        # boot, task control 50 Hz, monitor
    ├── track_controller.*  # comandi/fail-safe/state machine (ADR-009)
    ├── command_handler.*   # parser JSON dei comandi logici
    ├── Kconfig.projbuild   # tutte le costanti (pin, PWM, rampa, limiti, rete)
    └── certs/              # mTLS (ca.crt, node6.crt, node6.key) - non committati
```

Condiviso: `firmware/common/` → `L298NDriver` (`drivers/l298n_driver.cpp`,
LEDC PWM + rampa), `WifiStation`, `MqttClient`, state machine. La matematica
pura dei motori (`clamp_velocity`, `motor_levels`, `ramp_schedule`) è in
`firmware/common/include/hal/motor_logic.hpp`, specchio 1:1 di
`src/hardware/hal/motor.py` (ADR-018).

## Procedimento di caricamento (flash) su ESP32-S3

Come per il Node 7: due strade equivalenti (stessi file di progetto, stesso
`sdkconfig.local`).

- **A — VSCode + PlatformIO (consigliata)**: `pio run`, `pio run -t upload`,
  `pio device monitor`.
- **B — ESP-IDF classico**: `idf.py set-target esp32s3` (prima volta),
  `idf.py build`, `idf.py -p PORT flash monitor`.

Vincolo versioni: `platformio.ini` usa platform 6.12.x (= IDF v5.5.x), la CI
usa il container `espressif/idf:v5.2.2`: il codice deve restare buildabile su
entrambe (nessuna API esclusiva di una sola).

### Configurazione locale (mai committata)

```bash
cd firmware/node6_tracks && cp sdkconfig.local.example sdkconfig.local
```

WiFi/MQTT secondo il solito schema (hotspot del Pi oppure home WiFi, v.
`docs/deployment/DEPLOYMENT.md` §11/§12.1). Rete **2.4 GHz** obbligatoria.

### Produzione: mTLS (ADR-013)

```bash
cd firmware/node1_robot_core/docker/certs && ./generate.sh   # include node6
cp ca.crt node6.crt node6.key ../../../node6_tracks/main/certs/
```

poi `CONFIG_OPENJ5_MQTT_TLS=y` in `sdkconfig.local` (il build fallisce con
messaggio esplicito se i cert mancano). Il listener mTLS del broker è
TLS1.3-only: `CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y` (già nell'esempio).

## Comandi (topic `openj5/v1/tracks/cmd`)

| Payload | Effetto |
|---------|---------|
| `{"cmd":"forward","velocity":0.3}` | entrambi i motori avanti |
| `{"cmd":"backward","velocity":0.3}` | entrambi i motori indietro |
| `{"cmd":"spin_left","velocity":0.3}` | sinistro indietro, destro avanti |
| `{"cmd":"spin_right","velocity":0.3}` | sinistro avanti, destro indietro |
| `{"cmd":"stop"}` | **short-brake** immediato (priorità, ignora la coda) |

`velocity` è normalizzata in `[-1, +1]` (default `default_velocity` = 0.3,
clampata ai limiti config). È accettato anche il campo `"command"` come alias.

Anche `openj5/v1/system/emergency_stop` (payload qualsiasi) ferma il nodo.

Ack su `.../evt`, stato retained su `.../state`
(`boot|init|ready|running|error|recovery|shutdown`), telemetria 1 Hz su
`.../telemetry` (`left`, `right`, `mode`, `velocity`, `faulted`, `link`).

## Fail-safe

- motori **rilasciati al boot** (pin direzione bassi, PWM 0): nessun movimento
  finché non arriva un comando;
- **watchdog comando 1000 ms**: se i comandi si fermano mentre si marcia →
  short-brake + fault (un nuovo comando ripristina da `error`);
- **link MQTT perso** (`mqtt.connected() == false`) → short-brake + fault;
- **watchdog loop 1000 ms**: stall del task → brake + fault; monitor reboot
  dopo 5×;
- **E-stop di sistema** su `openj5/v1/system/emergency_stop`.

## Test

```bash
scripts/test/host_firmware.sh   # logica pura (rampa motori, stepper, Madgwick, PID, FSM) — 53 check
```

La build reale ESP-IDF **non è ancora in CI**: va eseguita localmente
(`pio run -e node6`, oppure `idf.py build`). La validazione on-device sul
banco è **T-033**.
