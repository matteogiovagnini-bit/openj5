# Architettura — Assistente Vocale Locale su Samsung Note 10

> Documento di progetto. Decisioni, stack, flussi, roadmap e rischi.
> Contesto: Note 10 (SM-N970F) headless con schermo rotto, riutilizzato come assistente vocale + hub domotico.

---

## 1. Decisioni di progetto (dal questionario)

| Dimensione | Scelta |
|---|---|
| **Obiettivo** | Domotica (controllo casa) **+** conversazione generale |
| **Host Home Assistant** | **Sul Note 10 stesso** (Home Assistant Core in container proot Linux dentro Termux) |
| **Ruolo AI** | **Ibrido** — il telefono è il "satellite" vocale (wake word + microfono + speaker); il "server" (HA + STT + TTS) gira sul telefono in proot |
| **Privacy** | **Tutto locale** (wake word, STT, TTS, intents), **tranne l'LLM** per la conversazione (cloud: OpenAI/Anthropic/Gemini) |
| **Controllo/gestione** | SSH (porta 8022), ADB (USB + Wi-Fi 5555), scrcpy `--no-audio` |

> ⚠️ **Nota importante sull'"ibrido"**: avendo scelto di mettere HA *sul Note 10*, il "server" coincide fisicamente col telefono. Quindi, in questa configurazione, **tutto il pipeline vocale gira sul device** (in due ambienti: Android/Termux + proot Ubuntu). Il termine "ibrido" resta valido come *architettura logica* (client satellite ↔ host HA), e consente in futuro di spostare STT/TTS/HA su un server dedicato **senza cambiare l'impianto**.

---

## 2. Vincoli hardware e ambiente

| Voce | Valore |
|---|---|
| SoC | Exynos 9825 (8 core, NPU) |
| RAM | 8 GB |
| Storage | 246 GB totali — **74 GB liberi (68% usato)** ✅ ampio margine |
| OS | Android 12 / One UI 4.1, patch 2023-08-01 |
| Root | ❌ No (`ro.secure=1`, `ro.debuggable=0`) |
| Schermo | ❌ Rotto → gestione headless via ADB/SSH/scrcpy |
| Microfono | ✅ Funziona (test plenty: max −1.8 dB) |
| Speaker | ✅ Funziona (usare scrcpy `--no-audio` in sviluppo) |
| Batteria | Salute ~79%, picco termico storico 51.8°C → attenzione 24/7 |
| Rete | Wi-Fi 192.168.1.107 (DHCP), IP utile da fissare |

---

## 3. Diagramma architetturale (logico)

```
                         ┌───────────────────────────  SAMSUNG NOTE 10  ───────────────────────────┐
                         │                                                                          │
   👤 voce utente        │   ┌── Android / Termux (host) ──────────┐   ┌── proot Ubuntu ────────┐  │
      ───────────────►   │   │  termux-wake-lock (keep-alive)      │   │  Home Assistant Core   │  │
                         │   │  termux-api (mic / speaker / TTS)   │   │   ├─ Assist (intents)  │  │
                         │   │  W A K E   W O R D  engine          │◄──┤   ├─ wyoming STT       │  │
                         │   │   (openWakeWord / Porcupine)        │   │   ├─ wyoming TTS       │  │
                         │   │  Satellite / bridge  ◄──────────────┼──►│   └─ integrazioni      │  │
                         │   │  sshd · Termux:Boot (autostart)     │   │       domotiche        │  │
                         │   └─────────────────────────────────────┘   └───────────┬────────────┘  │
                         │                                                          │               │
                         └──────────────────────────────────────────────────────────┼───────────────┘
                                                                                     │
                    ┌────────────────────────────────────────────────────────────────┼──────────────┐
                    │                                                                 ▼              │
                    │   DISPOSITIVI DOMOTICI                        LLM CLOUD (solo conversazione)  │
                    │   luci · prese · tapparelle · clima          OpenAI / Anthropic / Gemini      │
                    │   (Zigbee/Wi-Fi: Hue, Shelly, Tuya, …)       (unico dato che esce di casa)    │
                    └────────────────────────────────────────────────────────────────────────────────┘
```

