#!/usr/bin/env bash
#
# OpenJ5 Node 1 bootstrap - Raspberry Pi 4 8GB + Raspberry Pi OS Lite 64-bit.
#
# Reference OS/storage: Pi OS Lite Bookworm arm64 + NVMe on USB3 (ADR-016).
# Automates docs/deployment/DEPLOYMENT.md sections 4-8:
#   system prep, memory cgroups for compose limits, Docker install,
#   code checkout, secrets+certs, stack up.
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
case "${ID:-}" in
    debian|raspbian) ;;
    ubuntu) die "Ubuntu detected: reference OS is now Raspberry Pi OS Lite 64-bit (ADR-016). Reflash or override with FORCE_OS=1." ;;
    *) die "unsupported OS '${ID:-?}': use Raspberry Pi OS Lite 64-bit (Bookworm)" ;;
esac
[ "${VERSION_ID:-0}" = "12" ] || log "WARNING: Bookworm (Debian 12) expected, found '${VERSION_ID:-?}'"
[ "$(uname -m)" = "aarch64" ] || die "64-bit OS required (aarch64). Reflash with Pi OS Lite 64-bit."
if [ "${FORCE_OS:-0}" != "1" ]; then
    true
fi

FREE_GB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
[ "${FREE_GB:-0}" -ge 16 ] || die "only ${FREE_GB}GB free on / — at least 16GB needed for images+volumes"

REBOOT_REQUIRED=0

# ------------------------------------------------------------
# 1. System preparation
# ------------------------------------------------------------
step "System update"
sudo apt-get update -qq
sudo apt-get full-upgrade -y -qq
sudo timedatectl set-timezone "$TIMEZONE" 2>/dev/null || log "timezone setup skipped"
sudo apt-get install -y -qq git curl openssl ca-certificates

step "Memory cgroups for container limits (ADR-016)"
CMDLINE=/boot/firmware/cmdline.txt
if [ ! -f "$CMDLINE" ]; then
    CMDLINE=/boot/cmdline.txt
fi
[ -f "$CMDLINE" ] || die "cmdline.txt not found (/boot/firmware/cmdline.txt expected on Bookworm)"
if grep -q cgroup_memory "$CMDLINE"; then
    log "cgroup parameters already present"
else
    sudo sed -i '1s/$/ cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory/' "$CMDLINE"
    grep -q ' ' <<< "$(cat "$CMDLINE")" && awk 'NR>1{exit 1}' "$CMDLINE" \
        || log "cmdline.txt kept as single line"
    REBOOT_REQUIRED=1
    log "patched $CMDLINE (reboot required to activate)"
fi

step "journald -> volatile (storage wear reduction)"
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=volatile\nRuntimeMaxUse=64M\n' \
    | sudo tee /etc/systemd/journald.conf.d/openj5.conf >/dev/null
sudo systemctl restart systemd-journald

step "Hardware watchdog"
if ! grep -q 'dtparam=watchdog=on' /boot/firmware/config.txt 2>/dev/null; then
    echo 'dtparam=watchdog=on' | sudo tee -a /boot/firmware/config.txt >/dev/null
    sudo apt-get install -y -qq watchdog
    sudo systemctl enable --now watchdog 2>/dev/null || true
    REBOOT_REQUIRED=1
else
    log "watchdog dtparam already enabled"
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
if [ "$REBOOT_REQUIRED" -eq 1 ]; then
    log "IMPORTANT: reboot now ('sudo reboot') so cgroup/watchdog params take effect,"
    log "then verify memory limits: docker run --rm --memory=256m alpine sh -c 'free -m'"
    log ""
fi
log "Full guide: docs/deployment/DEPLOYMENT.md"
