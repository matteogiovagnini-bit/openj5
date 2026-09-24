# OpenJ5 Bench Bring-Up — Nodo 7 Balance (ESP32-S3 + A4988 + NEMA17 + MPU6050)

> Prototipo di banco del Nodo 7: NEMA17 sul giunto corpo/cingoli secondo **ADR-017**.
> Firmware: `firmware/node7_balance/` (+ `firmware/common/`) · Config: `config/node7_balance/node.json`
> Driver HAL Python (bench Pi): `src/hardware/drivers/a4988.py` · Ultimo aggiornamento: 2026-09-23

---

## 1. Materiale

| Componente | Note |
|------------|------|
| ESP32-S3 DevKitC-1 (o compatibile) | Nodo 7 dedicato, WiFi nativo |
| Modulo **A4988** (o DRV8825, pin-compatible) | Driver STEP/DIR con chopper a corrente |
| Motore **NEMA17** (200 step/ghi, ≥0.4 N·m col riduttore) | Albero → puleggia 20T |
| **MPU6050** breakout (GY-521) | IMU sul corpo, indirizzo 0x68 |
| Alimentatore **12 V ≥ 2 A** (o LiPo 3S 11,1–12,6 V) | **Solo motore** (VMOT: 8–35 V) |
| **Condensatore 100 µF elettrolitico** | Obbligatorio su VMOT/GND vicino all'A4988 |
| Cavetti dupont F-F ×~12 + cavi potenza | Segnali + alimentazione |
| Multimetro con scala DC V | Regolazione Vref (limitatore di corrente) |
| Cinghia dentata 20T→80T + mozzo (T-027) | Riduzione 1:4 — *meccanica da fare* |

---

## 2. Collegamenti

### 2.1 ESP32-S3 ↔ A4988 (segnali)

| A4988 | GPIO ESP32-S3 | Funzione | Note |
|-------|---------------|----------|------|
| STEP | **GPIO4** | Impulso = 1 microstep | `config/node7_balance/node.json` → `step_pin` |
| DIR | **GPIO5** | Livello = direzione | `dir_pin` |
| ENABLE | **GPIO6** | **Attivo basso**: LOW = bobine eccitate | `enable_pin`; HIGH = rilascio (free shaft) |
| VDD | 3V3 | Logica 3,3 V | A4988 accetta 3–5,5 V |
| GND | GND | ⚠️ **Massa comune obbligatoria** | Vedi §2.3 |

**Ponti sull'A4988 (segnali di configurazione, NON collegati all'ESP32):**

| Pin A4988 | Collegamento | Perché |
|-----------|--------------|--------|
| RESET ↔ SLEEP | Collegati insieme e portati a **3V3** | Con RESET basso l'A4988 **non emette impulsi** (errore classico: "hum ma non gira") |
| MS1, MS2, MS3 | Tutti a **3V3** (o jumper) | = **1/16 microstep** → coerente con `"microsteps": 16` |

### 2.2 A4988 ↔ NEMA17 (bobine)

| A4988 | NEMA17 |
|-------|--------|
| 1A | A1 (bobina A) |
| 1B | A2 |
| 2A | B1 (bobina B) |
| 2B | B2 |

- Invertire la rotazione: scambiare **A1↔A2** (o B1↔B2), oppure `"inverted": true` in config.
- ⚠️ **Collegare/scarroccare le bobine solo con VMOT spento**: l'A4988 si può danneggiare per scarica elettrostatica sugli output.

### 2.3 Alimentazione (potenza vs logica)

```
  ALIM 12V ≥2A ──┬── + ──── VMOT (A4988)
                 │            └──‖+‖─┐  100µF IL PIÙ VICINO POSSIBILE
                 │                   │  (polo − verso GND!)
  MASSA ─────────┴── GND ──┬── GND (A4988)
                           ├── GND (ESP32)     ← STESSA MASSA ⚠️
                           └── GND (alim)
  ESP32 3V3 ────────────── VDD (A4988) + MS1/2/3 + RESET/SLEEP
  ESP32 GPIO4/5/6 ──────── STEP / DIR / ENABLE
  USB PC ────────────────── solo logica ESP32 (bench: va bene con masse comuni)
```

- **Il NEMA17 NON si alimenta mai dal Pi/USB/3V3**: solo VMOT.
- Il condensatore **100 µF su VMOT è obbligatorio**: l'A4988 senza di esso va in under-voltage nei cambi di direzione e si rischia il danno (lo richiede il datasheet; le board non lo soldano).
- Soglie: VMOT 8–35 V; con LiPo 3S piena (12,6 V) si sta nei limiti (nessun regolatore 5 V a bordo da rimuovere, a differenza del L298N).

### 2.4 I2C ↔ MPU6050 (IMU sul corpo)

