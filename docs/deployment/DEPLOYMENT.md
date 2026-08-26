# OpenJ5 Deployment Guide — Raspberry Pi 4 8GB (Node 1: Robot Core)

> Target OS: **Raspberry Pi OS Lite 64-bit (Bookworm)** — decision ADR-016.
> Primary storage: **NVMe on USB3** (SD card = bootloader recovery only).
> Estimated time: 45-60 minutes. Last updated: 2026-08-25.

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

Suggested hardening (`ufw` is not preinstalled on Pi OS Lite):

```bash
sudo ufw default deny incoming
sudo ufw allow from 192.168.1.0/24 to any port 22,8080,3000 proto tcp
sudo ufw allow 8883/tcp        # ESP32 nodes
sudo ufw enable
```

## 11. Daily Power Off / On (quick reference)

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

## 12. Troubleshooting

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

## 13. What's Next After Bootstrap

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
