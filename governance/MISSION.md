# MISSION

## Dichiarazione di Missione

**Democratizzare la robotica embodiment professionale** fornendo una piattaforma open source, modulare, documentata e duratura che permetta a chiunque — maker, ricercatori, startup, studenti — di concentrarsi sull'intelligenza e l'interazione del robot, non sull'infrastruttura.

---

## Obiettivi di Missione (Prioritizzati)

### 1. Infrastruttura Robotica Professionale Accessibile
Fornire un'architettura di riferimento (Reference Architecture) per robot umanoidi che applica **pratiche enterprise** (Hexagonal Architecture, DDD, Event-Driven, DI, Plugin System, HAL, Digital Twin) in un progetto open source replicabile da un singolo maker.

### 2. Eliminare la Frammentazione
Oggi chi costruisce un robot deve reinventare: comunicazione, HAL, state machine, configurazione, OTA, simulazione, SDK. OpenJ5 fornisce **tutto questo out-of-the-box**, ben documentato e testato.

### 3. Abilitare l'AI Embodiment Reale
L'AI moderna (LLM, VLM, Diffusion Policy, RL) ha bisogno di un **corpo** per interagire col mondo fisico. OpenJ5 fornisce quel corpo — con API pulite, simulazione fedele, hardware sostituibile — così i ricercatori AI possono testare embodiment *davvero*.

### 4. Creare un Ecosistema Sostenibile
Non un progetto "one-man show". OpenJ5 è progettato per:
- **Governance distribuita** (Design Authority, Component Owners)
- **Plugin marketplace** comunitario
- **Hardware certification** (Core / Compatible / Experimental)
- **Funding model** sostenibile (sponsor, support pro, certification, training)

### 5. Documentazione come Prodotto
La documentazione non è "dopo". È **parte del deliverable**. Ogni funzionalità include: API docs, diagrammi Mermaid, ADR, guide utente, guide sviluppatore, troubleshooting, esempi.

---

## Cosa NON È la Missione

| Non Missione | Perché |
|--------------|--------|
| Costruire il "miglior robot Johnny 5" | L'hardware è un mezzo, non il fine. La piattaforma è il prodotto. |
| Competere con Boston Dynamics / Unitree / Tesla | Loro fanno prodotti closed-source. Noi facciamo infrastruttura open. |
| Essere un framework ROS 2 wrapper | ROS 2 è *un* protocollo supportato dal Communication Gateway. Non l'architettura. |
| Fare tutto noi | La piattaforma abilita altri a fare. Noi mantenuti da loro. |

---

## Misurazione della Missione (KPIs Annuali)

| KPI | Target Anno 1 | Target Anno 3 |
|-----|---------------|---------------|
| Robot costruiti (community) | 20 | 100+ |
| Plugin nel registry | 10 | 50+ |
| Contributor attivi/mese | 5 | 20+ |
| Paper/corsi che usano OpenJ5 | 2 | 10+ |
| Startup/aziende su base OpenJ5 | 0 | 3+ |
| Copertura test (core) | >80% | >90% |
| Docs coverage (API publiche) | 100% | 100% |
| ADR accumulati | 20 | 60+ |
| Tempo setup nuovo sviluppatore | <4 ore | <30 min |
| Tempo add nuovo plugin | <1 giorno | <2 ore |

---

## Impegno Permanente

> **OpenJ5 non sarà mai abbandonato.** Se il core team cambia, la governance (Design Authority, ADR, docs, continuity prompt) garantisce continuità. Il codice è scritto per essere letto, capito, esteso da chiunque — oggi o tra 5 anni.

> **La documentazione è il vero codice sorgente.** Il codice eseguibile è solo una rappresentazione compilata della documentazione.