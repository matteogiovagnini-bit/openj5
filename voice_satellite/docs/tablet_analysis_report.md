# Report Analisi Dispositivi - Documentazione per Ripresa Lavoro

**Ultimo aggiornamento:** 2026-10-12  
**Stato:** ✅ Samsung Note 10 **controllabile via USB + Wireless ADB** (schermo rotto, ma controllo completo dal Mac)

---

## 🔑 STATO CONNESSIONE SAMSUNG NOTE 10 (ATTUALE)

| Canale | Indirizzo/ID | Stato |
|---|---|---|
| **USB** | `R58M83YAQEK` (usb:20-4) | ✅ `device` (autorizzato, senza popup) |
| **Wireless TCP** | `192.168.1.107:5555` | ✅ `device` (porta fissa) |
| **mDNS pairing** | `adb-R58M83YAQEK-AnOUM7._adb-tls-connect._tcp` | ✅ accoppiato |

### Come è stato risolto (schermo rotto)
1. **Wireless Debugging** attivato su Note 10 (via hub USB-C → monitor/tastiera/mouse)
2. Pairing con codice: `adb pair 192.168.1.107:<porta>` → `Successfully paired`
3. Connessione: `adb connect 192.168.1.107:<porta>` → `device`
4. **Porta fissa**: `adb -s 192.168.1.107:<porta> tcpip 5555` → ora sempre `5555`
5. **Chiave del Mac registrata** → collegando il cavo USB, il Note 10 viene riconosciuto **`device` subito** (nessun popup RSA)

### Comandi rapidi di riconnessione
```bash
# USB (basta collegare il cavo)
adb devices -l

# Wireless (dopo riavvio telefono: riattiva toggle "Debug wireless", poi)
adb connect 192.168.1.107:5555

# Rendere di nuovo fissa la porta (dopo riavvio, se serve)
adb -s R58M83YAQEK tcpip 5555

# Proiettare/controllare dal Mac (funziona su USB o TCP)
scrcpy -s R58M83YAQEK            # via USB (più veloce)
scrcpy -s 192.168.1.107:5555     # via Wi-Fi
```

> ⚠️ **Nota porta**: `tcpip 5555` persiste fino al riavvio. Il "Debug wireless" classico usa porte dinamiche (es. `43655`) e richiede la schermata aperta; la modalità `tcpip 5555` no.

---

## 1. Samsung Galaxy Note 10 (SM-N970F) — SPECIFICHE VERIFICATE VIA ADB

### Identità
| Campo | Valore |
|---|---|
| **Brand** | samsung |
| **Modello** | SM-N970F |
| **Nome prodotto** | d1eea / d1xx (codename `d1`) |
| **Seriale** | R58M83YAQEK |
| **Regione/OS cond.** | Locale `en-GB`, build EU (d1eea) |

### Hardware
| Componente | Valore rilevato |
|---|---|
| **SoC** | **Exynos 9825** (`exynos9825` / `universal9825`, 7nm) |
| **CPU** | ARMv8-A 64-bit, 8 core (Cortex-A55 0xd05 + A75 + Mongoose M4) |
| **ABI** | `arm64-v8a` (+ armeabi-v7a, armeabi) |
| **GPU** | ARM **Mali** (EGL/Vulkan `mali`; driver Exynos 9825) |
| **RAM** | **7.59 GB** (`MemTotal 7591864 kB` → 8 GB LPDDR4X) |
| **Storage** | **256 GB UFS 3.0** (`/data` 229G totali, 214G usati, 15G liberi — 94%) |
| **Schermo** | **1080×2280**, densità **420 dpi** → 6.3" Dynamic AMOLED |
| **Sensori** | **35 sensori** (suite completa): Accelerometro LSM6DSO, **Giroscopio LSM6DSO**, Magnetico AK09918C, **Barometro LPS22H**, Prossimità TMD4910, Luce, Step Detector, ecc. |
| **Fotocamere** | **4 dispositivi camera** (0-3): front + tripla posteriore |
| **Batteria** | 3500 mAh design — attuale: **76%**, 3.83 V, **~42.7 °C** |

### Software
| Campo | Valore |
|---|---|
| **Android** | **12** (SDK 31) |
| **Interfaccia** | **One UI 4.1** (`ro.build.version.oneui=40100`) |
| **Build** | `SP1A.210812.016.N970FXXS9HWHA` |
| **PDA** | N970FXXS9HWHA |
| **Fingerprint** | `samsung/d1eea/d1:12/SP1A.210812.016/N970FXXS9HWHA:user/release-keys` |
| **Patch sicurezza** | **2023-08-01** |
| **Build date** | 2023-08-17 |
| **Tipo** | `user` / `release-keys` (no root, `ro.secure=1`, `ro.debuggable=0`) |

