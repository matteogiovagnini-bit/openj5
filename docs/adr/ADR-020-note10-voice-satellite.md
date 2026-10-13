# ADR-020: Note 10 Voice Satellite as the OpenJ5 Voice Interface (Home Assistant + Wyoming + Companion Assistant)

## Status
Accepted (2026-10-13)

## Context

OpenJ5's roadmap (v0.5.0 "Vision & Interaction") calls for a **Speech Plugin**
(TTS/STT, voice commands) and basic conversation, and the SDK already exposes a
`SpeechAPI` plus `ISpeechPlugin`/`WakeWordPlugin`/`WhisperSttPlugin`/`PiperTtsPlugin`
contracts (ADR-006, ADR-007). What the project did **not** have was the physical,
always-on **voice front-end**: Node 1 (Raspberry Pi 4) has no microphone/speaker in
the reference build and, per ADR-019, the Pi is "brain only".

Building a bespoke Android wake-word app from scratch was rejected early: it is a
high-maintenance, high-risk component (audio focus, battery, Android API churn) for
a problem the Home Assistant ecosystem already solves end-to-end with an official
app and on-device wake word.

Available hardware: a **Samsung Galaxy Note 10 (SM-N970F)** with a **broken screen**,
8 GB RAM, Android 12/API 31, already repurposed as an always-on, headless
ADB/SSH-controlled device (217 GB free). It is the natural candidate for an
external voice terminal.

Constraints that shaped the decision:
- **Local-first / privacy**: STT and TTS must run locally; only the (future) LLM may
  be cloud.
- **Italian**: commands and spoken replies in Italian.
- The device must not become a *robot node*; it stays an **external accessory**
  (ADR-019 keeps the node fleet on ESP32-S3).
- Robot actuation must flow through the project's existing transport
  (ADR-015 MQTT / REST), not through a bespoke voice path.

## Decision

Use the Note 10 as an **external voice satellite** for OpenJ5, built from proven,
off-the-shelf components — no custom Android app:

1. **Host runtime on the phone.** Termux + `proot-distro` running an OCI
   `python:3.14-slim` container ("ha", Debian 13, Python ≥ 3.14.2) hosting
   **Home Assistant Core** (2026.10.1) in `/opt/ha`.
2. **Local speech engines** (Wyoming protocol, inside the same container):
   - **STT**: `wyoming-faster-whisper` — model `small`, language `it`, TCP 10300.
   - **TTS**: `wyoming-piper` — voice `it_IT-serena-medium`, TCP 10200.
3. **Voice satellite**: the official **Home Assistant Companion** Android app
   (2026.8.4), configured as the device's **default Android assistant**, with the
   **on-device microWakeWord "Okay Nabu"** enabled. No audio leaves the device for
   wake-word detection.
4. **Pipeline**: a single Assist pipeline **"Assistente Locale"**
   (`01m4tje8tnx44erdd0v45fqtm1`) → wake word → STT (Whisper) → intent → TTS
   (Piper) → phone speaker.
5. **Robot interface (future, T-034)**: HA acts as the bridge. Voice intents are
   translated to **MQTT logical commands** (`openj5/v1/...`, ADR-006/ADR-015) toward
   Node 1 → nodes. The voice layer never actuates directly.

The satellite is **not a node**; it is documented as an accessory and its entire
implementation, scripts and assets live in [`voice_satellite/`](../../voice_satellite/).

## Alternatives Considered

- **Custom Android app with embedded wake word / STT (Vosk, Porcupine, openWakeWord).**
  Rejected: large surface (audio focus, permissions, battery, API churn), duplicates
  what HA Companion already ships, and would need dedicated maintenance for years.
- **Commercial/closed wake word service** (e.g. cloud assistants). Rejected: violates
  local-first privacy constraint.
- **Home Assistant Voice Preview Edition / dedicated satellite hardware.** Rejected:
  extra cost, not needed — the Note 10 is already available and always-on.
- **Run Home Assistant on Node 1 (Raspberry Pi 4).** Rejected: ADR-019 makes the Pi
  "brain only" running the robot stack (Docker Compose, broker, DB); co-locating an
  HA instance there would couple the voice layer to the robot runtime and its
  failure modes. The phone is a cleaner, isolated terminal.
- **Wake word in Italian on-device.** Not available with the current HA Companion /
  microWakeWord model set; deferred (documented limitation), STT/TTS stay Italian.

## Consequences

Easier:
- A complete, local Italian voice loop is operational today with **zero custom code**:
  wake word → STT → intent → TTS, verified end-to-end (foreground and background).
- Clean separation: the voice front-end is decoupled from the robot core and reaches
  it only through MQTT/REST, so the robot can evolve (ADR-019) without touching voice.
- Reuses the SDK's existing Speech plugin contracts (ADR-007): the satellite is the
  concrete consumer that validates `SpeechAPI`.

Harder / risks:
- **Device is a single point of failure** and a battery/thermal concern: needs a wall
  charger ≥5 V/2 A; battery health ≈ 79 % and slow discharge on weak USB were observed.
- **Wake word is English-only** ("Okay Nabu"); commands/responses remain Italian.
- **Maintenance burden**: a proot container on Android is non-trivial to reproduce and
  harden (autostart, watchdog, backups — see T-036).
- **Custom patch required**: `faster-whisper` needs a manual patch for PyAV 19
  (`metadata_errors` removed); an upgrade may silently break STT (documented in
  `docs/KNOWLEDGE_BASE.md` §6).
- Fragile device state: `am force-stop` of the Companion app resets the default
  assistant to Google and disables the wake word.

## Implementation Notes

- Everything is provisioned through **ADB (USB/TCP) and SSH (Termux:8022)**; the
  broken screen means the UI is driven with `uiautomator dump` + `input tap/text`
  and visually via `scrcpy`. Full log in `voice_satellite/docs/`.
- The native settings screen (`SettingsActivity`) is **not exported**; the Assist
  toggle is reached from the companion web settings → *App complementare* → scroll
  to the **Assist** category → *Assist per Android* (see architecture doc §5).
- Battery whitelist applied via
  `dumpsys deviceidle whitelist +io.homeassistant.companion.android` (and `+com.termux`).
- Deployment of the satellite is documented and reproducible:
  `voice_satellite/README.md` §7 and `voice_satellite/docs/voice_assistant_architecture.md` Fases 0–5.
- Follow-up work captured as tasks: **T-034** (voice → MQTT robot command contract),
  **T-035** (cloud LLM conversation engine), **T-036** (hardening/autostart/watchdog),
  **T-037** (Empathy/session persistence & wake-word language options).

## Related ADRs
- ADR-006: Robot SDK Facade (`SpeechAPI` is the contract this satellite consumes)
- ADR-007: Plugin Architecture (`ISpeechPlugin`/`WakeWordPlugin`/`WhisperSttPlugin`/`PiperTtsPlugin`)
- ADR-015: MQTT as Primary Transport Protocol (voice → HA → MQTT → nodes)
- ADR-019: All Nodes on ESP32-S3, Pi Brain Only (motivates an *external* satellite)
- ADR-014: Python for Robot Core, C++ for Firmware (Wyoming/HA stack language)
