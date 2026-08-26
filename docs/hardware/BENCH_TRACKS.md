# OpenJ5 Bench Bring-Up — Nodo 6 Cingoli (L298N + 2× DC Gear Motor)

> Prototipo da banco del Nodo 6: due motoriduttori DC pilotati da L298N via GPIO del Pi.
> Driver HAL: `src/hardware/drivers/l298n.py` · Demo: `scripts/demo/tracks_bench.py`
> Config: `config/bench/tracks.json` · Ultimo aggiornamento: 2026-08-26

---

## 1. Materiale

| Componente | Note |
|------------|------|
| Raspberry Pi 4 (openj5-core) | Già operativo con stack Docker |
| L298N dual H-bridge module | Versione blu con heatsink e jumper |
| 2× motoriduttore DC 12V (XD-37GB520 300rpm) | Un motore = sinistro, uno = destro |
| Batteria LiPo 3S (11,1–12,6V) o alimentatore 12V ≥2A | Potenza SOLO ai motori |
| Fusibile inline 5A (consigliato) sul + batteria | Protezione cortocircuiti |
| Cavetti dupont F-F ×8 + portafusibili | Segnali |

---

## 2. Collegamenti

### 2.1 L298N ↔ Raspberry Pi (segnali)

| L298N | Pin fisico Pi | GPIO | Funzione |
|-------|--------------|------|----------|
| ENA *(jumper rimosso)* | 12 | GPIO18 | PWM motore sinistro |
| IN1 | 16 | GPIO23 | Direzione sx A |
| IN2 | 18 | GPIO24 | Direzione sx B |
| ENB *(jumper rimosso)* | 33 | GPIO13 | PWM motore destro |
| IN3 | 15 | GPIO22 | Direzione dx A |
| IN4 | 13 | GPIO27 | Direzione dx B |
| GND | 6 | — | Massa comune ⚠️ obbligatoria |

⚠️ **Rimuovere i jumper ENA ed ENB**: li sostituiamo con i GPIO per il controllo velocità PWM.

### 2.2 Alimentazione

| Da | A |
|----|---|
| Batteria **+** (via fusibile) | L298N **VMS** |
| Batteria **−** | L298N **GND** **e** Pi pin 6 (massa comune) |
| Pi **pin 4** (5V) | L298N **+5V** |
| OUT1/OUT2 | Motore sinistro |
| OUT3/OUT4 | Motore destro |

```
   BATTERIA 3S ──┬── VMS (L298N)          POTENZA MOTORI (mai dal Pi!)
                 └── GND ──┬── GND (L298N)
                           └── GND (Pi pin 6)     ← STESSA MASSA
   PI 5V (pin 4) ────── +5V (L298N, jumper rimosso)
   PI GPIO ──────────── ENA/IN1..IN4            ← SOLO SEGNALI
```

⚠️ Con LiPo carico pieno 12,6V il regolatore di bordo è al limite: **tenere il jumper
del 5V RIMOSSO** e alimentare la logica dal Pi come sopra.

### 2.3 Checklist pre-test

1. Jumper ENA/ENB rimossi ✅
2. Jumper regolatore 5V rimosso ✅
3. Massa comune verificata (continuità GND batteria ↔ Pi ↔ modulo) ✅
4. **Ruote sollevate da terra** ✅
5. Nessun segnale su GPIO14/15 (console seriale) ✅
6. La **batteria si collega PER ULTIMA**, tutto già cablato ✅

---

## 3. Software

```bash
# una volta sola
sudo apt install -y python3-gpiozero

# ad ogni sessione bancare (dopo che lo stack è su, vedi DEPLOYMENT §14)
cd ~/src/openj5
python3 scripts/demo/tracks_bench.py        # --config per JSON alternativo
```

Comandi demo: `w/s` avanti/indietro · `a/d` sterzo sul posto · `+/−` velocità ·
`x` stop · `q` esci (brake automatico sempre).

I pin NON sono nel codice: tutto vive in `config/bench/tracks.json`.

---

## 4. Spegnimento fine sessione

1. Nel demo premi `q` (motori rilasciati e frenati)
2. **Stacca la batteria** dal L298N (o switch di linea se installato)
3. Ferma lo stack (opzionale ma pulito):
   ```bash
   cd ~/src/openj5/firmware/node1_robot_core/docker
   docker compose stop
   ```
4. Spegni il Pi:
   ```bash
   sudo poweroff
   ```
5. Attendi ~20s che il LED verde (ACT) smetta completamente di lampeggiare,
   poi stacca l'alimentatore USB-C

**LiPo**: se resta fermo settimane, riportalo a *storage* (~11,4V) col caricabatterie.

---

## 5. Riaccensione / riattivazione

1. Collega l'alimentatore USB-C del Pi → boot automatico da NVMe (~60s)
2. Attendi che i servizi risalgano da soli (policy `unless-stopped`):
   ```bash
   cd ~/src/openj5/firmware/node1_robot_core/docker
   docker compose ps          # tutto Up; robot-core healthy dopo ~90s
   curl -fk https://localhost:8080/health
   ```
   > Se hai fatto `docker compose stop` alla chiusura, usa `docker compose start`
   > (oppure `up -d`). Senza stop esplicito non serve nulla: ripartono da soli.
3. Verifica da PC: Swagger `https://openj5-core.local:8080/api/docs`,
   Grafana `http://openj5-core.local:3000`
4. Per i motori: collega la batteria **dopo** il boot del Pi, ruote sollevate,
   lancia il demo (§3)

---

## 6. Troubleshooting rapido

| Sintomo | Causa / cura |
|---------|--------------|
| Un motore gira al contrario | Inverti i suoi DUE fili su OUTx |
| Velocità fissa, ignora +/- | Jumper ENA/ENB ancora montati |
| Il Pi si riavvia quando parte il motore | Massa comune assente o potenza presa per errore dal Pi |
| `ModuleNotFoundError: gpiozero` | `sudo apt install python3-gpiozero python3-libgpiod` |
| Demo parte ma nulla si muove | Batteria non collegata / fusibile aperto / ENA-ENB scollegati |

---

*Rispetta ADR-005 (HAL: questo driver è la prima implementazione reale),
ADR-002 (prototipo Nodo 6) e la regola costituzionale zero-numeri-magici
(mappatura GPIO interamente in `config/bench/tracks.json`).*