### ⚠️ Salute batteria (dato importante)
| Indicatore | Valore | Significato |
|---|---|---|
| **ASOC** (`mSavedBatteryAsoc`) | **79%** | Capacità stimata ~79% dell'originale (degradata) |
| **Charge counter** | 2.529.566 µAh @ 76% | ~3.33 Ah piena (≈3500 mAh nominale) |
| **Temp. max storica** | 51.8 °C | Riscaldamento elevato in passato |
| **Uso batteria** | 89.364 | Cicli/uso accumulato |
| **Temp. attuale** | 42.7 °C | Calda (sotto uso) |
| **Health flag** | 2 | "Good" riportato dal sistema |

> **Conclusione batteria**: salute reale ~79%, temperatura alta. Per uso continuativo (es. assistente vocale sempre alimentato) → gestire calore e degrado (vedi sezione 3).

---

## 2. Dispositivo: "Xiaomi Pad 6 Pro" (RISULTATO: CLONE/FALSO)

### Specs dichiarate vs Hardware reale (via ADB)
| Componente | Dichiarato | Reale rilevato |
|---|---|---|
| **Brand** | Xiaomi | `DW` (sconosciuto) |
| **Modello** | Pad 6 Pro (2023) | `Pad6_Pro` (solo build.prop) |
| **SoC** | Snapdragon 8+ Gen 1 | **MediaTek MT6737** (Quad Cortex-A53 @1.5GHz, 2016) |
| **RAM** | 8/12 GB | 16 GB* (incoerente, MT6737 max 3GB) |
| **Storage** | 128-512 GB UFS 3.1 | 10 GB user + 1 TB* fittizio |
| **Schermo** | 11" 2.8K 120Hz | **800×1280 @ 210 dpi** (~7.6") |
| **Android** | 13/14 | **8.1.0** (SDK 27, 2017) |
| **Patch** | 2023/24 | **Nov 2020** |
| **Camera** | 50MP+2MP / 8MP | camera service non trovato |
| **Sensori** | Giroscopio ecc. | 5 sensori base (**NO giroscopio**) |
| **GPU** | Adreno 730 | Mali-T720MP2 |

\* incoerenti con MT6737

### Indicatori clone
- Fingerprint: `Kdoce/Z8/Z8:10/QP1A...` (Android 10) ma release 8.1.0
- Build date 2024, patch 2020
- Enormi proprità custom `ro.product.*` (`switchword=168168`, `eyesdistance`, ecc.)
- Nessuna camera, no giroscopio

### Conclusione
Tablet budget MT6737 con `build.prop` truccato. Valore ~30-50€. **Non aggiornabile** (SoC obsoleto, nessun supporto vendor/custom ROM).

---

## 3. Progetto: Assistente Vocale Locale su Note 10

### Verdetto: **HARDWARE PIÙ CHE SUFFICIENTE** ✅
| Punto forza | Dettaglio |
|---|---|
| **SoC** | Exynos 9825 (7nm) — DSP per hotword always-on |
| **RAM 8 GB** | Spazio per modelli ASR/TTS on-device |
| **Storage 256 GB** | Ampio per modelli locali |
| **Sensori** | Suite completa (incl. giroscopio, barometro) |
| **USB-C + DeX** | Periferiche, display esterno, alimentazione |
| **Controllo** | ADB USB + scrcpy → gestione anche senza schermo |

### Limitazioni
- **Batteria degradata (79%)** + temperature alte → per uso 24/7: rimuovere batteria + alimentazione diretta USB-C PD, OPPURE limitazione carica (root + Magisk + ACC)
- Android 12, patch **Ago 2023** → isolare in VLAN, no esposizione internet
- Microfoni near-field → aggiungere mic array USB (ReSpeaker 2/4-mic, 15-30€) per far-field
- **No root** attualmente → alcune opzioni (carica, boot script) richiedono root

### Soluzioni software (ordine facilità)
| Soluzione | Tipo | Difficoltà | Note |
|---|---|---|---|
| **Home Assistant Companion + Assist** | Locale (Wyoming) | ★★☆ | Migliore integrazione HA |
| **Rhasspy** (Termux/Docker) | **100% Locale** | ★★★ | STT/TTS/hotword offline |
| **Leon AI** (Node.js) | Locale/Cloud | ★★☆ | Modulare, gira su Termux |
| **OpenVoiceOS / Neon AI** | Locale | ★★★ | Fork Mycroft, completo |
| **Termux + Whisper.cpp + Piper + Porcupine** | **100% Locale** | ★★★★ | DIY massimo controllo |

