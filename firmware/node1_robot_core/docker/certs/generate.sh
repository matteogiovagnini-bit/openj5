#!/usr/bin/env bash
#
# OpenJ5 TLS Certificate Generation Script
#
# Generates all certificates required by docker-compose.yml:
#   - Certificate Authority (ca.crt, ca.key)
#   - Mosquitto broker cert (mosquitto.crt, mosquitto.key)
#   - Node certificates node1-node6 (nodeN.crt, nodeN.key)
#   - API certificate (api.crt, api.key)
#   - ROS2 bridge certificate (rosbridge.crt, rosbridge.key)
#   - JWT signing keys (jwt_private.pem, jwt_public.pem)
#
# Usage:
#   bash certs/generate.sh                 # interactive
#   bash certs/generate.sh --force         # overwrite existing certs
#   bash certs/generate.sh --quiet         # no prompts, auto-answers
#
# Run from: firmware/node1_robot_core/docker/

set -euo pipefail

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAYS_CA=3650
DAYS_LEAF=825
KEY_BITS=2048
COUNTRY="IT"
STATE="Italy"
LOCALITY="Rome"
ORG="OpenJ5"
ORG_UNIT="Robot Core"
COMMON_NAME="openj5.local"

FORCE=0
QUIET=0

for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --quiet) QUIET=1 ;;
    esac
done

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

log() { printf "\033[1;34m[openj5]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[openj5]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[openj5]\033[0m ERROR: %s\n" "$*"; exit 1; }

prompt_yes() {
    [ "$QUIET" -eq 1 ] && return 0
    local answer
    read -r -p "$1 [y/N] " answer
    [[ "$answer" =~ ^[Yy]$ ]]
}

# ------------------------------------------------------------
# Preflight checks
# ------------------------------------------------------------

command -v openssl >/dev/null 2>&1 || die "openssl not found. Install with: sudo apt install openssl"

mkdir -p "$CERT_DIR"

# Guard: refuse to overwrite unless --force
if [ -f "$CERT_DIR/ca.crt" ] && [ "$FORCE" -eq 0 ]; then
    die "Certificates already exist in $CERT_DIR. Use --force to regenerate."
fi

# ------------------------------------------------------------
# OpenSSL config (for SANs and proper extensions)
# ------------------------------------------------------------

OPENSSL_CNF="$CERT_DIR/openssl.cnf"
cat > "$OPENSSL_CNF" <<'EOF'
[ req ]
distinguished_name = req_distinguished_name
prompt = no
req_extensions = v3_req

[ req_distinguished_name ]
C = __COUNTRY__
ST = __STATE__
L = __LOCALITY__
O = __ORG__
OU = __ORG_UNIT__
CN = __COMMON_NAME__

