# VISION

## OpenJ5: La Piattaforma Robotica Open Source per l'Era dell'AI Embodiment

### Visione a 10 Anni

OpenJ5 diventerà **la piattaforma di riferimento mondiale per la robotica embodiment open source** — una piattaforma dove ricercatori, maker, startup e aziende possono costruire, sperimentare e deployare robot umanoidi modulari senza reinventare l'architettura ogni volta.

### Cosa Rende OpenJ5 Unico

| Differenziatore | Descrizione |
|----------------|-------------|
| **Hardware 100% Parametrico** | Tutto il CAD è generato parametricamente in FreeCad. Cambi un parametro (es. altezza torso, lunghezza braccio) e rigeneri tutto: STL, BOM, URDF, cablaggi. |
| **Architettura a 6 Nodi Distribuiti** | Non un singolo SBC, ma 6 nodi specializzati (1× RPi4 + 5× ESP32) che comunicano via gateway astratto. Scalabile, resiliente, sostituibile nodo per nodo. |
| **Hardware Abstraction Layer Totale** | Zero dipendenze da PCA9685, L298N, ESP32, RPi4 nel codice applicativo. Solo interfacce: `IServoDriver`, `IMotorDriver`, `ICameraDriver`, `ICommunicationGateway`. |
| **Robot SDK ad Alto Livello** | `robot.head.lookAt(x,y,z)`, `robot.rightArm.grab()`, `robot.tracks.moveTo(x,y,theta)`. Mai più topic MQTT o angoli servo nel codice applicativo. |
| **Digital Twin Nativo** | Stesso SDK, stesse API → Robot Reale **O** Simulatore (Gazebo/Isaac Sim). Switch senza cambiare una riga di codice. |
| **Plugin Architecture Nativa** | Vision, Speech, AI, Navigation, Battery, Motion, Hardware, Communication = Plugin. Caricabili, sostituibili, versionabili. |
| **Configuration-Driven Everything** | Zero hardcoded values. Tutto in JSON/YAML/DB: servo limits, PID, PID, topic names, IP, pinout, calibrazioni. |
| **Event-Driven Architecture** | Event Bus centrale. `FaceDetected` → `BehaviorEngine` → `MotionPlanner` → `HeadController`. Zero coupling diretto. |
| **Digital Twin Nativo** | Stesso SDK controlla robot reale e simulatore. Stesso codice, stesso deploy. |
| **OTA & Fleet Ready** | Ogni ESP32 aggiornabile OTA. Fleet management ready per multi-robot. |

### Principi Guida (Non Negozabili)

1. **Longevità** — Il codice scritto oggi deve compilare e funzionare tra 5 anni senza rewrite architetturale.
2. **Sostituibilità** — Ogni componente (HW, FW, SW, Protocollo, Driver) deve essere sostituibile senza toccare il resto.
3. **Documentazione = Codice** — Funzionalità senza docs aggiornate = incompleta. Sempre.
4. **Configurazione > Codice** — Nessun numero magico, nessun hardcoded. Tutto configurabile.
5. **Testabilità** — Unit, Integration, Hardware, Simulation test per OGNI modulo. CI/CD obbligatorio.
6. **Open Source Vero** — MIT/Apache 2.0. Nessun vendor lock-in. Community first.

### Visione per Stakeholder

| Stakeholder | Valore OpenJ5 |
|-------------|---------------|
| **Maker/Hobbyist** | Robot Johnny 5 stampabile, documentato, estendibile. Impara robotica vera. |
| **Ricercatore** | Piattaforma embodiment per AI, HRI, manipulation. Focus su ricerca, non infrastruttura. |
| **Startup** | Time-to-market: usa OpenJ5 come base, customizza plugin/HW, vai in produzione. |
| **Università** | Piattaforma didattica completa: HW, FW, SW, AI, Control, HRI in un progetto. |
| **Azienda** | Prototipazione rapida, PoC embodiment, base per prodotti commerciali (con supporto pro). |

### Metriche di Successo (Anno 3)

- [ ] 100+ robot OpenJ5 costruiti globalmente (community map)
- [ ] 50+ plugin pubblicati su registry
- [ ] 10+ paper accademici che usano OpenJ5
- [ ] 3+ startup/prodotti derivati
- [ ] 100+ contributor GitHub
- [ ] Simulazione e robot reale indistinguibili per SDK
- [ ] Architettura stabile v1.0.0 (SemVer) — no breaking changes per 2+ anni

---

> **"Non costruiamo un robot. Costruiamo la piattaforma che rende banale costruire robot."**