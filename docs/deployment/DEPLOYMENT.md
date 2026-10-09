# OpenJ5 Deployment Guide — Raspberry Pi 4 8GB (Node 1: Robot Core)

> Target OS: **Raspberry Pi OS Lite 64-bit (Bookworm)** — decision ADR-016.
> Primary storage: **NVMe on USB3** (SD card = bootloader recovery only).
> Estimated time: 45-60 minutes. Last updated: 2026-10-09 (boot checklist §12, hotspot disabled pending USB dongle).

---

## 1. Hardware Required

| Item | Notes |
|------|-------|
| Raspberry Pi 4 Model B 8GB | Reference hardware (ADR-002) |
| NVMe drive + USB3 enclosure (UASP) | ~300-400 MB/s vs ~40-90 MB/s SD; survives DB write load |
| microSD card 8GB+ | Only for one-time bootloader recovery if USB boot fails |
| Power supply 5.1V / 3A USB-C | Official PSU; NVMe adds ~1-2W — avoid bus-powered hubs without external supply |
| Ethernet cable (recommended) or WiFi | Ethernet preferred for the robot backbone |
| Active cooling (case fan/heatsinks) | Sustained load uses 3-4 cores |

Memory budget: compose hard limits total ≈ 7G, real usage ~2.5-4GB for the robot
services + ~1GB monitoring. Fits in 8GB with headroom (no desktop installed).

---

## 2. Flash Raspberry Pi OS Lite onto the NVMe

On your PC (NVMe connected via the USB3 enclosure):

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Device → **Raspberry Pi 4**.
3. OS → **Raspberry Pi OS (other) → Raspberry Pi OS Lite (64-bit)**.
   ⚠️ Not "Lite (32-bit)", not the desktop variant (ADR-016).
4. Storage → your **NVMe drive**.
5. OS customization (`Ctrl+Shift+X`):
   - Hostname: `openj5-core`
   - Enable SSH (password or public key)
   - Username: `openj5` + password — first user gets UID/GID **1000**
     (required: the Mosquitto container reads TLS keys as group 1000)
   - WiFi SSID/password if not using Ethernet
   - Timezone / keyboard locale
6. Write, eject safely, connect the enclosure to a **blue USB3 port** on the Pi,
   power on.

### One-time bootloader recovery (only if the Pi does not boot from USB)

Recent units boot from USB out of the box. If yours doesn't:

1. With Imager: OS → *Misc utility images* → **Bootloader (Pi 4 Family) → USB Boot**,
   storage → the microSD card; write it.
2. Boot the Pi from that SD alone, wait ~10 s until the green LED blinks steadily,
   power off, remove the SD.
3. Boot from NVMe. Afterwards verify with `sudo rpi-eeprom-update`.

## 3. First Login

```bash
ssh openj5@openj5-core.local     # mDNS; use the IP if .local doesn't resolve
```

## 4. System Preparation

```bash
sudo apt update && sudo apt full-upgrade -y
sudo timedatectl set-timezone Europe/Rome    # adjust
sudo apt install -y git curl openssl ca-certificates ufw
```

### 4.1 Enable memory cgroups (REQUIRED for compose limits)

Raspberry Pi OS ships with the memory cgroup disabled; without this step
`deploy.resources.limits` in docker-compose is silently ignored:

```bash
CG="cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory"
grep -q cgroup_memory /boot/firmware/cmdline.txt || \
  sudo sed -i '1s/$/ '"$CG"'/' /boot/firmware/cmdline.txt
cat /boot/firmware/cmdline.txt   # must remain ONE single line
sudo reboot
```

After reboot verify:

```bash
docker run --rm --memory=256m alpine sh -c 'free -m | head -2'
# "total" column must show ~256MB, not the full RAM
```

### 4.2 Reduce log wear and add watchdog

```bash
# volatile journald (the NVMe thanks you)
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=volatile\nRuntimeMaxUse=64M\n' | \
  sudo tee /etc/systemd/journald.conf.d/openj5.conf
sudo systemctl restart systemd-journald

# hardware watchdog (BCM2835) via systemd
echo 'dtparam=watchdog=on' | sudo tee -a /boot/firmware/config.txt
sudo apt install -y watchdog
printf 'watchdog-device = /dev/watchdog\ninterval = 15\n' | \
  sudo tee /etc/watchdog.conf.d/openj5.conf >/dev/null 2>&1 || true
sudo systemctl enable --now watchdog
```

### 4.3 TRIM check for the NVMe (optional)

```bash
lsblk --discard /dev/sda    # DISC-GRAN/DISC-MAX non-zero = TRIM passthrough OK
sudo systemctl enable fstrim.timer
```

