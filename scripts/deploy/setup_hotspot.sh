#!/usr/bin/env bash
#
# OpenJ5 WiFi hotspot - Raspberry Pi as access point for the ESP32 nodes.
#
# docs/deployment/DEPLOYMENT.md section 11. Two modes:
#
#   AP_IF=ap0 (default)  single radio (AP+STA share one channel): the
#                        built-in WiFi serves the robot LAN on a virtual
#                        `ap0` while the same radio keeps the uplink (wlan0
#                        client, NetworkManager). The uplink MUST be on
#                        2.4 GHz (ESP32 are 2.4 GHz only) and
#                        openj5-channel-sync keeps the AP on the STA channel
#                        -> PIN the router's 2.4 GHz channel once.
#   AP_IF=wlan1          dedicated radio (USB WiFi dongle with AP mode):
#                        uplink free on 5 GHz (wlan0), the AP runs on the
#                        dongle at a FIXED channel (AP_CHANNEL), no channel
#                        sync, no uplink/channel coupling.
#
# Both modes: the ESP hotspot is always 2.4 GHz (hw_mode=g).
#
# Generates (idempotent - re-run after changing SSID/PASSPHRASE):
#   /etc/hostapd/openj5.conf             hostapd AP (WPA2, 0600: passphrase)
#   /etc/dnsmasq.d/openj5.conf           DHCP + DNS (openj5-core -> AP IP)
#   /etc/sysctl.d/99-openj5-hotspot.conf net.ipv4.ip_forward
#   /etc/systemd/system/openj5-*.service|.timer
#   /usr/local/sbin/openj5-{ap-if,nat,channel-sync}
#
# Usage (on the Pi, sudo-capable user; uplink already connected):
#   bash scripts/deploy/setup_hotspot.sh                 # single radio (ap0)
#   AP_IF=wlan1 bash scripts/deploy/setup_hotspot.sh     # USB dongle as AP
#   SSID=openj5 PASSPHRASE='...' AP_CHANNEL=11 AP_IF=wlan1 bash ...
#
# Env options: SSID PASSPHRASE WIFI_IF AP_IF AP_CHANNEL AP_IP DHCP_START
#              DHCP_END MQTT_HOST DNS_UPSTREAM
#
# Secrets: the passphrase ends up only in /etc/hostapd/openj5.conf (0600
# root, on the Pi) - never in git. The ESP mirrors it in the uncommitted
# sdkconfig.local (template: firmware/node7_balance/sdkconfig.local.example).

set -euo pipefail

# ------------------------------------------------------------
# Configuration (override via environment)
# ------------------------------------------------------------
SSID="${SSID:-openj5}"
PASSPHRASE="${PASSPHRASE:-}"
WIFI_IF="${WIFI_IF:-wlan0}"
AP_IF="${AP_IF:-ap0}"
AP_CHANNEL="${AP_CHANNEL:-6}"       # fixed AP channel (dual-radio mode; also single-radio start value)
AP_IP="${AP_IP:-192.168.4.1}"
SUBNET="${AP_IP%.*}"
DHCP_START="${DHCP_START:-${SUBNET}.50}"
DHCP_END="${DHCP_END:-${SUBNET}.150}"
NETMASK="${NETMASK:-255.255.255.0}"
# CIDR prefix for the AP address (255.255.255.0 -> 24); guard against garbage.
AP_PREFIX="$(printf '%s' "$NETMASK" | awk -F. '{c=0; for (i=1;i<=4;i++) {x=$i; while (x>0) {c+=x%2; x=int(x/2)}} print c}')"
case "$AP_PREFIX" in ''|*[!0-9]*|0) AP_PREFIX=24 ;; esac
MQTT_HOST="${MQTT_HOST:-openj5-core}"
DNS_UPSTREAM="${DNS_UPSTREAM:-1.1.1.1}"

HOTSPOT_CONF=/etc/hostapd/openj5.conf
DNSMASQ_CONF=/etc/dnsmasq.d/openj5.conf
SYSCTL_CONF=/etc/sysctl.d/99-openj5-hotspot.conf
UNIT_DIR=/etc/systemd/system
LIB_DIR=/usr/local/sbin

