======================================================================
PERSISTENT PROJECT MEMORY
======================================================================

OpenJ5 è un progetto di lunga durata.

Ogni sessione di sviluppo deve poter essere interrotta e ripresa in qualsiasi momento, anche utilizzando una diversa IA.

Per questo motivo è OBBLIGATORIO mantenere aggiornata la memoria del progetto.

La documentazione è parte integrante del codice.

Un'implementazione senza documentazione aggiornata è considerata incompleta.

======================================================================
SESSION REPORT
======================================================================

Alla fine di OGNI sessione creare o aggiornare:

/docs/SESSION_REPORT.md

contenente almeno:

• Data e ora

• Versione del progetto

• Obiettivi della sessione

• Attività completate

• File creati

• File modificati

• Decisioni prese

• ADR creati

• Problemi riscontrati

• Debito tecnico

• Funzionalità rimaste incomplete

• Prossimi passi consigliati

• Prompt di continuità da utilizzare nella prossima sessione

======================================================================
PROJECT STATUS
======================================================================

Aggiornare sempre:

/docs/PROJECT_STATUS.md

con:

Percentuale completamento

Hardware

Firmware

Software

CAD

Elettronica

Documentazione

Testing

Roadmap

Rischi

Problemi aperti

Dipendenze

======================================================================
PROJECT MEMORY
======================================================================

Creare

/docs/PROJECT_MEMORY.md

Questo documento rappresenta la memoria permanente del progetto.

Deve contenere:

Visione generale

Architettura

Decisioni principali

Hardware utilizzato

Motivazioni

Pattern utilizzati

Regole di progettazione

Convenzioni

Obiettivi futuri

Mai perdere questo documento.

======================================================================
KNOWLEDGE BASE
======================================================================

Creare

/docs/KNOWLEDGE_BASE.md

Contiene:

Domande frequenti

Problemi risolti

Best Practice

Scelte progettuali

Procedure

Suggerimenti

Errori da evitare

======================================================================
NEXT TASK
======================================================================

Creare

/docs/NEXT_TASK.md

Questo documento deve contenere solamente

le prossime attività ordinate per priorità.

Ogni attività deve avere

ID

Titolo

Descrizione

Priorità

Dipendenze

Stima

Stato

======================================================================
DECISION LOG
======================================================================

Ogni decisione importante deve produrre automaticamente un nuovo ADR.

Mai modificare un ADR precedente.

Gli ADR rappresentano la storia dell'evoluzione del progetto.

======================================================================
CHANGELOG
======================================================================

Aggiornare sempre

CHANGELOG.md

Seguendo il formato Keep a Changelog.

======================================================================
VERSIONING
======================================================================

Utilizzare Semantic Versioning.

Major.Minor.Patch

Esempi

0.1.0

0.2.0

0.3.0

1.0.0

======================================================================
IMPLEMENTATION WORKFLOW
======================================================================

Per ogni nuova funzionalità seguire SEMPRE il seguente flusso.

1.

Analisi

2.

Verifica impatto architetturale

3.

Aggiornamento documentazione

4.

Creazione ADR se necessario

5.

Implementazione

6.

Unit Test

7.

Integration Test

8.

Refactoring

9.

Aggiornamento README

10.

Aggiornamento CHANGELOG

11.

Aggiornamento PROJECT_STATUS

12.

Aggiornamento PROJECT_MEMORY

13.

Aggiornamento NEXT_TASK

14.

Generazione SESSION_REPORT

Se uno dei punti precedenti non viene completato,

la funzionalità NON è considerata terminata.

======================================================================
QUALITY GATE
======================================================================

Prima di considerare completata qualsiasi implementazione verificare:

✓ Compila

✓ Test superati

✓ Documentazione aggiornata

✓ ADR aggiornati

✓ Changelog aggiornato

✓ Roadmap aggiornata

✓ Nessun warning critico

✓ Nessun TODO senza descrizione

✓ Nessun codice duplicato

✓ Nessun numero magico

======================================================================
SELF REVIEW
======================================================================

Alla fine di ogni implementazione eseguire automaticamente una revisione del lavoro.

Verificare:

Possibili miglioramenti

Debito tecnico

Codice duplicato

Problemi architetturali

Violazioni SOLID

Violazioni Clean Architecture

Violazioni DDD

Possibili ottimizzazioni

Documentare tutto.

======================================================================
CONTINUITY PROMPT
======================================================================

Alla fine di ogni sessione generare automaticamente

/docs/CONTINUATION_PROMPT.md

contenente un prompt completo che permetta ad un'altra IA

(OpenCode, ChatGPT, Claude, Gemini, Codex ecc.)

di continuare immediatamente il progetto senza perdere il contesto.

Il prompt deve includere:

- Stato corrente del progetto
- Architettura
- Decisioni principali
- Hardware utilizzato
- Software implementato
- Firmware implementato
- CAD disponibile
- Documentazione aggiornata
- Attività completate
- Attività in corso
- Prossime attività
- Rischi
- Debito tecnico
- Istruzioni operative

Questo documento deve essere sempre rigenerato alla fine di ogni sessione.

======================================================================
REGOLA FONDAMENTALE
======================================================================

Il progetto deve poter essere chiuso oggi e riaperto tra due anni, oppure continuato da un'altra IA o da un altro sviluppatore, senza perdere alcuna informazione tecnica o decisione progettuale.

La continuità del progetto è un requisito funzionale, non un'attività opzionale.