If values are zero your enclosure does not pass UNMAP through — harmless, just
skip periodic TRIM.

Quick performance sanity check (optional):

```bash
sudo hdparm -t $(findmnt -n -o SOURCE /)    # expect ~200-400 MB/sec on good enclosures
```

## 5. Install Docker Engine (official repository)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker          # or log out/in
docker version && docker compose version
```

Docker starts on boot automatically; all OpenJ5 services use
`restart: unless-stopped`, so the whole robot returns after a power cycle.

## 6. Get the Code

Option A — clone (if the repo is reachable/pushed):

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/matteogiovagnini-bit/openj5.git
cd openj5
```

Option B — copy from your dev machine (secrets never travel):

```bash
rsync -av --exclude '.git' --exclude 'node_modules' \
    ~/Documenti/Matteo/openj5/ openj5@openj5-core.local:~/src/openj5/
```

## 7. Generate Secrets and Certificates (on the Pi)

```bash
cd ~/src/openj5/firmware/node1_robot_core/docker

# 1. Secrets: db password, grafana admin password, OTA ECDSA P-256 key
bash secrets/generate.sh

# 2. TLS certificates: CA, broker, node1-6, api, rosbridge, JWT keys
bash certs/generate.sh --quiet
```

Both are gitignored — they exist only on the robot.

Or run steps 4→7 in one shot with the bootstrap script:

```bash
bash ~/src/openj5/scripts/deploy/bootstrap_rpi4.sh
```

## 8. Launch the Stack

```bash
cd ~/src/openj5/firmware/node1_robot_core/docker
docker compose up -d
watch docker compose ps     # wait until everything is healthy (first pull ~10 min)
```

First boot builds the `robot-core` image locally (Python deps download).
Subsequent boots take seconds.

## 9. Verify

| Check | Command / URL | Expected |
|-------|---------------|----------|
| Services healthy | `docker compose ps` | All `Up (healthy)` |
| Robot Core API | `curl -fk https://localhost:8080/health` | `{"status":"ok",...}` |
| Swagger UI | browser: `https://openj5-core:8080/api/docs` (accept self-signed cert) | OpenAPI page |
| MQTT broker | `mosquitto_sub -h localhost -p 8883 --cafile certs/ca.crt -t '$SYS/broker/version' -C 1` | broker version line |
| Grafana | browser: `http://openj5-core:3000` (admin / password in `secrets/grafana_password.txt`) | dashboards provisioned |
| Prometheus | browser: `http://openj5-core:9091/targets` | scrapers up |
| Loki | `curl -s http://localhost:3100/ready` | `ready` |
| Memory limits active | section 4.1 test | container capped at 256MB |
| Logs | `docker compose logs -f robot-core` | structured JSON logs |

Reboot test: `sudo reboot` → after ~2 minutes everything must be back up without
manual action.

## 10. Network Layout (host ports)

| Port | Service | Exposed to |
|------|---------|-----------|
| 22 | SSH | LAN |
| 1883 | MQTT plain (debug only) | LAN |
| 8883 | MQTT TLS (ESP32 nodes attach here) | LAN |
| 9001 | MQTT WebSocket | LAN |
| 8080/8081 | REST API / WS (TLS) | LAN |
| 9090 | rosbridge (TLS) | LAN |
| 3000 / 9091 / 3100 | Grafana / Prometheus / Loki | LAN |
| 4317/4318/8888 | OTEL collector | host-only usage |

Internal bridge `robot-internal` has no internet; only `robot-external` egresses.
Docker does **not** program published ports (`ports:`) for a container attached
*only* to an `internal: true` network — no DNAT rule, no `docker-proxy`,
connections are refused with no warning at deploy time. Mosquitto is therefore
attached to **both** networks (`robot-internal` for container-to-container,
`robot-external` for its LAN listeners); any future service whose ports must
answer on the host needs the same treatment.

Suggested hardening (`ufw` is not preinstalled on Pi OS Lite):

```bash
sudo ufw default deny incoming
sudo ufw allow from 192.168.1.0/24 to any port 22,8080,3000 proto tcp
sudo ufw allow 8883/tcp        # ESP32 nodes
sudo ufw enable
```

## 11. WiFi Hotspot for the ESP Nodes (single-radio AP+STA)