[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = localhost
DNS.2 = openj5.local
IP.1 = 127.0.0.1

[ v3_ca ]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF

# Substitute placeholders
sed -i \
    -e "s/__COUNTRY__/$COUNTRY/g" \
    -e "s/__STATE__/$STATE/g" \
    -e "s/__LOCALITY__/$LOCALITY/g" \
    -e "s/__ORG__/$ORG/g" \
    -e "s/__ORG_UNIT__/$ORG_UNIT/g" \
    -e "s/__COMMON_NAME__/$COMMON_NAME/g" \
    "$OPENSSL_CNF"

# ------------------------------------------------------------
# CA
# ------------------------------------------------------------

log "Generating Certificate Authority (valid ${DAYS_CA} days)"
openssl genrsa -out "$CERT_DIR/ca.key" "$KEY_BITS" 2>/dev/null
openssl req -new -x509 \
    -key "$CERT_DIR/ca.key" \
    -out "$CERT_DIR/ca.crt" \
    -days "$DAYS_CA" \
    -config "$OPENSSL_CNF" \
    -extensions v3_ca \
    -subj "/C=$COUNTRY/ST=$STATE/L=$LOCALITY/O=$ORG/OU=$ORG_UNIT/CN=OpenJ5 Root CA" \
    >/dev/null 2>&1

log "CA generated: $CERT_DIR/ca.crt"

# ------------------------------------------------------------
# Leaf certificate helper
# ------------------------------------------------------------

gen_leaf() {
    local name="$1"
    local cn="$2"

    log "Generating certificate for $cn"

    openssl genrsa -out "$CERT_DIR/$name.key" "$KEY_BITS" 2>/dev/null
    openssl req -new \
        -key "$CERT_DIR/$name.key" \
        -out "$CERT_DIR/$name.csr" \
        -config "$OPENSSL_CNF" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$LOCALITY/O=$ORG/OU=$ORG_UNIT/CN=$cn" \
        >/dev/null 2>&1

    # Generate SAN file for each leaf (include hostname)
    local san_file="$CERT_DIR/$name.san"
    cat > "$san_file" <<EOF
subjectAltName=DNS:localhost,DNS:$cn,DNS:openj5.local,IP:127.0.0.1
EOF

    openssl x509 -req \
        -in "$CERT_DIR/$name.csr" \
        -CA "$CERT_DIR/ca.crt" \
        -CAkey "$CERT_DIR/ca.key" \
        -CAcreateserial \
        -out "$CERT_DIR/$name.crt" \
        -days "$DAYS_LEAF" \
        -extfile "$san_file" \
        >/dev/null 2>&1

    rm -f "$CERT_DIR/$name.csr" "$CERT_DIR/$name.san"
    # 640 + owning group: private keys readable only by owner and group.
    # Container services run with the owner uid/gid (1000) or with gid 1000
    # (mosquitto user: 1883:1000), so bind-mounted keys stay readable without
    # world access.
    chmod 640 "$CERT_DIR/$name.key"
    log "Certificate for $cn generated"
}

# ------------------------------------------------------------
# Generate leaf certificates
# ------------------------------------------------------------

gen_leaf "mosquitto"   "mosquitto"
gen_leaf "api"         "api"
gen_leaf "rosbridge"   "rosbridge"
gen_leaf "jwt-svc"     "jwt"

for i in 1 2 3 4 5 6; do
    gen_leaf "node$i" "node$i"
done

# ------------------------------------------------------------
# JWT signing keys (RSA 2048)
# ------------------------------------------------------------

log "Generating JWT signing keys"
openssl genpkey \
    -algorithm RSA \
    -out "$CERT_DIR/jwt_private.pem" \
    -pkeyopt rsa_keygen_bits:2048 \
    >/dev/null 2>&1
openssl rsa \
    -pubout \
    -in "$CERT_DIR/jwt_private.pem" \
    -out "$CERT_DIR/jwt_public.pem" \
    >/dev/null 2>&1

chmod 600 "$CERT_DIR/jwt_private.pem"

# ------------------------------------------------------------
# Verify
# ------------------------------------------------------------

log "Verifying certificates..."
for name in ca mosquitto api rosbridge node1 node2 node3 node4 node5 node6; do
    openssl verify -CAfile "$CERT_DIR/ca.crt" "$CERT_DIR/$name.crt" >/dev/null 2>&1 \
        || warn "Verification failed for $name"
done

log "Verifying JWT keypair match..."
JWT_PUB=$(openssl rsa -pubin -in "$CERT_DIR/jwt_public.pem" -modulus -noout 2>/dev/null | openssl md5)
JWT_PRIV=$(openssl rsa -in "$CERT_DIR/jwt_private.pem" -modulus -noout 2>/dev/null | openssl md5)
[ "$JWT_PUB" = "$JWT_PRIV" ] && log "JWT keypair OK" || warn "JWT keypair mismatch!"

# ------------------------------------------------------------
# Cleanup & summary
# ------------------------------------------------------------

rm -f "$CERT_DIR/openssl.cnf" "$CERT_DIR/ca.srl"
chmod 644 "$CERT_DIR"/*.crt "$CERT_DIR"/*.pem 2>/dev/null || true

log ""
log "Certificate generation complete."
log "Generated files in: $CERT_DIR"
log "  - CA:           ca.crt / ca.key"
log "  - Broker:       mosquitto.crt / mosquitto.key"
log "  - API:          api.crt / api.key"
log "  - ROS2 bridge:  rosbridge.crt / rosbridge.key"
log "  - Nodes:        node1.crt ... node6.crt (each with .key)"
log "  - JWT:          jwt_public.pem / jwt_private.pem"
log ""
log "IMPORTANT: ca.key, all *.key and jwt_private.pem are SECRETS."
log "Store them securely and NEVER commit them to git."
log "Restart services after copying certs to host: docker compose restart"
