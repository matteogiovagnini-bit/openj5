#!/bin/sh
# OpenJ5 host tests for the pure firmware logic (stepper math, Madgwick,
# ADR-009 state machine, Node 7 balance PID). No ESP-IDF needed: any C++20
# compiler works. Run in CI (firmware-host-tests job) and before closing any
# firmware session.
set -e

cd "$(dirname "$0")/../.."

CXX="${CXX:-c++}"
OUT="${TMPDIR:-/tmp}/openj5_host_firmware_test"

echo "Compiling host firmware tests with: $($CXX --version | head -1)"
$CXX -std=c++20 -Wall -Wextra -Werror -O2 \
    -Ifirmware/common/include \
    firmware/common/test/host_test.cpp \
    firmware/common/imu/madgwick.cpp \
    firmware/common/statemachine/state_machine.cpp \
    -o "$OUT"

"$OUT"
echo "host_firmware OK"