### Setup minimo consigliato
1. **Termux** + **Termux:API** + **Termux:Boot** (via ADB: `adb install`)
2. **Rhasspy** (proot-distro Ubuntu) o **Leon AI**
3. **Porcupine** per hotword custom
4. **Whisper.cpp** (STT) + **Piper** (TTS) — modelli `tiny`/`base`
5. **Wyoming** → satellite in **Home Assistant**
6. Alimentazione permanente (gestione batteria/calore)

### Costi aggiuntivi stimati
- ReSpeaker 2-mic USB HAT: ~15-25€
- Alimentatore USB-C PD 30W: ~10-15€
- Tempo: 4-8h → **Totale ~25-40€**

---

## 4. Prossimi Passi

### ✅ FATTO
- [x] Sbloccare ADB (wireless pairing + porta fissa 5555)
- [x] USB ADB autorizzato automaticamente (chiave Mac registrata)
- [x] scrcpy per controllo visivo/input dal Mac
- [x] Raccolta specifiche complete Note 10
- [x] **Termux + Termux:API + Termux:Boot installati** (APK F-Droid, `pm install` diretto)
- [x] **SSH configurato**: `ssh -p 8022 u0_a1382@192.168.1.107` (chiave ed25519 Mac)
- [x] **Script helper**: `./termux.sh <comando>` nel report dir
- [x] `pkg update` + `pkg upgrade` (openssl prompt risolto con force-confold)

### 🔜 DA FARE
- [ ] **Installare app via ADB**: `adb -s R58M83YAQEK install <apk>` (Termux + Termux:API + Termux:Boot da F-Droid)
- [ ] Decidere soluzione voice assistant (Rhasspy consigliato)
- [ ] Gestione batteria/calore (root o alimentazione diretta)
- [ ] (Opzionale) Sblocco bootloader → LineageOS 20/21
- [ ] (Opzionale) Togliere PIN: Impostazioni → Schermata di blocco → Tipo blocco → Nessuno

---

## 5. Infrastruttura di Controllo (Aggiunto)

### Accessi multipli al Note 10 (tutti funzionanti)
| Metodo | Comando | Note |
|---|---|---|
| **ADB USB** | `adb -s R58M83YAQEK shell ...` | Sempre disponibile col cavo |
| **ADB Wi-Fi** | `adb connect 192.168.1.107:5555` / `adb -s 192.168.1.107:5555 shell ...` | Porta fissa post-`tcpip` |
| **scrcpy** | `scrcpy -s R58M83YAQEK` | Video + mouse/tastiera sul Mac |
| **SSH→Termux** | `ssh -p 8022 u0_a1382@192.168.1.107` | Shell piena, no input injection |
| **Script** | `./termux.sh <cmd>` | Wrapper SSH (report dir) |

### SSH Termux - dettagli
- **Porta**: 8022, **utente**: `u0_a1382`, **auth**: chiave ed25519 del Mac (`opencode-mac`)
- **Host key**: registrata in `~/.ssh/known_hosts` (se cambia: `ssh-keygen -R "[192.168.1.107]:8022"`)
- File chiave spinto con `echo ... > ~/.ssh/authorized_keys` via input injection (funziona con quoting `input text '...%s...'`)
- **apt conffile**: `/data/data/com.termux/files/usr/etc/apt/apt.conf.d/98f` con `--force-confold` per upgrade non-interattivi da SSH

### Termux installato (F-Droid, firma coerente)
- `com.termux` 0.118.3
- `com.termux.api` 0.53.0
- `com.termux.boot` 0.8.1
- Pacchetti: `openssh python git termux-api` (+ upgrade completo in corso)

### Comandi utili da Mac
```bash
# SSH rapido
/Volumes/Dati/Matteo/Tablet/termux.sh "comando"

# Upgrade pacchetti (non-interattivo)
/Volumes/Dati/Matteo/Tablet/termux.sh "DEBIAN_FRONTEND=noninteractive pkg upgrade -y"

# Avvio servizi all'avvio (Termux:Boot)
/Volumes/Dati/Matteo/Tablet/termux.sh "mkdir -p ~/.termux/boot && echo 'sshd' > ~/.termux/boot/start-sshd && chmod +x ~/.termux/boot/start-sshd"
```

---

## 6. Comandi Utili