### Flusso di una richiesta vocale (sequenza)

```
1. Utente dice la wake word        →  "Ehi Casa"
2. Wake word engine (Termux)       →  rileva → attiva ascolto
3. Registrazione comando (mic)     →  clip audio (16 kHz, opus/wav)
4. STT (wyoming-faster-whisper)    →  testo ("accendi la luce del salotto")
5. HA Assist (intenti)             →  ▸ se domotica   → esegue (luce ON) → testo risposta
                                      ▸ se generico   → LLM cloud → testo risposta
6. TTS (wyoming-piper, voce IT)    →  audio
7. Riproduzione (speaker telefono) →  risposta vocale
```

Obiettivo di latenza percepita: wake word < 1 s; trascrizione+intent < 2-3 s; TTS < 1 s (modello `small` su Exynos 9825).

---

## 4. Stack software (componenti)

| Funzione | Tecnologia scelta | Dove gira | Note |
|---|---|---|---|
| Runtime base | **Termux** (+ Termux:API, Termux:Boot) | Android | già installato e funzionante ✅ |
| Linux container | **proot-distro** (Ubuntu/Debian ≥ Python 3.13) | Android | HA Core richiede Python 3.13 |
| Hub domotico | **Home Assistant Core** (pip/venv) | proot | Assist = motore intenti |
| Wake word | **microWakeWord** (app HA Companion, on-device) | Android | modello `Okay Nabu`; rilevamento 100% locale ✅ |
| STT | **faster-whisper** (add-on Wyoming) | proot | modello `small` IT, tmp `medium` |
| TTS | **Piper** (add-on Wyoming) | proot | voci italiane; fallback `termux-tts-speak` |
| Intenti/NLU | **HA Assist** + `intents` | proot | italiano supportato |
| Conversazione | **OpenAI/Anthropic Conversation** (HA) | cloud | unico traffico esterno |
| Bridge audio | **termux-api** + script ponte | Android | mic ↔ HA, HA → speaker |
| Accesso/gestione | SSH 8022 · ADB · scrcpy `--no-audio` | Mac | già operativo ✅ |
| Autostart | **Termux:Boot** script | Android | `~/.termux/boot/` |
| Keep-alive | `termux-wake-lock` | Android | evita il kill del satellite |

---

## 5. Il nodo critico: il "satellite vocale" su Android

Android 10+ **limita l'accesso al microfono in background**. Questo è il punto più delicato del progetto. Opzioni a confronto:

| Opz. | Approccio | Pro | Contro |
|---|---|---|---|
| **A** | Termux in foreground + loop `termux-microphone-record` (clip corte) + openWakeWord | nessuna app custom; tutto in Termux | latenza, consumo, Mic in background a rischio |
| **B** | App Android dedicata wake-word (custom o esistente) come foreground service | robusto, hotword sempre attiva | serve compilare/installare un APK (install via `pm` già padroneggiato) |
| **C** | App **Home Assistant Companion** + Assist | ufficiale, integrato | **nessuna hotword always-on** (push-to-talk / scorciatoia) |
| **D** | Implementare un **Wyoming satellite** nativo Android | standard HA | sviluppo app significativo |

**Raccomandazione (implementata)**: l'**opzione C** è risultata vincente. L'app ufficiale **Home Assistant Companion** (≥2026.2) include un **wake word on-device** (microWakeWord) attivo come `VoiceInteractionService` Android, quindi **non serve** l'opzione B (app custom). Vedi **Fase 5** nel log per i dettagli completi. L'opzione A resta un fallback; la D (satellite Wyoming nativo) è superflua in questa configurazione.

---

## 6. Gestione 24/7 (alimentazione, calore, affidabilità)