| MPU6050 (GY-521) | ESP32-S3 | Note |
|------------------|----------|------|
| VCC | 3V3 | GY-521 con VCC=3V3 → pull-up I2C a 3,3 V corretti |
| GND | GND | |
| SDA | **GPIO8** | `i2c sda` (Kconfig `OPENJ5_I2C_SDA`) |
| SCL | **GPIO9** | `i2c scl` (Kconfig `OPENJ5_I2C_SCL`) |
| AD0 | **GND** | Indirizzo **0x68 (104)** → `"address": 104` in config |
| XDA/XCL/INT | — | Non usati (INT opzionale futuro) |

**Montaggio IMU**: fisata sul **corpo** (non sui cingoli!), assi con **Z verso l'alto e Y trasversale** (sinistra→destra): il pitch (rotazione attorno a Y) è l'angolo corpo-vs-gravità usato dal PID. Il cavo va lasciato con scarico meccanico: ruota insieme al corpo.

### 2.5 Vincoli pin ESP32-S3 (scelti e verificati)

I pin 4/5/6/8/9 sono **sicuri**. Evitare sempre:

| GPIO | Motivo |
|------|--------|
| 19, 20 | USB D−/D+ nativo (JTAG/flash via USB) |
| 26–32 | SPI flash/PSRAM (su moduli con PSRAM ottale) |
| 43, 44 | UART0 TX/RX (console seriale) |
| 0, 3, 45, 46 | **Strapping pins** (boot/modo flash): livelli congelati a boot |

---

## 3. Corrente di fase: regolazione del Vref (A4988)

L'A4988 limita la corrente col potenziometro a bordo (**chopper**). Con i sense resistor standard **Rs = 0,1 Ω**:

```
I_peak(max) = Vref / (8 × Rs)  =  Vref / 0,8      →  Vref = I_peak × 0,8
I_RMS ≈ I_peak / √2
```

Per la config `"rms_current_ma": 550` → I_peak = 0,778 A → **Vref ≈ 0,62 V**.

**Procedura (VMOT acceso, bobine NON collegate):**
1. Multimetro in DC V: puntale nero su GND, rosso sul pin **Vref** (lato opposto del potenziometro, sulla maggior parte delle board blu/verdi — vedere incisione `GND` accanto al trimmer).
2. Girare il trimmer fino a **0,62 V ±0,05**.
3. Con Rs = 0,2 Ω (alcune board): raddoppiare (≈ 1,24 V) — **misurare Rs è più sicuro che assumere**.