log()  { printf "\033[1;34m[openj5-hotspot]\033[0m %s\n" "$*"; }
step() { printf "\n\033[1;34m[openj5-hotspot]\033[0m == %s ==\n" "$*"; }
die()  { printf "\033[1;31m[openj5-hotspot]\033[0m ERROR: %s\n" "$*" >&2; exit 1; }

# ------------------------------------------------------------
# Preflight
# ------------------------------------------------------------
command -v sudo >/dev/null 2>&1 || die "run as a sudo-capable user"
[ -d "/sys/class/net/$WIFI_IF" ] || die "WiFi interface '$WIFI_IF' not found (set WIFI_IF=)"

# The passphrase/SSID land in a plain-text conf file: reject characters that
# would break the `key=value` lines or the unquoted heredocs below.
for v in SSID PASSPHRASE; do
    if printf '%s' "${!v}" | grep -Eq '["#\\]'; then
        die "$v must not contain double quotes, '#' or backslash"
    fi
done

if [ -z "$PASSPHRASE" ]; then
    [ -t 0 ] || die "PASSPHRASE is required (8-63 chars, WPA2)"
    read -r -s -p "Hotspot passphrase (WPA2, 8-63 chars): " PASSPHRASE
    echo
fi
[ "${#PASSPHRASE}" -ge 8 ] && [ "${#PASSPHRASE}" -le 63 ] \
    || die "passphrase must be 8-63 characters"

sta_channel="$(iw dev "$WIFI_IF" info 2>/dev/null | awk '$1 == "channel" {print $2}' || true)"
if [ "$AP_IF" = "ap0" ]; then
    # Single radio: with the uplink on 5 GHz the 2.4 GHz AP cannot run at all.
    if [ -n "$sta_channel" ] && [ "$sta_channel" -gt 14 ] 2>/dev/null; then
        die "$WIFI_IF uplink is on 5 GHz (channel $sta_channel) and AP_IF=ap0 shares that radio: connect the uplink to the 2.4 GHz SSID, or plug a USB WiFi dongle and re-run with AP_IF=wlan1"
    elif [ -z "$sta_channel" ]; then
        log "WARNING: $WIFI_IF not connected yet - the AP starts on channel $AP_CHANNEL and openj5-channel-sync will follow the STA channel once connected. PIN the router's 2.4 GHz channel so it never hops."
    fi
    log "single-radio mode: uplink + AP share $WIFI_IF (channel sync active)"
else
    [ -d "/sys/class/net/$AP_IF" ] || die "AP interface '$AP_IF' not found - plug the USB dongle, check 'iw dev', then re-run with AP_IF=<iface>"
    if [ -z "$sta_channel" ]; then
        log "WARNING: uplink $WIFI_IF not connected yet (AP works anyway, no internet sharing until it is)"
    fi
    log "dedicated-radio mode: uplink $WIFI_IF (free for 5 GHz) + AP on $AP_IF (channel $AP_CHANNEL fixed)"
fi

# ------------------------------------------------------------
# Packages
# ------------------------------------------------------------
step "Packages (hostapd, dnsmasq, iw)"
sudo apt-get update -qq
sudo apt-get install -y -qq hostapd dnsmasq iw iptables

# Dedicated radio: the dongle must support AP mode (iw is available only now).
if [ "$AP_IF" != "ap0" ]; then
    phy="$(readlink -f "/sys/class/net/$AP_IF/phy80211" 2>/dev/null || true)"
    if [ -z "$phy" ] || ! iw phy "$(basename "$phy")" info 2>/dev/null \
            | grep -Eq '^[[:space:]]*\*[[:space:]]+AP([[:space:]]|$)'; then
        die "$AP_IF does not support AP mode (driver/dongle) - the hotspot cannot run on it. Check: iw phy \$(basename \$(readlink -f /sys/class/net/$AP_IF/phy80211)) info | grep -A12 'Supported interface modes'"
    fi
fi

