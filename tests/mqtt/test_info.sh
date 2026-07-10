#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

# Wait for one diagnostics JSON payload (replaces the old GET /info HTTP test).

set -e
. "$(dirname "$0")/_common.sh"

: "${SIGN:?Set SIGN to the sign topic base (givemeasign/sign/MAC_with_underscores)}"

echo "Waiting for one message on ${SIGN}/diagnostics (timeout 90s)..."
${MOSQUITTO_SUB} -t "${SIGN}/diagnostics" -C 1 -W 90
