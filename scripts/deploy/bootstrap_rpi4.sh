#!/usr/bin/env bash
#
# OpenJ5 Node 1 bootstrap - Raspberry Pi 4 8GB + Ubuntu Server 24.04 LTS arm64.
#
# Automates docs/deployment/DEPLOYMENT.md sections 3-7:
#   system prep, Docker install, code checkout, secrets+certs, stack up.
#
# Usage:
#   bash scripts/deploy/bootstrap_rpi4.sh                  # full run
#   SKIP_DOCKER=1 bash ...                                 # skip Docker install
#   REPO_DIR=/opt/openj5 bash ...                          # custom checkout path
#
# Run ON the Raspberry Pi as a sudo-capable user.

set -euo pipefail

# ------------------------------------------------------------
# Configuration (override via environment)
# ------------------------------------------------------------
REPO_URL="${REPO_URL:-https://github.com/matteogiovagnini-bit/openj5.git}"
REPO_DIR="${REPO_DIR:-$HOME/src/openj5}"
DEPLOY_DIR="$REPO_DIR/firmware/node1_robot_core/docker"
TIMEZONE="${TIMEZONE:-Europe/Rome}"

log()  { printf "\033[1;34m[openj5-bootstrap]\033[0m %s\n" "$*"; }
step() { printf "\n\033[1;34m[openj5-bootstrap]\033[0m == %s ==\n" "$*"; }
die()  { printf "\033[1;31m[openj5-bootstrap]\033[0m ERROR: %s\n" "$*" >&2; exit 1; }

# ------------------------------------------------------------
# Preflight
# ------------------------------------------------------------
command -v sudo >/dev/null 2>&1 || die "run as a sudo-capable user"
[ -f /proc/device-tree/model ] && grep -qi "Raspberry Pi" /proc/device-tree/model \
    || log "WARNING: this does not look like a Raspberry Pi (continuing)"
. /etc/os-release
case "${VERSION_ID:-}" in
    22.04|24.04) log "Ubuntu $VERSION_ID detected" ;;
    *) log "WARNING: Ubuntu 22.04/24.04 expected, found '${VERSION_ID:-?}' (continuing)" ;;
esac
[ "$(uname -m)" = "aarch64" ] || die "64-bit OS required (aarch64). Reflash with Ubuntu Server 64-bit."

FREE_GB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
[ "${FREE_GB:-0}" -ge 16 ] || die "only ${FREE_GB}GB free on / — at least 16GB needed for images+volumes"

# ------------------------------------------------------------
# 1. System preparation
# ------------------------------------------------------------
step "System update"
sudo apt-get update -qq
sudo apt-get full-upgrade -y -qq
sudo timedatectl set-timezone "$TIMEZONE" 2>/dev/null || log "timezone setup skipped"
sudo apt-get install -y -qq git curl openssl ca-certificates

# Reduce SD wear when journald is persistent
if [ -d /var/log/journal ]; then
    step "journald -> volatile (SD wear reduction)"
    sudo mkdir -p /etc/systemd/journald.conf.d
    printf '[Journal]\nStorage=volatile\nRuntimeMaxUse=64M\n' \
        | sudo tee /etc/systemd/journald.conf.d/openj5.conf >/dev/null
    sudo systemctl restart systemd-journald
fi

# ------------------------------------------------------------
# 2. Docker Engine
# ------------------------------------------------------------
if [ "${SKIP_DOCKER:-0}" = "1" ]; then
    step "Docker install skipped (SKIP_DOCKER=1)"
elif command -v docker >/dev/null 2>&1; then
    step "Docker already present: $(docker --version)"
else
    step "Installing Docker Engine (get.docker.com)"
    curl -fsSL https://get.docker.com | sudo sh
fi
docker info >/dev/null 2>&1 || { sudo usermod -aG docker "$USER"; die "added '$USER' to docker group - log out, back in, rerun"; }
docker compose version >/dev/null 2>&1 || die "docker compose plugin missing"
docker info --format 'cgroup driver: {{.CgroupDriver}}' || true
sudo systemctl enable docker >/dev/null 2>&1 || true

# ------------------------------------------------------------
# 3. Code
# ------------------------------------------------------------
step "Repository"
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --ff-only || log "pull failed, keeping current checkout"
else
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$DEPLOY_DIR"

# ------------------------------------------------------------
# 4. Secrets and certificates (idempotent, gitignored)
# ------------------------------------------------------------
step "Secrets (db, grafana, OTA key)"
bash secrets/generate.sh

if [ ! -f certs/ca.crt ]; then
    step "TLS certificates (first generation)"
    bash certs/generate.sh --quiet
else
    step "TLS certificates already present, keeping them"
fi

# Mosquitto container runs as uid 1883/gid 1000; keys must be group-readable
sudo chgrp 1000 certs/*.key 2>/dev/null || true
chmod 640 certs/*.key 2>/dev/null || true

# ------------------------------------------------------------
# 5. Stack up
# ------------------------------------------------------------
step "Starting stack"
docker compose up -d --build

log ""
log "Bootstrap complete. Verification:"
log "  docker compose ps"
log "  curl -fk https://localhost:8080/health"
log "  Grafana: http://$(hostname):3000 (admin / secrets/grafana_password.txt)"
log ""
log "Full guide: docs/deployment/DEPLOYMENT.md"