> **Status 2026-10-09: hotspot DISABLED (waiting for a USB WiFi dongle).** The
> home router's band steering cannot be switched off, and on a single radio the
> STA→deauth→reassoc loop never settles (see "Radio constraints" below): the Pi
> and the ESP nodes therefore join the **home WiFi directly** — current mode
> and boot checklist in §12.1-§12.3. All AP units (`openj5-ap-if`,
> `openj5-hostapd`, `openj5-nat`, `openj5-channel-sync.timer`, `dnsmasq`) are
> `disabled`. With a USB dongle (dedicated radio, `AP_IF=wlan1` below) this
> section applies again: re-run `setup_hotspot.sh` and move the ESPs back to
> the `openj5` SSID / `openj5-core` broker name.

The ESP32 nodes do **not** join your home WiFi: they connect to a hotspot
created by the Pi's built-in WiFi, while the same radio keeps the Pi's
internet uplink (AP+STA on one radio). WiFi credentials then live in
exactly one place (the Pi), the robot LAN keeps working even if the home
router is down, and dnsmasq resolves the broker hostname `openj5-core`
(what the firmware expects by default) to the Pi. If a USB WiFi dongle is
available, the AP moves to that second radio (`AP_IF=wlan1`, dual mode
below) and the uplink stays free on 5 GHz.

```text
                        home router (2.4 GHz, FIXED channel)
                                  │ STA client (wlan0)
internet ◄── home WiFi ───── ┌────┴─────┐
                             │ Raspberry │  same radio, same channel
                             │  Pi (N.1) │╌╌╌╌╌╌╌╌╌╌╌╌┐
                             │ mosquitto │              │ AP (ap0)
                             │ robot-core│        ┌─────┴─────┐
                             └───────────┘        │ ESP32 ×6  │
                                                  │ SSID openj5
                                                  └───────────┘
```

### Radio constraints

- **ESP32 are 2.4 GHz only**: the hotspot is always 2.4 GHz (`hw_mode=g`).
- **One radio = one channel** (default, `AP_IF=ap0`): the AP must sit on the
  STA channel. The installer's sync (`openj5-channel-sync.timer`, every 60 s)
  re-pins hostapd automatically — but **pin the router's 2.4 GHz channel**
  (e.g. 6) so it never hops, and connect the uplink to the **2.4 GHz** SSID:
  on 5 GHz the single radio cannot host the AP at all (the installer stops
  with an explicit error).
- **Turn off the router's band/client steering** (Archer-style "band
  steering", OneMesh, 802.11v): those routers push the STA off the 2.4 GHz
  BSSID with WNM "Preferred List" requests and deauthenticate it. On a single
  radio this becomes a loop (observed: disconnect every ~9 s): the channel is
  saturated for ~2 s out of every 9 (slow link, DHCP lease churn) and hostapd
  beacon gaps make the SSID look *invisible* while the Pi itself pings fine.
  Symptoms: `journalctl -u wpa_supplicant` filling with
  `Preferred List Available` and `CTRL-EVENT-DISCONNECTED ... reason=2`.
  Fix on the router: disable steering for the 2.4 GHz network and pin its
  channel; wpa_supplicant blacklists the steered BSSID for 30 min, so
  re-check ~30 min after the change (the loop returns if the router is left
  steering).
- **Dedicated radio** (`AP_IF=wlan1`, USB WiFi dongle with AP mode): the
  uplink stays free on 5 GHz while the dongle hosts the AP on a **fixed**
  channel (`AP_CHANNEL`, default 6) — no channel sync, no coupling with the
  router. Find the dongle's interface with `iw dev`; the installer refuses
  dongles whose driver lacks AP mode. Recommended whenever a dongle exists.
- Control traffic never crosses the internet link (broker and robot-core
  are on the Pi itself): only avoid heavy downloads *while* the robot runs.

### Install

```bash
bash scripts/deploy/setup_hotspot.sh               # single radio: prompts for passphrase
AP_IF=wlan1 bash scripts/deploy/setup_hotspot.sh   # USB dongle: uplink free on 5 GHz
# options: SSID=... PASSPHRASE=... AP_CHANNEL=11 AP_IP=192.168.4.1 WIFI_IF=wlan0 DNS_UPSTREAM=...
```

Idempotent — re-run after changing SSID/passphrase. What it configures:

| Piece | File / unit | Role |
|-------|-------------|------|
| hostapd AP (WPA2) | `/etc/hostapd/openj5.conf` (0600) | `ap0` interface + passphrase |
| dnsmasq | `/etc/dnsmasq.d/openj5.conf` | DHCP `192.168.4.50-150`, DNS `openj5-core` → `192.168.4.1` |
| NAT | `openj5-nat.service` | share the wlan0 uplink (`ip_forward` + MASQUERADE) |
| virtual interface | `openj5-ap-if.service` | creates `ap0`, unmanaged by NetworkManager |
| channel sync | `openj5-channel-sync.timer` | single radio only: AP channel = STA channel (60 s) |