- **Alimentazione**: hub/dock USB-C o caricatore dedicato. Batteria 79% + uso continuo = calore → valutare **presa smart** con orari o (con root futuro) charge-limit.
- **Termico**: il picco storico 51.8°C è da monitorare; il STT on-device scalda. Mitigazioni: modello STT `small`, throttling, posizione ventilata, evitare di incassare il telefono.
- **Autostart**: script in `~/.termux/boot/` (sshd già presente) → aggiungere wake-lock + satellite.
- **Watchdog**: script cron/loop che riavvia HA e il satellite se non rispondono; log su file.
- **IP statico**: riservare DHCP per 192.168.1.107 (o IP fisso) per SSH/ADB stabili.
- **Backup**: snapshot della config HA (`/data/.../files/home/...`) su Mac periodicamente.

---

## 7. Roadmap a fasi

| Fase | Obiettivo | Stato |
|---|---|---|
| **0** | Pulizia device | ✅ fatto — 425 app rimosse, 217 GB liberi | 
| **1** | Linux nel proot | ✅ fatto — container `ha` = `python:3.14-slim` |
| **2** | Home Assistant Core | ✅ fatto — HA 2026.10.1 su `http://192.168.1.107:8123` |
| **3** | Voce locale | ✅ fatto — faster-whisper (STT) + Piper IT (TTS) via Wyoming |
| **4** | Pipeline Assist | ✅ fatto — pipeline "Assistente Locale" predefinita, testata |
| **5** | Satellite vocale | ✅ fatto — HA Companion + wake word "Okay Nabu" on-device, test end-to-end |
| **6** | Conversazione | ⏳ prossimo — LLM cloud via HA (OpenAI/Anthropic) |
| **7** | Domotica | ⏳ integrazione dispositivi + intenti IT |
| **8** | Hardening | ⏳ autostart (Termux:Boot), watchdog, alimentazione/termico, backup |

---

## 8. Alternative e fallback

- **HA su Mac** (container/VM) o **Raspberry Pi 5 / mini PC** → sposta STT/TTS/HA fuori dal telefono (più robusto, latenze migliori); il Note 10 resta satellite puro. Consigliato se il device fatica o scalda troppo.
- **LLM locale** (se in futuro si vuole privacy totale): `llama.cpp` con modello ~3B quantizzato — fattibile sulla RAM ma lento su Exynos; oppure su un server.
- **Speaker esterno/BT**: non necessario (speaker interno sano), ma utile se il telefono viene incassato.

---

## 9. Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---|---|---|
| Mic in background bloccato da Android | hotword non affidabile | foreground service (opz. B) / wake-lock |
| Proot fragile agli aggiornamenti | HA si rompe | backup config, pin versioni, documentare |
| Calore/degrado batteria 24/7 | affidabilità hw | alimentazione controllata, ventilazione, monitor |
| Storage ridotto dopo modelli | HA/Whisper non ci stanno | già 74 GB liberi; modelli `small` |
| Python < 3.13 nella distro proot | HA non parte | scegliere distro con 3.13 (trixie/25.04/Arch ARM) |
| Volume giochi/latenza su Exynos | UX scarsa | STT `small`, pre-roll, streaming risposta |

---

## 10. Prossimo passo immediato

Stato attuale: **assistente vocale completo e funzionante** sul Note 10 (Fasi 0-5 ✅).

1. **Ricarica/alimentazione**: il device è al **13%** (in carica USB) — tenerlo alimentato h24 prima dei test prolungati.
2. **Fase 6 — Conversazione (LLM cloud)**: aggiungere un'integrazione OpenAI/Anthropic in HA e creare un **agente conversazionale** che usi le entità di casa come strumenti, mantenendo la pipeline locale per la domotica.
3. **Fase 7 — Domotica**: aggiungere i dispositivi reali (Zigbee/Wi-Fi) e definire gli intenti in italiano.
4. **Fase 8 — Hardening**: autostart (Termux:Boot), watchdog, IP statico, monitor termico, backup config.
5. **Robot**: condividere la documentazione del robot per definire il **contratto comandi** (MQTT/REST, vedi §12).

