# OpenJ5 Deployment Guide — Raspberry Pi 4 8GB (Node 1: Robot Core)

> Target: prepare a Raspberry Pi 4 8GB as **openj5-core**, running the full Robot Core
> Docker stack (10 services). Estimated time: 45-60 minutes.
> Last updated: 2026-08-25

---

## 1. Hardware Required

| Item | Notes |
|------|-------|
| Raspberry Pi 4 Model B 8GB | Reference hardware (ADR-002) |
| SSD USB 3.0 + case/adapters **(strongly recommended)** | SD card works but wears out fast with PostgreSQL/Prometheus writes |
| Power supply 5.1V / 3A USB-C | Official PSU recommended; Gazebo is CPU-hungry |
| MicroSD card 16GB+ | Only for first boot if using SSD boot |
| Ethernet cable (recommended) or WiFi | Ethernet strongly preferred for the robot backbone |
| Active cooling (case fan/heatsinks) | Sustained load ~3-4 cores |

Memory budget (compose limits): mosquitto+redis+postgres+robot-core+ros2-bridge+
gazebo ≈ 7G hard limits, ~2.5-4GB real usage; monitoring stack adds ~1GB. Fits in 8GB
with headroom for the OS.

---

## 2. Flash Ubuntu Server 24.04 LTS (64-bit)

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on your PC.
2. Choose OS → **Ubuntu Server 24.04.x LTS (64-bit)** — arm64 is mandatory.
3. Storage → your SD/SSD.
4. Open the gear icon (OS customization) and set:
   - Hostname: `openj5-core`
   - Username: `openj5` (or keep your own; see note below)
   - Enable SSH (password or public key)
   - WiFi SSID/password if not using Ethernet
   - Timezone and keyboard layout
5. Write, insert media into the Pi, power it on, wait ~2 minutes.

Find the device on your network:

```bash
ping openj5-core.local        # mDNS, works from most Linux/macOS
ssh <user>@openj5-core.local  # default password chosen in imager
```

> **UID/GID note:** the Mosquitto container runs as `1883:1000` to read bind-mounted
> TLS keys owned by group `1000`. The default first user on Ubuntu Server is exactly
> `1000:1000`. If you create a custom user with another primary group, either keep
> group 1000 or adjust `docker-compose.yml`.

## 3. System Preparation

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot   # if kernel updated

# Basics
sudo timedatectl set-timezone Europe/Rome     # adjust
sudo apt install -y git curl openssl ca-certificates

# Reduce SD-card wear (recommended if booting from SD):
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=volatile\nRuntimeMaxUse=64M\n' | \
  sudo tee /etc/systemd/journald.conf.d/openj5.conf
sudo systemctl restart systemd-journald
```

Optional (stability under sustained load): add a small zswap instead of heavy swap,
and enable the hardware watchdog:

```bash
# zswap (kernel default backend) - light on CPU, protects RAM headroom
echo 'zswap.enabled=1' | sudo tee /etc/modprobe.d/zswap.conf

# BCM2835 hardware watchdog handled by systemd
sudo apt install -y watchdog
sudo systemctl enable --now watchdog
```

## 4. Install Docker Engine (official repository)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker          # or log out/in
docker version && docker compose version
```

Docker starts on boot automatically (`systemd` unit enabled); all OpenJ5 services use
`restart: unless-stopped`, so the whole robot comes back after a power cycle.

## 5. Get the Code

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

## 6. Generate Secrets and Certificates (on the Pi)

Run **on the Pi**, inside the deploy directory:

```bash
cd ~/src/openj5/firmware/node1_robot_core/docker

# 1. Secrets: db password, grafana admin password, OTA ECDSA P-256 key
#    (also creates .env with DB_PASSWORD, kept in sync)
bash secrets/generate.sh

# 2. TLS certificates: CA, broker, node1-6, api, rosbridge, JWT keys
bash certs/generate.sh --quiet
```

