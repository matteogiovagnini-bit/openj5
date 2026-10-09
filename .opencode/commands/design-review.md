---
description: Esegue la Design Authority review a 10 punti di OpenJ5 sui cambiamenti della sessione corrente
agent: architect
---

Esegui la **OpenJ5 Design Authority review** su: $ARGUMENTS

Se non indichi un target, usa i cambiamenti non committati di questa sessione (`git diff` + `git status`).

Applica i 10 controlli di `Development_Constitution.md`:
1. Architettura generale (esagonale, Ports & Adapters)
2. Compatibilità con gli ADR (`docs/adr/`)
3. Compatibilità con il Robot SDK (`src/sdk/robot.py`)
4. Compatibilità con il Digital Twin (sim = real API)
5. Sistema di configurazione (nessun numero magico, tutto da `config/`)
6. Roadmap (`ROADMAP.md`)
7. Test (coverage ≥90% core.domain, nessun gate saltato)
8. Firmware ESP32 (parità Python↔firmware)
9. CAD ed elettronica
10. Nessuna violazione della Project Constitution

Riporta ⚠️ / ❌ per ogni punto con il file di evidenza. Concludi con: COMPLETATA (tutti ✅) oppure BLOCCATA con l'elenco delle azioni correttive e l'agente a cui affidarle.