> ⚠️ **Nota batteria/termico**: il wake word always-on consuma molta batteria e scalda. Per un uso 24/7 valutare alimentazione continua + ventilazione, e monitorare la temperatura (limite storico 51.8°C).

---

## 12. Controllo del robot (rover + umanoide — ESP32-S3 + Raspberry Pi)

> Il robot è in fase di progettazione da parte dell'utente; documentazione di dettaglio da condividere. Questa è la proposta di integrazione.

### Ruolo dei componenti
| Componente | Ruolo | Note |
|---|---|---|
| **Raspberry Pi** (a bordo robot) | "cervello" alto livello: server comandi, navigazione, eventuale ROS 2, API REST/WebSocket o MQTT | Wi-Fi, raggiungibile in rete |
| **ESP32-S3** | basso livello: motori, servo, sensori, IMU | collegato al Pi via UART/USB o Wi-Fi |
| **Note 10** | assistente vocale: wake word + STT + TTS + HA → **invia comandi al Pi** | host HA (proot) |

### Flusso di un comando vocale verso il robot
```
voce → STT → HA Assist (intent) → azione → [ponte] → Raspberry Pi → ESP32-S3 → attuatori
```
Ponte possibili (in ordine di preferenza):
- **A) MQTT** (consigliato): HA pubblica su topic `robot/cmd` → Pi/ESP32 sottoscrivono. Broker Mosquitto (sul Pi o nel container del Note 10).
- **B) REST**: HA `rest_command` → API HTTP sul Pi del robot.
- **C) ROS 2**: `rosbridge`/`ros2-web-bridge` sul Pi; HA invia comandi/Obiettivi.

### Dove far girare il broker MQTT
- **Consigliato**: Mosquitto **sul Raspberry Pi del robot** (vicino ai dispositivi, sempre acceso col robot). HA (sul Note 10) si collega come client.
- Alternativa: Mosquitto nel **container HA** (`apt install mosquitto`).

### Linguaggio naturale → comandi
- Intent HA dedicati: "vai avanti", "fermati", "gira a sinistra", "alza il braccio", "saluta" → `intent_script` → pubblica comando MQTT / chiama API.
- Per comandi liberi: **LLM con function calling** (cloud) che traduce la frase in chiamate strutturate (es. `move(linear, angular)`, `arm(joint, angle)`) → pubblica su MQTT.
- `intent_script` + servizi custom restano il metodo più affidabile per i comandi critici.

### Sicurezza / fail-safe
- Stop di emergenza indipendente (hardware) + comando "stop" prioritario
- Watchdog sul robot (se non arrivano comandi/heartbeat → stop)
- Limiti di velocità/coppia; autenticazione MQTT (user/pass) e TLS in LAN
- Nessun comando distruttivo senza conferma

### Note
- Trattandosi di un progetto **DIY in corso**, definiremo insieme l'interfaccia comandi (contratto MQTT/REST) quando condividi la documentazione del robot.
- Il robot potrà essere esposto in HA come `device` con entità (battery, sensors, stato) + servizi per i movimenti → così Assist può sia **leggere stato** che **comandare**.

---

### Fase 2 — Home Assistant Core ✅ (2026-10-13)
- Container `ha` = `python:3.14-slim` (Debian 13, Python 3.14.8)
- Venv in `/opt/ha`; `pip install homeassistant` → **HA 2026.10.1** installato
- Config dir: `/config` (nel container)
- Avvio: `proot-distro login ha -- /bin/bash -lc 'mkdir -p /config && exec /opt/ha/bin/hass --config /config'`
- **HA online** su `http://192.168.1.107:8123` (porta 8123 in ascolto, redirect a `/onboarding.html`)
- Log runtime: `~/ha_run.log` (attenzione: HA logga poco su stdout; usare UI/`/config/home-assistant.log`)
- ⚠️ Avvio manuale via `nohup`: la persistenza a reboot verrà gestita in Fase 7 (Termux:Boot + supervisor)