Note:
- A 550 mA RMS il motore resta tiepido e con il riduttore 1:4 la coppia basta (×4 sull'albero giunto). Se in banco il motore si scalda o il loop oscilla per pochi passi persi: scendere a Vref 0,44 V (≈ 390 mA RMS) — da ritarare al primo moto reale (debito aperto in SESSION_REPORT 2026-09-21).
- **Ridurre I_SENSET** non corregge perdita di passi da accelerazione troppo alta: prima `max_acceleration_steps_s2` (800), poi corrente.

---

## 4. Numeri di movimento (matematica, verificata da test)

| Grandezza | Valore | Formula |
|-----------|--------|---------|
| Microstep/motore-giro | 3200 | 200 step × 16 µstep |
| **jstep/giro giunto** | **12800** | 3200 × riduzione 1:4 (20T→80T) |
| **jstep/° giunto** | **35,556** | 12800 / 360 |
| Corsa | **±35° → ±1244 jstep** | 35 × 35,556 (limite meccanico cinghia) |
| Velocità max | 1600 jstep/s ≈ 45 °/s | `max_speed_steps_s` |
| Accelerazione max | 800 jstep/s² ≈ 22,5 °/s² | `max_acceleration_steps_s2` |

⚠️ I limiti `min_steps/max_steps` sono **±1244** (corretto il 2026-09-23: in configs/docs compariva ±4445 che corrisponde a ±125° — v. KNOWLEDGE_BASE §1-sexies; il firmware rifiuta le posizioni oltre ±35°).

---

## 5. Checklist pre-test (safety first)

1. ✅ Giunto **libero di ruotare**: corpo non fissato, mani/lacci **lontani** da cinghia e pulegge (pinch points).
2. ✅ VMOT **spento** prima di toccare cablaggio bobine.
3. ✅ Vref regolato **prima** del primo comando di movimento.
4. ✅ `"enabled_on_boot": false` (già di default): il firmware **non** eccita le bobine al boot.
5. ✅ Primo test con `level` a traguardo piccolo (±5°) e corpo sollevato/leggero.
6. ✅ `stop` (→ brake + hold) sempre a portata di comando; mosquitto_pub/SDK aperto in un terminale.

---

## 6. Accensione e prova

```bash
# 1) Flash del firmware — procedura completa A (VSCode+PlatformIO,
#    consigliata) / B (idf.py): porta, boot log, riflash, troubleshooting:
#    firmware/node7_balance/README.md §"Procedimento di caricamento (flash)";
#    cert TLS opzionali ivi
cd firmware/node7_balance
idf.py set-target esp32s3 && idf.py build && idf.py -p <porta> flash monitor
# oppure: pio run -t upload -t monitor

# 2) Comandi logici via Robot SDK (consigliato, ADR-006) — da openj5-core:
python3 -c "from sdk.robot import Robot; r=Robot(); r.body.level(); r.body.tilt(5.0); r.body.stow(); r.body.stop()"

# 3) Oppure diretto su MQTT. Il broker in ascolto su 1883 è SOLO localhost:
#    in LAN serve 8883 + mTLS (cert da certs/generate.sh; usa il cert `api`
#    che ha readwrite su openj5/#, trattalo come segreto).
C=firmware/node1_robot_core/docker/certs
H=<ip-del-broker>
M="--cafile $C/ca.crt --cert $C/api.crt --key $C/api.key"
mosquitto_sub -h $H -p 8883 $M -t 'openj5/v1/balance/#' -v   # telemetria/stato
mosquitto_pub -h $H -p 8883 $M -t openj5/v1/balance/cmd -m '{"command": "level"}'
mosquitto_pub -h $H -p 8883 $M -t openj5/v1/balance/cmd -m '{"command": "tilt", "angle_deg": 5, "speed": 0.5}'
```

Topic (ADR-017): `openj5/v1/balance/{cmd,evt,telemetry,state}` — comandi `level`, `tilt <deg>`, `stow`, `stop`.

**Sequenza di primo bring-up consigliata:**
1. Solo logica (USB) → `idf.py monitor`: verificare log `mpu6050: WHO_AM_I=0x68 OK` e WiFi/MQTT connect.
2. VMOT spento → comando `stow`: sentire il "clic" di ENABLE (bobine eccitate), zero movimento atteso a vuoto.
3. Vref misurato (§3).
4. VMOT acceso, corpo sostenuto a mano → `tilt 5` → il **giunto** va a +5° in
   apertura trapezio (con cingoli a filo il corpo segue di ~+5°): verificare la
   posizione su telemetria `joint_deg`, poi `level` e guardare `body_pitch_deg`
   convergere sul target.
5. `level` con inclinazione imposta dei cingoli (sotto blocco) → il corpo si riallinea.

---

## 7. Troubleshooting

| Sintomo | Causa probabile | Rimedio |
|---------|-----------------|---------|
| Motore ronza ma non gira | RESET basso, o MS1-3 fluttuanti, o ENABLE alto | Ponti §2.1 (RESET+SLEEP a 3V3, MS×3 a 3V3) |
| Non parte nessun comando MQTT | Broker in produzione = 8883 **mTLS** (cert obbligatorio), 1883 solo localhost | Build con `OPENJ5_MQTT_TLS=y` + cert in `firmware/certs/node7/`, o test in locale col bridge |
| Rotazione invertita rispetto al segno | Coppia di bobine o verso DIR | Scambiare A1↔A2 oppure `"inverted": true` |
| Passi persi in accel | Accel/corrente troppo bassa (o corpo troppo pesante per la coppia) | Prima `max_acceleration_steps_s2`, poi Vref; verificare tensione VMOT sotto carico |
| ESP32 si riavvia al movimento | Massa comune mancante / alim motore dal USB | §2.3: masse comuni, potenza esterna |
| `mpu6050 not found` | AD0 non a GND, SDA/SCL scambiati, cavo lungo | §2.4; indirizzo atteso 0x68 |
| Pitch instabile/oscilla | Montaggio IMU sbagliato (assi) o deadband < rumore | Assi §2.4; `deadband_deg` ≥ 0,5 |
| Posizione "drifta" dopo ostacolo | Passi persi (open-loop) — atteso | Chiusura su IMU: il PID corregge; homing = `stow` (riferimento 0) |

---

## 8. Riferimenti

- **ADR-017** `docs/adr/ADR-017-node7-balance-controller.md` (decisione, architettura)
- Config: `config/node7_balance/node.json` (pin, limiti, PID) · `config/common/topics.json` (node7)
- Firmware: `firmware/node7_balance/` (progetto) · `firmware/common/` (HAL stepper, MPU6050, comms)
- Simulazione del loop: `src/hardware/sim/leveling.py` (parità 1:1 col PID C++)
- Bench RPi (NEMA17 via GPIO Pi, pre-firmware): `src/hardware/drivers/a4988.py` + `config/bench/balance.json`
- Guida collegata al Nodo 6 cingoli: `BENCH_TRACKS.md`
