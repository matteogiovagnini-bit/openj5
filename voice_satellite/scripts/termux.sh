#!/bin/bash
# Connessione SSH al Termux del Samsung Note 10 (via Wi-Fi)
# Uso: ./termux.sh <comando>   oppure   ./termux.sh  (shell interattiva)
SRC_HOST="${TERMUX_HOST:-192.168.1.107}"
SRC_USER="u0_a1382"
SRC_PORT="8022"

exec ssh -p "$SRC_PORT" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$SRC_USER@$SRC_HOST" "$@"