The passphrase is stored only on the Pi (`/etc/hostapd/openj5.conf`, 0600) —
never in git.

### ESP side

```bash
cd firmware/node7_balance
cp sdkconfig.local.example sdkconfig.local   # then set SSID + passphrase
idf.py reconfigure                           # or: pio run
```

### Verify

```bash
sudo systemctl status openj5-hostapd dnsmasq
iw dev                                # ap0 exists, channel == wlan0 channel
hostname -I                           # must include 192.168.4.1
dig +short @192.168.4.1 openj5-core   # must answer 192.168.4.1
```

If you enabled `ufw` in section 10, also allow SSH from the hotspot subnet:

```bash
sudo ufw allow from 192.168.4.0/24 to any port 22 proto tcp
```

### Troubleshooting (hotspot)

| Symptom | Cause / fix |
|---------|-------------|
| ESP never gets an IP | wrong SSID/pass in `sdkconfig.local` → `reconfigure` + `erase-flash`; or AP down → `journalctl -u openj5-hostapd -e` |
| hostapd restart loop | channel mismatch: uplink on 5 GHz or router hopped → `iw dev wlan0 info`, pin the router's 2.4 GHz channel |
| DHCP clash / wrong subnet | home router already on `192.168.4.0/24` → re-run with `AP_IP=192.168.14.1` |
| Pi has no internet | uplink issue only — the robot LAN keeps working |
| `openj5-core` unresolved | `systemctl status dnsmasq`; `dig +short @192.168.4.1 openj5-core` |

## 12. Daily Power Off / On (quick reference)

**Spegnimento:**
```bash
cd ~/src/openj5/firmware/node1_robot_core/docker
docker compose stop        # opzionale ma pulito
sudo poweroff
```
Attendere ~20s che il LED ACT smetta di lampeggiare prima di staccare la USB-C.
Se in uso, staccare anche la batteria dei motori (guida banco: `docs/hardware/BENCH_TRACKS.md`).

**Riaccensione:**
1. Alimentatore USB-C → boot automatico da NVMe (~60s)
2. Lo stack risale da solo (`unless-stopped`). Se avevi fatto `stop`:
   `docker compose start`
3. Verifica (~90s dopo il boot): `docker compose ps` tutto healthy +
   `curl -fk https://localhost:8080/health`
4. Browser da PC: Swagger `https://openj5-core.local:8080/api/docs`,
   Grafana `http://openj5-core.local:3000`

### 12.1 Stato di rete (transitorio, 2026-10-09)

**Hotspot disabilitato in attesa di un dongle USB** (§11): Pi e nodi ESP
stanno sulla WiFi di casa `Piano_Terra_WIFI`.

- Uplink del Pi a **5 GHz** (profilo NetworkManager `Piano24`, `band=a`,
  `autoconnect=yes`): con lo steering del router non configurabile, la
  2.4 GHz scatena il loop deauth descritto in §11 (ora eliminato:
  `deauth = 0` in 2 h).
- Broker per gli ESP: `openj5-core.local` (mDNS di Avahi con
  `allow-interfaces=wlan0` → risponde `192.168.1.108`, mai gli indirizzi dei
  bridge Docker `172.17.x.x`), oppure in fallback diretto `192.168.1.108`.
  Il SAN del certificato broker contiene entrambi i nomi
  (`bash certs/generate.sh --quiet`).
- Gli ESP si agganciano alla 2.4 GHz della stessa SSID: il router "spinge"
  verso le 5 GHz solo i client dual-band, quindi loro non vengono
  deautenticati (verificato: telemetria continua, nessun reconnect).

### 12.2 Checklist di boot (~90 s dopo il power-on)

Cosa deve risalire da solo, in ordine:

| # | Componente | Stato atteso | Verifica |
|---|-----------|--------------|----------|
| 1 | NetworkManager, profilo `Piano24` | `autoconnect=yes`, `band=a`, `activated` su wlan0 | `nmcli -t -f NAME,DEVICE,STATE con show --active` → `Piano24:wlan0:activated` |
| 2 | IP del Pi | `192.168.1.108` presente | `hostname -I` |
| 3 | Avahi mDNS | `active`, `allow-interfaces=wlan0` | `getent hosts openj5-core.local` → `192.168.1.108` |
| 4 | Docker + stack | container `Up (healthy)` | `cd ~/src/openj5/firmware/node1_robot_core/docker && docker compose ps` |
| 5 | API robot-core | `{"status":"ok",...}` | `curl -fk https://localhost:8080/health` |
| 6 | Unità AP + dnsmasq | `inactive` e `disabled` (in attesa dongle) | `systemctl is-active openj5-ap-if openj5-hostapd openj5-nat openj5-channel-sync.timer dnsmasq` |
| 7 | Nodo ESP | telemetria presente sul broker | blocco seguente |

