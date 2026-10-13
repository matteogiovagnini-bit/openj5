# voice_satellite — Satellite vocale OpenJ5 (Samsung Note 10)

> **Stato:** ✅ Operativo (Fase 5 completata, 2026-10-13)
> **Documento di riferimento:** [`docs/voice_assistant_architecture.md`](docs/voice_assistant_architecture.md)
> **Decisione architetturale:** [`../docs/adr/ADR-020-note10-voice-satellite.md`](../docs/adr/ADR-020-note10-voice-satellite.md)

Questo folder raccoglie **tutto** il lavoro di realizzazione del satellite vocale di
OpenJ5: un Samsung Galaxy Note 10 (SM-N970F, schermo rotto) trasformato in assistente
vocale locale in italiano e interfaccia verso il robot.

---

## 1. Cos'è

Il Note 10 non è un nodo del robot (ADR-019: i nodi sono ESP32-S3 e il Pi è solo
"cervello"). È un **accessorio/terminale vocale esterno** che parla con OpenJ5 via
Home Assistant → MQTT/REST.

Funzioni realizzate:

1. **Wake word on-device** ("Okay Nabu", microWakeWord, solo in inglese) tramite
   l'app ufficiale **Home Assistant Companion** impostata come assistente Android.
2. **STT locale** in italiano: `wyoming-faster-whisper` (modello `small`, `it`).
3. **TTS locale** in italiano: `wyoming-piper` (voce `it_IT-serena-medium`).
4. **Pipeline Assist "Assistente Locale"** su Home Assistant Core, eseguita sul
   telefono stesso (proot).
5. **Test end-to-end superato** (foreground e background): wake word → STT →
   intent → TTS riprodotto dallo speaker.

L'**LLM conversazionale (cloud)** e il **controllo reale del robot** sono fasi future
(vedi task T-034…T-037 in `../docs/NEXT_TASK.md`).

---

## 2. Architettura (logica)

```
                 ┌─────────────────────────── Galaxy Note 10 (Android 12) ───────────────────────────┐
                 │                                                                                    │
  🎤 ute/robot   │   HA Companion app                     Termux                                        │
   parla  ───────┼──▶ microWakeWord "Okay Nabu"           ┌──────────────────────────────────────────┐│
                 │        │ (on-device, EN)               │  proot-distro  →  container "ha"          ││
                 │        ▼                               │   (python:3.14-slim, Debian 13)           ││
                 │   Assist / AssistVoiceInteractionService│   ┌────────────────────────────────────┐ ││
                 │        │                               │   │ Home Assistant Core 2026.10.1      │ ││
                 │        ▼                               │   │  pipeline "Assistente Locale"      │ ││
                 │   intent → Assist pipeline ───TCP──────┼──▶│   ├─ STT → wyoming-faster-whisper  │ ││
                 │        ▲                               │   │   │        :10300 (small, it)      │ ││
                 │        │                               │   │   └─ TTS → wyoming-piper           │ ││
                 │   🔊 speaker ◀── audio TTS ◀───────────┼───┤            :10200 (it_IT-serena)  │ ││
                 │                                        │   └────────────────────────────────────┘ ││
                 └────────────────────────────────────────┴──────────────────────────────────────────┘
                                                          │
                              (futuro) HA → MQTT (ADR-015) ▼
                                              Node 1 (Raspberry Pi 4) → Node 6 cingoli / Node 3/4 braccia
```

### Flusso di una richiesta vocale

1. La wake word "Okay Nabu" viene rilevata **on-device** (nessun audio inviato fuori).
2. L'app inoltra la richiesta alla pipeline Assist **"Assistente Locale"** di HA
   (`assist_pipeline/run`, subscription WebSocket, `pipeline=01m4tje8tnx44erdd0v45fqtm1`).
3. HA chiama `faster-whisper` (Wyoming, TCP 10300) → testo in italiano.
4. HA interpreta l'intento (frase → intent; in futuro LLM cloud per conversazione).
5. HA chiama `piper` (Wyoming, TCP 10200) → audio WAV in italiano.
6. L'audio torna all'app e viene riprodotto dallo speaker del telefono.

---

## 3. Struttura del folder

| Percorso | Contenuto |
|----------|-----------|
| `docs/voice_assistant_architecture.md` | Architettura completa + log di implementazione Fasi 0–5, roadmap a fasi, sezione robot |
| `docs/tablet_analysis_report.md` | Analisi hardware Note 10 (specifiche, batteria, accessi ADB/SSH/scrcpy), pulizia app |
| `scripts/ws_*.py` | Client HA (WebSocket + REST): ispezione, creazione/aggiornamento pipeline, run testuale/audio |
| `scripts/stt_test.py`, `scripts/tts_test.py` | Client di test diretti dei servizi Wyoming |
| `scripts/patch_whisper.sh` | **Patch obbligatoria** a `faster-whisper` per PyAV 19 (vedi KNOWLEDGE_BASE §6) |
| `scripts/termux.sh` | Wrapper SSH verso Termux (`./termux.sh "<cmd>"`) |
| `scripts/restore_keep.sh`, `uninstall_games.sh`, `uninstall_par.sh` | Script di pulizia app (425 app rimosse) |
| `reports/installed_apps*.txt`, `keep_apps.txt`, `remove_apps.txt` | Elenchi app prima/dopo la pulizia |
| `reports/scrcpy.log` | Log sessione scrcpy |
| `assets/audio/*.wav|.m4a` | Campioni audio di test (TTS Piper, registrazioni mic, wake word, "che ore sono") |
| `assets/screenshots/note10_screen.png` | Screenshot del device |
| `assets/apks/` | APK usati (HA Companion, Termux, Termux:API, Termux:Boot) — **esclusi da git** (vedi `.gitignore`) |