# ------------------------------------------------------------
# Configuration files
# ------------------------------------------------------------
step "Configuration files"
sudo tee "$HOTSPOT_CONF" >/dev/null <<EOF
# Generated by scripts/deploy/setup_hotspot.sh - do not edit (re-run instead).
# 0600 root: holds the WPA2 passphrase. Single-radio mode: the channel is
# kept equal to the STA uplink channel by openj5-channel-sync. Dedicated
# radio: it stays at the fixed AP_CHANNEL.
interface=$AP_IF
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$AP_CHANNEL
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSPHRASE
rsn_pairwise=CCMP
EOF
sudo chmod 600 "$HOTSPOT_CONF"

sudo tee "$DNSMASQ_CONF" >/dev/null <<EOF
# Generated by scripts/deploy/setup_hotspot.sh - do not edit (re-run instead).
# Robot LAN for the ESP nodes: DHCP + DNS on $AP_IF ONLY (interface= keeps
# this server off the home LAN). The firmware's default broker is a hostname
# (Kconfig OPENJ5_MQTT_HOST): resolve it to this Pi - mosquitto publishes
# 8883 on 0.0.0.0, so it answers on the AP interface as well.
interface=$AP_IF
except-interface=lo
bind-dynamic
dhcp-range=$DHCP_START,$DHCP_END,$NETMASK,12h
dhcp-option=option:router,$AP_IP
dhcp-option=option:dns-server,$AP_IP
address=/$MQTT_HOST/$AP_IP
# External names go upstream; the robot LAN itself keeps working offline.
no-resolv
server=$DNS_UPSTREAM
# /etc/hosts OVERRIDES address= for individual names (dnsmasq man), and Debian
# puts "127.0.1.1 <hostname>" there - keep dnsmasq off it so $MQTT_HOST wins.
no-hosts
EOF

# Debian ships conf-dir commented out in /etc/dnsmasq.conf: make sure drop-ins load.
if ! sudo grep -Eq '^[[:space:]]*conf-dir=/etc/dnsmasq\.d' /etc/dnsmasq.conf 2>/dev/null; then
    log "enabling conf-dir=/etc/dnsmasq.d in /etc/dnsmasq.conf"
    printf '\n# OpenJ5: load drop-ins (setup_hotspot.sh)\nconf-dir=/etc/dnsmasq.d/,*.conf\n' \
        | sudo tee -a /etc/dnsmasq.conf >/dev/null
fi
sudo dnsmasq --test >/dev/null || die "dnsmasq rejected the config (journalctl -u dnsmasq)"

echo 'net.ipv4.ip_forward=1' | sudo tee "$SYSCTL_CONF" >/dev/null

# ------------------------------------------------------------
# Helper scripts + systemd units
# ------------------------------------------------------------
step "Systemd units"
sudo tee "$LIB_DIR/openj5-ap-if" >/dev/null <<EOF
#!/usr/bin/env bash
# Created by setup_hotspot.sh: AP interface up, unmanaged by NetworkManager.
set -euo pipefail
rfkill unblock wifi 2>/dev/null || true
for _ in \$(seq 1 30); do [ -d "/sys/class/net/$WIFI_IF" ] && break; sleep 1; done
if [ "$AP_IF" = ap0 ]; then
    # single-radio mode: virtual AP interface on top of the uplink radio
    ip link show "$AP_IF" >/dev/null 2>&1 || iw dev "$WIFI_IF" interface add "$AP_IF" type __ap
else
    # dedicated radio (USB dongle): wait for enumeration + driver probe first
    for _ in \$(seq 1 40); do [ -d "/sys/class/net/$AP_IF" ] && break; sleep 1; done
    [ -d "/sys/class/net/$AP_IF" ] || { echo "openj5-ap-if: $AP_IF missing after 40s (dongle not enumerated? check lsusb / powered port)"; exit 1; }
    # drop the orphan virtual AP iface left by a previous single-radio install
    if [ -d /sys/class/net/ap0 ]; then
        ip link set ap0 down 2>/dev/null || true
        iw dev ap0 del 2>/dev/null || true
    fi