End-to-end: un messaggio deve arrivare entro ~10 s (se il nodo è acceso):

```bash
timeout 10 docker exec openj5-mosquitto mosquitto_sub -h 127.0.0.1 -p 8883 --cafile /mosquitto/certs/ca.crt --cert /mosquitto/certs/node1.crt --key /mosquitto/certs/node1.key -t "openj5/#" -C 1
```

### 12.3 Rimedi

| Sintoma | Causa | Rimedio |
|---------|-------|---------|
| wlan0 non connesso dopo il boot | profilo non attivato (gara NM/dhcp o autoconnect perso) | `sudo nmcli con up Piano24`; poi `nmcli -f connection.autoconnect con show Piano24` deve dire `yes` |
| Disconnessioni ogni ~9 s, SSH a scatti, log `Preferred List Available` + `CTRL-EVENT-DISCONNECTED ... reason=2` (`journalctl -u wpa_supplicant`) | band-steering del router su 2.4 GHz (§11) | tenere l uplink su 5 GHz: `sudo nmcli con mod Piano24 802-11-wireless.band a` (stato attuale) — oppure, con il dongle, spegnere lo steering sul router |
| `openj5-core.local` non risolve o risolve su `172.17.0.1` | Avahi pubblica tutti gli indirizzi del Pi, bridge Docker compresi | `allow-interfaces=wlan0` in `/etc/avahi/avahi-daemon.conf` + `sudo systemctl restart avahi-daemon` |
| ESP connesso alla WiFi ma niente telemetria | host broker errato in `sdkconfig.local`, oppure SAN senza `openj5-core.local` | `CONFIG_OPENJ5_MQTT_HOST="openj5-core.local"` + `pio run -t upload`; per il SAN: `bash certs/generate.sh --quiet` e `docker compose restart mosquitto` |
| `ap0` perde `192.168.4.1` poco dopo la creazione (solo hotspot) | gara: NetworkManager si riprende l interfaccia entro ~600 ms e cancella indirizzi non assegnati da lui | già risolto in `setup_hotspot.sh` (ordine `nmcli dev set $AP_IF managed no` → `ip addr replace`): rieseguire l installer |

**Ripristino hotspot (quando arriva il dongle USB):**

```bash
AP_IF=wlan1 bash scripts/deploy/setup_hotspot.sh
```

poi lato ESP: SSID `openj5` + `CONFIG_OPENJ5_MQTT_HOST="openj5-core"` in
`sdkconfig.local` e riflash (§11). Con la radio dedicata l uplink resta libero
su 5 GHz e non servono il sync di canale né il vincolo sul canale del router.

## 13. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| Compose memory limits ignored | Missing cgroup params: re-do §4.1, reboot, re-run the 256MB test |
| Pi won't boot from NVMe (green LED steady flashes) | EEPROM too old: §2 bootloader recovery via SD |
| NVMe disconnects under load | Power: use official PSU, avoid unpowered hubs; prefer UASP enclosure; try shorter cable |
| mosquitto restarts, "Unable to open private key file" | `chgrp 1000 certs/*.key && chmod 640 certs/*.key`; container runs `1883:1000` |
| mosquitto healthcheck unhealthy | Healthcheck reads `$SYS/broker/version`; ensure `$SYS` publisher is enabled (shipped config does it) |
| Port conflict errors on `up` | Another service uses 9090/8888/etc.: stop it or edit mapping |
| loki crashloop on read-only path | `path_prefix` must be inside writable volume mount (`loki_data`) |
| Postgres auth fails after regenerating secrets | `.env` must match `secrets/db_password.txt`: rerun `secrets/generate.sh`, then `down`/`up` |

Full lessons learned: `docs/KNOWLEDGE_BASE.md`.

## 14. What's Next After Bootstrap

1. ESP32 nodes flash (ROADMAP v0.4.0) will consume `certs/nodeN.crt|key`
   generated here.
2. OTA campaigns sign firmware with `secrets/ota_signing_key.pem` — back it up
   (losing it = losing fleet updatability).
3. CI pipeline validates lint/docs/Docker on every push; integration tests
   (v0.3.0) will run against this same compose stack.

---

*Follows ADR-002 (6-node architecture), ADR-010 (headless digital twin),
ADR-011 (signed OTA), ADR-013 (mTLS/JWT/fail-safe), ADR-015 (MQTT),
ADR-016 (Pi OS Lite + NVMe).*