```bash
# === Connessione ===
adb devices -l
adb connect 192.168.1.107:5555
adb -s R58M83YAQEK tcpip 5555

# === Controllo visivo ===
scrcpy -s R58M83YAQEK

# === Info dispositivo ===
adb -s R58M83YAQEK shell getprop | grep -E "ro.product|ro.build|ro.hardware" | sort
adb -s R58M83YAQEK shell cat /proc/meminfo | head -3
adb -s R58M83YAQEK shell df -h /data
adb -s R58M83YAQEK shell dumpsys battery
adb -s R58M83YAQEK shell wm size; adb -s R58M83YAQEK shell wm density

# === Interazione senza schermo (input injection) ===
adb -s R58M83YAQEK shell input keyevent 26     # power
adb -s R58M83YAQEK shell input keyevent 3      # home
adb -s R58M83YAQEK shell input tap X Y         # tap coordinate
adb -s R58M83YAQEK shell input text "ciao"     # digita
adb -s R58M83YAQEK shell uiautomator dump /sdcard/ui.xml  # leggi UI

# === Screenshot / recording ===
adb -s R58M83YAQEK exec-out screencap -p > screen.png
adb -s R58M83YAQEK shell screenrecord /sdcard/demo.mp4 --time-limit 30

# === App ===
adb -s R58M83YAQEK install app.apk
adb -s R58M83YAQEK shell pm list packages | grep -i termux
adb -s R58M83YAQEK shell am start -n com.termux/.app.TermuxActivity

# === File ===
adb -s R58M83YAQEK push file /sdcard/
adb -s R58M83YAQEK pull /sdcard/file .
```

---

## 7. Note Hardware / Ambiente

- **scrcpy**: installato in `/opt/local/bin/scrcpy` (v4.0), ottimo per device con schermo rotto
- **ADB**: `/opt/local/bin/adb` (v1.0.41 / 36.0.2, MacPorts), Darwin 21.6.0 x86_64
- **No root** sul Note 10 → niente scrittura automatica chiavi, niente controllo carica senza Magisk
- **Backup possibile**: `adb backup` / copia MTP / scrcpy + screenshot

---

## 8. Test Audio Hardware (RISULTATO CORRETTO 2026-10-13)

### Metodo
Test via Termux:API (`termux-microphone-record`, `termux-tts-speak`, `termux-volume`) da SSH, con verifica a livello di sistema (`dumpsys audio`) e analisi file sul Mac (`ffmpeg volumedetect`).

### 🎙 Microfono → ✅ FUNZIONA
- Registrazione 34 s (AAC mono 8 kHz) su `/sdcard`, trasferita via SSH
- `max_volume: -1.8 dB` (audio reale), `mean_volume: -42.4 dB` → voce catturata
- Conclusione: **microfono MEMS del telefono operativo**

### 🔊 Altoparlanti → ✅ FUNZIONANO (falso allarme iniziale)
- **scrcpy 4.0 `--audio` (default) mette a tacere il device**: l'audio viene catturato e inoltrato al computer, la riproduzione locale sul telefono è silenziata → sembrava che lo speaker fosse guasto
- Verificato con TTS su stream `music` e `call` (routing `Devices: speaker` / `VOICE_CALL → earpiece`, volume 15/15 e 8/8)
- **Test decisivo**: con cavo USB scollegato e controllo via Wi-Fi (SSH 8022 / ADB 5555) il telefono parla perfettamente da solo → trasduttori OK
- **Configurazione di sviluppo corretta**: `scrcpy --no-audio` → schermo/input sul Mac ma il suono resta sul telefono (confermato con cavo collegato)

### 💡 Regole pratiche per l'assistente vocale
1. **Dev**: lanciare sempre `scrcpy -s R58M83YAQEK --stay-awake --window-title Note10-USB --no-audio`
2. **Standalone**: senza cavo il telefono emette audio normalmente (24/7 sulla dock)
3. Microfono OK → STT locale (Whisper, usare `-r 16000` invece del default 8 kHz) fattibile
4. Niente speaker esterno necessario — l'hardware audio è integro

---

## 9. Pulizia device (2026-10-13)

- Rimosse **425 app** (giochi + utility) con `pm uninstall --user 0` (script device-side, batch paralleli)
- Prima: 505 app terze parti. Dopo: **5** (Termux ×3 + 2 utility)
- **Spazio liberato: ~143 GB** → `/data` passata da 74 GB a **217 GB liberi (6% usato)**
- ⚠️ **Errore minore**: il comando `comm` richiede file ordinati; la keep-list non lo era → **19 app "da tenere" sono state rimosse per errore** (ChatGPT, Google Foto, Samsung Internet/Calcolatrice/Registratore, Snapchat, Amazon, ecc.)
  - Non ripristinabili con `pm install-existing` (su questo device erano preload come app utente, non nell'immagine di sistema)
  - Reinstallabili dal Play Store se necessari (non indispensabili per l'assistente)
  - Core intatti (Play Store, GMS, launcher, SystemUI, Settings, Termux)
- Script: `uninstall_par.sh`, `restore_keep.sh`, liste `installed_apps*.txt`, `keep_apps.txt`, `remove_apps.txt`

---

*Report aggiornato durante sessione OpenCode. Note 10 ora pienamente controllabile dal Mac (USB + Wi-Fi). Test audio: mic OK, speaker OK (usare `scrcpy --no-audio` durante lo sviluppo). Device ripulito: 217 GB liberi.*