Both files/directories are gitignored — they exist only on the robot.

Key permissions are set automatically (`600` private keys, group-readable by the
container's gid). If you regenerate later, re-check:

```bash
chmod 640 certs/*.key && chgrp 1000 certs/*.key   # group readable by mosquitto (uid 1883/gid 1000)
```

## 7. Launch the Stack

```bash
cd ~/src/openj5/firmware/node1_robot_core/docker
docker compose up -d
watch docker compose ps     # wait until everything is healthy (first pull ~10 min)
```

First boot builds the `robot-core` image locally (Python deps download). Subsequent
boots take seconds.

## 8. Verify

| Check | Command / URL | Expected |
|-------|---------------|----------|
| Services healthy | `docker compose ps` | All `Up (healthy)` |
| Robot Core API | `curl -fk https://localhost:8080/health` | `{"status":"ok",...}` |
| Swagger UI | browser: `https://openj5-core:8080/api/docs` (accept self-signed cert) | OpenAPI page |
| MQTT broker | `mosquitto_sub -h localhost -p 8883 --cafile certs/ca.crt -t '$SYS/broker/version' -C 1` | broker version line |
| MQTT WebSocket | port 9001 listening | — |
| Grafana | browser: `http://openj5-core:3000` (admin / password in `secrets/grafana_password.txt`) | dashboards provisioned |
| Prometheus | browser: `http://openj5-core:9091/targets` | scrapers up |
| Loki | `curl -s http://localhost:3100/ready` | `ready` |
| Logs | `docker compose logs -f robot-core` | structured JSON logs |

Reboot test: `sudo reboot` → after ~2 minutes everything must be back up without
manual action.

## 9. Network Layout (host ports)

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

The internal bridge network `robot-internal` has no internet access; only
`robot-external` egresses (OTA, image pulls).

Suggested hardening (when the robot leaves your desk):

```bash
sudo ufw default deny incoming
sudo ufw allow from 192.168.1.0/24 to any port 22,8080,3000 proto tcp
sudo ufw allow 8883/tcp        # ESP32 nodes
sudo ufw enable
```

## 10. Troubleshooting (lessons learned 2026-08-13, see docs/KNOWLEDGE_BASE.md)

| Symptom | Cause / Fix |
|---------|-------------|
| mosquitto restarts, logs "Unable to open private key file" | Cert key permissions: `chgrp 1000 certs/*.key && chmod 640 certs/*.key`; container runs `1883:1000` |
| mosquitto healthcheck unhealthy | Healthcheck reads `$SYS/broker/version`; ensure broker publishes `$SYS` topics (config ships a publisher) |
| Port conflict errors on `up` | Something else uses 9090/8888/etc.: stop the conflicting service or edit the mapping |
| loki crashloop writing to read-only path | Config requires `path_prefix` inside the writable volume mount (`loki_data`) |
| robot-core build fails pulling ROS packages | Not an error: the Python image intentionally has no ROS deps (rosbridge runs separately) |
| Postgres password mismatch after regenerating secrets | `.env` and `secrets/db_password.txt` must match — rerun `secrets/generate.sh`, then `docker compose down && up -d` (volume keeps old data; drop `postgres_data` only for a clean start) |

## 11. What's Next After Bootstrap

1. ESP32 nodes flash (T-014, ROADMAP v0.4.0) will consume the per-node certificates
   `certs/nodeN.crt|key` already generated here.
2. OTA campaigns sign firmware with `secrets/ota_signing_key.pem` — back it up safely
   (losing it = losing fleet updatability).
3. CI pipeline (`.github/workflows/ci.yml`) validates lint/docs/Docker on every push;
   integration tests (v0.3.0) will run against this same compose stack.

---

*This document follows ADR-002 (6-node architecture), ADR-011 (signed OTA),
ADR-013 (mTLS/JWT/fail-safe), ADR-015 (MQTT primary transport).*