---

### Fase 3 — Motori voce locali (STT/TTS) 🔄 (2026-10-13)
- Venv dedicati nel container `ha`:
  - `/opt/whisper` → `wyoming-faster-whisper` (STT) — ✅ installato
  - `/opt/piper` → `wyoming-piper` (TTS) — ✅ installato
- **TTS Piper** avviato e funzionante:
  - Voce italiana **`it_IT-serena-medium`** scaricata in `/opt/piper/data` (63 MB)
  - Comando: `/opt/piper/bin/wyoming-piper --voice it_IT-serena-medium --data-dir /opt/piper/data --uri tcp://0.0.0.0:10200`
  - Porta **10200** in ascolto; protocollo Wyoming 1.10.2; voce annunciata ✅
- **STT Whisper** in avvio:
  - Comando: `/opt/whisper/bin/wyoming-faster-whisper --model small --language it --data-dir /opt/whisper/data --uri tcp://0.0.0.0:10300`
  - Porta **10300**; scarica modello `Systran/faster-whisper-small` (~460 MB)
- ⚠️ Nota onnxruntime: warning su GPU discovery (`/sys/bus/pci/devices` permessi) → irrilevante, usa CPU
- Voci Piper italiane disponibili: `paola` (medium), `riccardo` (x_low), `serena` (medium/high)
- **Da fare in HA**: aggiungere integrazioni **Wyoming Protocol** (piper 127.0.0.1:10200, whisper 127.0.0.1:10300) e configurare Assist (Pipeline) con lingua `it`
- 🐛 **Bug risolto (importante)**: `faster-whisper 1.2.1` usava `av.open(..., metadata_errors="ignore")`, parametro **rimosso in PyAV 19** → errore `TypeError`. Patch applicata a `/opt/whisper/lib/python3.14/site-packages/faster_whisper/audio.py` (rimosso il parametro; backup `.bak`). Script: `patch_whisper.sh`
  - ⚠️ La patch va riapplicata se si reinstalla/aggiorna `faster-whisper`
- ✅ **Test end-to-end superato**:
  - Piper → *"Ciao, questa è una prova del sistema di riconoscimento vocale."* (22050 Hz)
  - Whisper → trascrizione **corretta** della stessa frase
  - Script di test: `stt_test.py`, `tts_test.py`; campione: `piper_serena_it.wav`
- ⚠️ La registrazione microfono `mic_test.m4a` risultava troppo debole (media −42 dB) → trascrizione vuota; con audio pulito funziona

---

### Fase 4 — Integrazione HA + Pipeline Assist ✅ (2026-10-13)
- **Token**: creato un *long-lived access token* dall'UI di HA (usato per API REST + WebSocket)
- **Integrazioni Wyoming aggiunte via config flow API** (`POST /api/config/config_entries/flow`):
  - 🐛 **Bug risolto**: il pacchetto Python `wyoming` **non era installato** nel venv di HA e l'auto-install di HA in proot falliva silenziosamente → risposta HTTP vuota ("Empty reply from server")
    - Fix: `/opt/ha/bin/pip install wyoming==1.10.2` + riavvio HA
  - `piper` (TTS) → `tcp://127.0.0.1:10200` → `entry_id 01M4TJ9VRZ45AXND4VJRX1JK1X`, stato **loaded** → entità **`tts.piper`**
  - `faster-whisper` (STT) → `tcp://127.0.0.1:10300` → `entry_id 01M4TJ9W4Y245DYS1F47H5ZBJP`, stato **loaded** → entità **`stt.faster_whisper`**
