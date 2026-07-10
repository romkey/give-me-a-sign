#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

# Publish sample payloads, then ask the sign to dump its Data store over MQTT.
# Requires SIGN so the dump can be requested and observed on data/state.

set -e
. "$(dirname "$0")/_common.sh"

: "${SIGN:?Set SIGN to the sign topic base (givemeasign/sign/MAC_with_underscores)}"

echo "Publishing sample payloads..."
publish_all aqi '{"aqi": 58}'
publish_all uv '{"index": 5}'
publish_all message '{"text": "data probe", "color": 65280}'
sleep 2

echo "Requesting full data store dump..."
publish_sign data/publish publish

echo "Listening for ${SIGN}/data/state (5s)..."
# shellcheck disable=SC2086
timeout 5 ${MOSQUITTO_SUB} -t "${SIGN}/data/state" -C 1 -W 5 || true

echo "Expect JSON containing aqi/uv/message keys on ${SIGN}/data/state."