---

## 4. Quick reference (comandi chiave)

```sh
# --- Accesso al device ---
/opt/local/bin/adb devices                        # USB R58M83YAQEK
/opt/local/bin/adb connect 192.168.1.107:5555     # TCP
./scripts/termux.sh "nproc"                       # SSH Termux (porta 8022)

# --- Container HA (proot) ---
proot-distro login ha -- /bin/bash -lc '<cmd>'

# --- Avvio servizi (dentro il container) ---
# Home Assistant
proot-distro login ha -- /bin/bash -lc 'mkdir -p /config && exec /opt/ha/bin/hass --config /config'
# STT (whisper)
/opt/whisper/bin/wyoming-faster-whisper --model small --language it --data-dir /opt/whisper/data --uri tcp://0.0.0.0:10300
# TTS (piper)
/opt/piper/bin/wyoming-piper --voice it_IT-serena-medium --data-dir /opt/piper/data --uri tcp://0.0.0.0:10200

# --- Client HA (con /opt/ha/bin/python) ---
/opt/ha/bin/python scripts/ws_inspect.py          # ispeziona entità/pipeline
/opt/ha/bin/python scripts/ws_run.py "che ore sono"   # test pipeline testuale
/opt/ha/bin/python scripts/ws_run_audio.py <file.wav> # test pipeline audio

# --- Test Wyoming diretti ---
/opt/ha/bin/python scripts/stt_test.py <file.wav>
/opt/ha/bin/python scripts/tts_test.py "ciao"

# --- Debug pipeline (logcat) ---
/opt/local/bin/adb logcat | grep -i assist_pipeline
```

> **Volume su Android** (non esiste `adb shell media volume`):
> `adb shell cmd media_session volume --stream 3 --set 15`

---

## 5. ⛔ Avvertenze critiche

- **NON usare `am force-stop io.homeassistant.companion.android`**: resetta
  l'assistente predefinito di Android a Google e spegne la wake word. Per ripristinare:
  reimpostare HA come assistente predefinito + riattivare lo switch wake word
  (procedura in `docs/voice_assistant_architecture.md` §5.5).
- **Alimentazione**: il device va tenuto su **caricatore a muro ≥5V/2A**. La salute
  batteria è al ~79% e con alimentazione USB debole è in lenta scarica (`-68 mA`).
  Rischio spegnimento → stop di HA e del satellite.
- **Wake word solo in inglese**: la parola di attivazione è "Okay Nabu"; comandi e
  risposte restano in italiano.
- La cartella `assets/apks/` è esclusa da git (binari pesanti ~155 MB); gli APK sono
  reinstallabili da F-Droid (Termux) e dalla release HA Companion.

---

## 6. Dove ho integrato le conoscenze nel progetto

| Documento OpenJ5 | Contenuto aggiunto |
|------------------|--------------------|
| `docs/adr/ADR-020-note10-voice-satellite.md` | Decisione architetturale del satellite vocale |
| `docs/adr/INDEX.md` | Riga ADR-020 |
| `docs/PROJECT_MEMORY.md` | Sezione 11 — satellite vocale |
| `docs/KNOWLEDGE_BASE.md` | Sezione 6 — problemi risolti (HA in proot, PyAV, wake word, …) |
| `docs/NEXT_TASK.md` | Task T-034…T-037 (LLM, comandi robot, hardening) |
| `PROJECT_STATUS.md` | Componente satellite vocale + conteggio ADR |
| `CHANGELOG.md` | Voce `Unreleased` → Added |
| `ROADMAP.md` | Nota a v0.5.0 (Speech Plugin) |

---

## 7. Riproduzione (sintesi)

Da zero su un Note 10 pulito:

1. **Termux** (F-Droid) + **Termux:API** + **Termux:Boot**; SSH con chiave.
2. `pkg install proot-distro` → `proot-distro install ha` con immagine `python:3.14-slim`.
3. Nel container: installare HA in `/opt/ha` (venv), `wyoming`, `wyoming-piper`
   (`/opt/piper`), `wyoming-faster-whisper` (`/opt/whisper`); applicare
   `scripts/patch_whisper.sh`.
4. HA: onboarding, aggiungere integrazioni Wyoming `piper` e `faster-whisper`,
   creare pipeline **"Assistente Locale"** (`tts_language: it_IT`).
5. **HA Companion** (APK) → login → impostare HA come **assistente predefinito** →
   attivare la **wake word**.
6. Whitelist batteria:
   `adb shell dumpsys deviceidle whitelist +io.homeassistant.companion.android`
   (e `+com.termux`).
7. Collaudo: `ws_run.py "che ore sono"` e test end-to-end a voce.

Dettagli completi in `docs/voice_assistant_architecture.md` (Fasi 0–5).