- **Pipeline Assist "Assistente Locale"** creata via WebSocket API (`assist_pipeline/pipeline/create`) e impostata **predefinita**:
  - `language: it` · `conversation_engine: conversation.home_assistant` (`it`)
  - `stt_engine: stt.faster_whisper` (`it`) · `tts_engine: tts.piper` (`it_IT`) · `tts_voice: it_IT-serena-medium`
  - `pipeline id: 01m4tje8tnx44erdd0v45fqtm1`
  - 🐛 **Bug risolto**: il TTS wyoming espone le lingue **esattamente** come annunciate dal servizio (`it_IT`), **senza normalizzazione** a `it`; il codice HA è in `/opt/ha/lib/python3.14/site-packages/homeassistant/components/wyoming/tts.py` (`_rebuild_voices` → `_attr_supported_languages = sorted(voice_languages)`). → Impostare **`tts_language: it_IT`** (non `it`), altrimenti errore `tts-not-supported`
  - ⚠️ Nota protocollo: `assist_pipeline/run` è una **subscription** → il primo messaggio è solo l'*ack* `{"type":"result","success":true,"result":null}`; gli **eventi** (`run-start`, `stt-end`, `intent-end`, `tts-start`, `tts-end`, `run-end`) arrivano dopo, **senza** chiudere la connessione
- **✅ Test 1 — testo→intento→TTS**: `"che ore sono"` → `"Sono le 14:09"` → Piper genera mp3 (`/api/tts_proxy/...mp3`)
- **✅ Test 2 — audio→STT→intento→TTS (pipeline completa)**:
  - Input: audio Piper di *"che ore sono"* → ffmpeg → PCM 16 kHz mono s16le (`query.raw`, 28608 byte)
  - Flusso binario WS: run con `input:{type:audio,sample_rate:16000}` → `stt_binary_handler_id` dall'evento `run-start` → frame `bytes([handler_id])+pcm` → chiusura con `bytes([handler_id])`
  - Risultato: `stt-end → "che ore sono."` · `intent-end → "Sono le 14:11"` · `tts-start → tts.piper it_IT` ✅
- **Script di supporto** (nel container, venv `/opt/ha`, che ora ha `wyoming` + `aiohttp`):
  - `ws_inspect.py`, `ws_engines.py`, `ws_create_pipeline.py`, `ws_update_pipeline.py`, `ws_run.py`, `ws_run_audio.py`
- **Stato HA**: `http://192.168.1.107:8123` · posizione "Casa" · lingua `it` · country IT · TZ Europe/Rome
- **Prossimo**: Fase 4b — satellite vocale sul Note 10 (wake word + mic + speaker); Fase 6 — LLM cloud

---

### Fase 5 — Satellite vocale: App HA Companion + wake word on-device ✅ (2026-10-13)

> **Scelta implementata: Opzione C evoluta.** L'app ufficiale **Home Assistant Companion** (≥2026.2) implementa un **wake word on-device** (microWakeWord, modelli TFLite `.tflite`) come servizio di assistenza vocale Android. Questo elimina la necessità di scrivere un'app custom (opzione B) e mantiene la privacy (rilevamento **completamente locale**, nessuna rete). Il modello di default è **"Okay Nabu"**.

#### 5.1 Installazione app Companion
- APK scaricato: `apks/app-full-release.apk` → **versione 2026.8.4-full** (`versionCode=24228`, `targetSdk=37`)
- Installazione: `adb install -r -g apks/app-full-release.apk` → **`-g`** concede tutti i permessi runtime (incl. `RECORD_AUDIO`)
- Onboarding: server `http://192.168.1.107:8123` → nome server **"Casa"** → login utente `admin`
- Nome dispositivo: **`Note10-Satellite`**
- Posizione: **non condivisa**; livello sicurezza connessione: **"Meno sicuro"** (HTTP in LAN)
- App in plancia ("Benvenuto/a Admin")