fi
# NetworkManager must release the iface BEFORE it gets its address: NM
# auto-manages new wifi ifaces within ~600 ms and flushes addresses it did
# not assign (observed: ap0 lost 192.168.4.1 right after creation).
if command -v nmcli >/dev/null 2>&1; then
    for _ in \$(seq 1 10); do
        nmcli dev set "$AP_IF" managed no >/dev/null 2>&1 && break
        sleep 1
    done
fi
if ! err="\$(ip link set "$AP_IF" up 2>&1)"; then
    echo "openj5-ap-if: cannot bring $AP_IF up: \$err"
    rfkill list 2>/dev/null || true
    exit 1
fi
# The AP needs its address (gateway/DNS for the ESP LAN): dnsmasq only hands
# out leases and answers $MQTT_HOST on this IP.
ip addr replace "$AP_IP/$AP_PREFIX" dev "$AP_IF"
EOF
sudo chmod 755 "$LIB_DIR/openj5-ap-if"

sudo tee "$LIB_DIR/openj5-nat" >/dev/null <<EOF
#!/usr/bin/env bash
# Created by setup_hotspot.sh: share the $WIFI_IF uplink with the hotspot.
set -euo pipefail
sysctl -q -p $SYSCTL_CONF
add() { iptables -C "\$@" 2>/dev/null || iptables -A "\$@"; }
add FORWARD -i "$AP_IF" -o "$WIFI_IF" -j ACCEPT
add FORWARD -i "$WIFI_IF" -o "$AP_IF" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -C POSTROUTING -o "$WIFI_IF" -j MASQUERADE 2>/dev/null \\
    || iptables -t nat -A POSTROUTING -o "$WIFI_IF" -j MASQUERADE
EOF
sudo chmod 755 "$LIB_DIR/openj5-nat"

if [ "$AP_IF" = "ap0" ]; then
    sudo tee "$LIB_DIR/openj5-channel-sync" >/dev/null <<EOF
#!/usr/bin/env bash
# Created by setup_hotspot.sh: keep hostapd on the STA channel (single radio).
set -euo pipefail
CONF=$HOTSPOT_CONF
[ -f "\$CONF" ] || exit 0
sta="\$(iw dev $WIFI_IF info 2>/dev/null | awk '\$1 == "channel" {print \$2}' || true)"
[ -n "\$sta" ] || exit 0                      # STA not connected: keep current channel
[ "\$sta" -le 14 ] 2>/dev/null \\
    || { echo "openj5-channel-sync: STA on 5 GHz (channel \$sta), 2.4 GHz AP impossible"; exit 0; }
ap="\$(awk -F= '/^channel=/ {print \$2}' "\$CONF")"
if [ "\$sta" != "\$ap" ]; then
    sed -i "s/^channel=.*/channel=\$sta/" "\$CONF"
    systemctl try-restart openj5-hostapd.service || true
fi
EOF
    sudo chmod 755 "$LIB_DIR/openj5-channel-sync"
else
    # Dedicated radio: the AP channel is independent - remove/never re-enable sync.
    sudo systemctl disable --now openj5-channel-sync.timer 2>/dev/null || true
    sudo rm -f "$LIB_DIR/openj5-channel-sync" \
        "$UNIT_DIR/openj5-channel-sync.service" "$UNIT_DIR/openj5-channel-sync.timer"
fi

sudo tee "$UNIT_DIR/openj5-ap-if.service" >/dev/null <<EOF
[Unit]
Description=OpenJ5 hotspot - create the $AP_IF virtual AP interface
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=120
ExecStart=$LIB_DIR/openj5-ap-if

[Install]
WantedBy=multi-user.target
EOF

sudo tee "$UNIT_DIR/openj5-hostapd.service" >/dev/null <<EOF
[Unit]
Description=OpenJ5 hotspot - hostapd on $AP_IF
Requires=openj5-ap-if.service
After=openj5-ap-if.service network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/sbin/hostapd $HOTSPOT_CONF
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee "$UNIT_DIR/openj5-nat.service" >/dev/null <<EOF
[Unit]
Description=OpenJ5 hotspot - ip_forward + NAT to $WIFI_IF
Requires=openj5-ap-if.service
After=openj5-ap-if.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$LIB_DIR/openj5-nat

