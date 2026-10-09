---
description: Avvia un ciclo di lavoro orchestrato sul backlog OpenJ5 (legge NEXT_TASK.md, pianifica e delega al team)
agent: orchestrator
---

Apri un ciclo di lavoro di sviluppo su OpenJ5.

Contesto git (ultimi commit): !`git log --oneline -3`
Stato working tree: !`git status --short | head -20`

Attività richiesta dall'utente: $ARGUMENTS

Se l'attività è vuota, prendi il primo task ⬜ di **priorità alta** da `docs/NEXT_TASK.md` e proponlo all'utente in una riga prima di partire.

Segui il tuo workflow: contesto → livello di decisione (A/B/C) → piano a passi assegnabili → delega ai subagenti (`architect`, `python-dev`, `firmware-dev`, `tester`, `tech-writer`) → gate di verifica → Design Authority → aggiornamento documentazione → report finale onesto.