#### 5.2 Accesso alle impostazioni native (`SettingsActivity`)
`SettingsActivity` **non è esportata** → non avviabile con `adb am start`. Non esiste un deep link dedicato. **Percorso individuato**:
1. Plancia → barra laterale (drawer nativo) → **"Impostazioni"** → impostazioni **web** HA
2. In fondo alla pagina web, voce **"App complementare"** (`Sensori, widget, notifiche e altro ancora`) → **apre la `SettingsActivity` nativa** (titolo **"App complementare"**)
3. Nella schermata nativa, la categoria **"Assist"** si trova **molto in basso** (dopo *Server e dispositivi*, *Sensori*, *Altre impostazioni*, *Notifiche*): **attenzione a non saltarla** — uno scroll troppo aggressivo la oltrepassa
4. Categoria **Assist** → **"Assist per Android"** → schermata con:
   - **Assistente predefinito** (stato + pulsante *"Imposta come predefinito"*)
   - **Parola di attivazione** (Sperimentale) → switch **"Abilita il rilevamento della parola di attivazione"** → **"Okay Nabu"** + pulsante *"Testa parola di attivazione"*

#### 5.3 Impostazione come assistente predefinito Android
- Tap su **"Imposta come predefinito"** → apre le impostazioni di sistema **"App assistenza dispositivo"** → tap sulla riga dell'app corrente → dialog con *Nessuna / Bixby Voice / Finder / Google / **Home Assistant*** → selezionare **Home Assistant** → dialog di conferma (l'assistente potrà leggere info sullo schermo) → **OK**
- La schermata mostra quindi **"Home Assistant è il tuo assistente predefinito"** ✅
- Stato di sistema verificato: `App assistenza dispositivo: Home Assistant`