[Install]
WantedBy=multi-user.target
EOF

if [ "$AP_IF" = "ap0" ]; then
    sudo tee "$UNIT_DIR/openj5-channel-sync.service" >/dev/null <<EOF
[Unit]
Description=OpenJ5 hotspot - sync hostapd channel with the STA uplink

[Service]
Type=oneshot
ExecStart=$LIB_DIR/openj5-channel-sync
EOF

    sudo tee "$UNIT_DIR/openj5-channel-sync.timer" >/dev/null <<EOF
[Unit]
Description=OpenJ5 hotspot - channel sync every minute (router may hop)

[Timer]
OnBootSec=20s
OnUnitActiveSec=60s
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
fi

# ------------------------------------------------------------
# Enable + start (single radio: channel sync BEFORE hostapd, no restart loop)
# ------------------------------------------------------------
step "Enable services"
sudo systemctl daemon-reload
# explicit enable+restart: a re-run (e.g. ap0 -> dongle switch) must re-execute
# the helpers and reload the regenerated configs, enable --now alone would not.
sudo systemctl enable openj5-ap-if.service
sudo systemctl restart openj5-ap-if.service
if [ "$AP_IF" = "ap0" ]; then
    sudo "$LIB_DIR/openj5-channel-sync" || true
    sudo systemctl enable --now openj5-channel-sync.timer
else
    log "dedicated radio: AP channel fixed at $AP_CHANNEL, channel sync not needed"
fi
sudo systemctl enable openj5-hostapd.service
sudo systemctl restart openj5-hostapd.service
sudo systemctl enable openj5-nat.service
sudo systemctl restart openj5-nat.service
sudo systemctl enable dnsmasq.service 2>/dev/null || true
sudo systemctl restart dnsmasq.service || die "dnsmasq failed to start (journalctl -u dnsmasq)"

# ------------------------------------------------------------
# Verification
# ------------------------------------------------------------
step "Verification"
if [ -d "/sys/class/net/$AP_IF" ]; then
    log "$AP_IF: up (channel $(iw dev "$AP_IF" info 2>/dev/null | awk '$1 == "channel" {print $2}' || echo '?'))"
else
    log "WARNING: $AP_IF missing - check 'systemctl status openj5-ap-if'"
fi
sudo systemctl is-active --quiet openj5-hostapd.service \
    && log "hostapd: active" \
    || log "WARNING: hostapd not active - 'journalctl -u openj5-hostapd -e' (channel mismatch?)"
sudo systemctl is-active --quiet dnsmasq.service \
    && log "dnsmasq: active (DHCP $DHCP_START-$DHCP_END, DNS $MQTT_HOST -> $AP_IP)" \
    || log "WARNING: dnsmasq not active - 'journalctl -u dnsmasq -e'"
log "verify DNS:  dig +short @$AP_IP $MQTT_HOST   (must answer $AP_IP)"
log "verify addr: hostname -I   (must include $AP_IP)"

log ""
log "Done. Next:"
log "  - ESP side: cd firmware/node7_balance && cp sdkconfig.local.example sdkconfig.local"
log "    then set SSID='$SSID' and the passphrase (never committed)."
if [ "$AP_IF" = "ap0" ]; then
    log "  - Router: PIN the 2.4 GHz channel (the AP follows the uplink channel; a hop breaks the AP until the sync timer catches it)."
else
    log "  - AP channel fixed at $AP_CHANNEL on $AP_IF (uplink $WIFI_IF independent - change anytime with AP_CHANNEL= and a re-run)."
fi
log "  - ufw (DEPLOYMENT.md section 10): allow the hotspot subnet for SSH, e.g."
log "      sudo ufw allow from $SUBNET.0/24 to any port 22 proto tcp"
log "Full guide: docs/deployment/DEPLOYMENT.md section 11"
