# ADR-016: Raspberry Pi OS Lite 64-bit (Bookworm) as Node 1 Reference OS, NVMe-over-USB3 Storage

## Status
Accepted

## Context
Node 1 (Robot Core, Raspberry Pi 4 8GB) was originally specified with
"Ubuntu Server 22.04/24.04 LTS" (ADR-002 era docs, GOALS G1.1). Before the first
real hardware deployment (T-018) the OS choice was re-evaluated, because:

1. **ROS 2 does not constrain the host OS anymore**: rosbridge runs in its own
   container (ADR-003/ADR-015), so Ubuntu's main historical advantage on the Pi
   (first-class ROS 2 host support) is irrelevant for OpenJ5.
2. **Vision roadmap (v0.5.0)** will use the Pi camera stack (libcamera/picamera2),
   which is first-class only on Raspberry Pi OS.
3. **Hardware integration**: firmware updates via apt, `raspi-config`, watchdog
   dtparam are best supported on Raspberry Pi OS.
4. **Storage**: PostgreSQL + Prometheus + Gazebo assets generate continuous random
   I/O that quickly wears an SD card; an NVMe drive on USB3 gives ~300-400 MB/s
   sequential (vs ~40-90 MB/s SD) and far better endurance/random-I/O latency.
   The Pi 4 boots natively from USB mass storage via its EEPROM bootloader.
5. Owner preference for the official Pi Foundation OS.

## Decision
1. **Raspberry Pi OS Lite 64-bit (Bookworm)** is the reference OS for Node 1.
   The desktop (PIXEL) variant is explicitly NOT used: the node runs headless,
   all interaction is via SSH/browser (REST :8080, Grafana :3000, rosbridge :9090),
   saving ~0.5-1GB RAM and reducing attack surface. Desktop can be added later for
   bench work without reflashing (`apt install raspberrypi-ui-mods`).
2. **Primary storage = NVMe on USB3** (UASP-capable enclosure recommended);
   microSD remains the fallback/bootloader-recovery medium.
3. Container memory limits (`deploy.resources.limits` in docker-compose) require
   adding `cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory` to
   `/boot/firmware/cmdline.txt` (single line) - automated by the bootstrap script.

## Alternatives Considered
1. **Ubuntu Server 24.04 LTS arm64** - Previously documented default. Longer
   fixed support window (Apr 2029) and uniform CI base, but weaker Pi hardware
   integration, manual libcamera setup, slightly heavier footprint.
   Rejected for v0.3.0-era deployment; may be revisited via new ADR for
   fleet/server variants.
2. **Raspberry Pi OS with desktop (64-bit)** - Useful only with a physically
   attached display; wasted RAM/CPU on an embedded robot node. Rejected.
3. **Dual-OS documentation** - Doubles maintenance of procedures and
   troubleshooting matrices for zero current benefit (everything else runs in
   containers). Rejected; keep one blessed path.

## Consequences
**Positive:**
- Best-in-class Pi hardware support (firmware, watchdog, camera stack ready for v0.5.0).
- Lighter idle footprint -> more RAM/CPU headroom for the 10-service stack.
- NVMe storage removes the SD-card wear failure mode and speeds DB-heavy services.
- Headless-only reduces attack surface (consistent with ADR-013 posture).

**Negative:**
- Support lifecycle follows Debian/Pi Foundation releases (~2028 for Bookworm);
  an OS refresh (Trixie) will be a planned maintenance task, acceptable within
  the 10-year platform horizon.
- `cmdline.txt` modification is mandatory for compose memory limits; forgetting
  it silently disables `deploy.resources.limits`.
- USB boot depends on EEPROM bootloader version; very old Pi 4 units need a
  one-time bootloader update from SD (documented procedure).
- Documentation updated repo-wide (README, ARCHITECTURE diagrams, GOALS,
  DEPLOYMENT, bootstrap script).

## Implementation Notes
- `docs/deployment/DEPLOYMENT.md` rewritten for Pi OS Lite + NVMe flow:
  flash NVMe directly with Raspberry Pi Imager (headless customization),
  one-time EEPROM/USB-boot recovery via SD only if needed.
- `scripts/deploy/bootstrap_rpi4.sh` detects Debian Bookworm/aarch64, applies the
  cgroup cmdline patch idempotently (reboot hint), keeps secrets/certs generation
  on-device.
- Verification after boot: `rpi-eeprom-update`, `lsblk --discard` (TRIM passthrough),
  `docker info` showing default cgroup with memory limits honored.

## Related ADRs
- ADR-002: Six-node distributed architecture (defines Node 1 hardware)
- ADR-010: Digital Twin Native (headless Gazebo fits the no-desktop decision)
- ADR-013: Security (headless reduces exposed surface; mTLS/JWT unchanged)
- ADR-015: MQTT primary transport (rosbridge containerized -> no host ROS dependency)