#### 5.4 Abilitazione wake word
- Switch **"Abilita il rilevamento della parola di attivazione"** → **ON** (`checked=true`, persistente)
- Modello: **`Okay Nabu`** (`wakeword/okay_nabu.tflite`)
- Log di attivazione del servizio: `MicroWakeWordEngine: Engine initialized: stride=3, inputScale=0.101961, inputZeroPoint=-128, arena=65536 bytes`
- Servizio Android: **`io.homeassistant.companion.android/.assist.service.AssistVoiceInteractionService`** (bound dal sistema perché HA è l'assistente predefinito)

#### 5.5 Permesso esecuzione in background (fondamentale)
L'app avvisava *"Home Assistant non ha il permesso di funzionare in background"*. Risolto via ADB con la whitelist di ottimizzazione batteria:
```
adb shell dumpsys deviceidle whitelist +io.homeassistant.companion.android
adb shell dumpsys deviceidle whitelist +com.termux   # anche per l'host HA/proot
```
Dopo l'operazione la schermata Companion mostra **"Home Assistant ha accesso all'esecuzione in background."** ✅
Con la whitelist e HA come assistente predefinito, il wake word funziona **anche con l'app in background / schermo su home**.

> ⚠️ **Non usare `am force-stop io.homeassistant.companion.android`**: il force-stop dell'app assistente predefinita fa **fallback** dell'assistente di sistema (a Google) e **disattiva lo switch wake word** + ferma il servizio. Per riattivare: reimpostare HA come assistente predefinito (5.3) e riabilitare lo switch (5.4).

#### 5.6 Test end-to-end (senza parlare: audio iniettato via speaker)
Poiché non è possibile parlare al telefono, il test è stato fatto **riproducendo l'audio dallo speaker interno**, captato dal microfono:
1. **Wake word**: generata con **Piper voce inglese** (`en_US-lessac-medium`, scaricata in `/opt/piper/data`):
   `echo "Okay Nabu" | /opt/piper/bin/piper -m /opt/piper/data/en_US-lessac-medium.onnx -f /root/okay_nabu.wav`
2. **Comando IT**: `echo "che ore sono" | piper -m .../it_IT-serena-medium.onnx -f /root/cmd_ore.wav`
3. **Trasferimento**: `./termux.sh "cat <rootfs>/root/okay_nabu.wav" > file` → `adb push` in **`/sdcard/Download/`**
4. **Riproduzione**: `termux-media-player play /sdcard/Download/okay_nabu.wav` (poi `cmd_ore.wav`)
5. Volume media alzato: `adb shell cmd media_session volume --stream 3 --set 15`

**Risultati (logcat):**
- `MicroWakeWordEngine: Wake word detected` → `AssistViewModelBase: Setting up recorder`
- `assist_pipeline/run ... input={sample_rate=16000, wake_word_phrase=Okay Nabu} ... pipeline=01m4tje8tnx44erdd0v45fqtm1` ✅ (usa la **nostra pipeline** "Assistente Locale")
- STT riconosce **"che ore sono"** → `tts-start {"engine":"tts.piper","language":"it_IT","voice":"it_IT-serena-medium","tts_input":"Sono le 15:19"}` ✅
- Risposta riprodotta dallo speaker (`AudioUrlPlayer`, `USAGE_ASSISTANT`)

✅ **Ciclo completo verificato dal telefono, anche in background:** wake word on-device → STT locale → intent HA → TTS locale → risposta vocale.

#### 5.7 Gestione schermo e notifiche durante i test
- Gestione UI headless: `uiautomator dump` + parsing XML + `input tap/text` (il modello non vede immagini)
- `mCurrentFocus=null` può comparire con le finestre `VoiceInteractionSession` — usare `logcat` per la conferma reale
- Nota: `adb shell media volume ...` non esiste su questo device; usare **`cmd media_session volume --stream 3 --set 15`**

#### 5.8 File/asset prodotti in questa fase
| File | Contenuto |
|---|---|
| `apks/app-full-release.apk` | APK HA Companion 2026.8.4 (installato sul device) |
| `/opt/piper/data/en_US-lessac-medium.onnx(.json)` | voce Piper inglese (generazione wake word di test) |
| `$(container)/root/okay_nabu.wav` | campione "Okay Nabu" (Piper EN) |
| `$(container)/root/cmd_ore.wav` | campione comando "che ore sono" (Piper IT) |
| `/sdcard/Download/okay_nabu.wav`, `cmd_ore.wav` | copie sul device per la riproduzione |

> 📌 **Prossimo (Fase 6)**: aggiungere un **LLM cloud** (OpenAI/Anthropic) come `conversation_engine`/agente per la conversazione libera, mantenendo la pipeline locale per la domotica. Poi **Fase 7**: autostart (Termux:Boot), watchdog, alimentazione/termico.

---

## 11. Log di implementazione

### Fase 0 — Pulizia device ✅ (2026-10-13)
- Rimozione 425 app (giochi); `/data` da 74 GB → **217 GB liberi**
- Errore minore: 19 app non-gioco rimosse per un `comm` su lista non ordinata (reinstallabili da Play Store)
- Core intatti; Termux + SSH funzionanti

### Fase 1 — Linux in proot ✅ (2026-10-13)
- `proot-distro` 5.10.0 installato in Termux (nuova versione basata su **immagini OCI/Docker**)
- **Scoperta chiave**: HA 2026.10.1 richiede **Python ≥ 3.14.2**. Debian trixie ha 3.13.5 → **insufficiente**
  - Primo tentativo con `debian:trixie` → container `debian` (Python 3.13.5) — **scartato** per il vincolo Python
  - Soluzione: container **`ha`** creato dall'immagine ufficiale **`python:3.14-slim`** → Debian 13 + **Python 3.14.8** ✅
  - Comando: `proot-distro install -n ha python:3.14-slim`
- Note operative:
  - Il PATH del proot include `/data/data/com.termux/files/usr/bin` in coda → usare sempre `/usr/local/bin/python3` (container `ha`) o il venv
  - Immagini OCI: si può installare qualsiasi immagine Docker con `proot-distro install -n <nome> <image>:<tag>`
- Dipendenze di sistema nel container `ha`: bluez, libffi-dev, libssl-dev, libjpeg-dev, zlib1g-dev, autoconf, build-essential, libopenblas-dev, liblapack-dev, libsqlite3-dev, git, cmake, pkg-config, ffmpeg
- Comandi utili:
  - `proot-distro login ha` → shell nel container HA
  - `proot-distro login ha -- /bin/bash -lc '<cmd>'` → comando singolo
  - `proot-distro list` / `proot-distro remove <nome>`
