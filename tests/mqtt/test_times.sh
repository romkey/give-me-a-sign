#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

# Exercise clock solar colors using timestamps relative to the current time,
# and optionally set the device clock via MQTT time/set when SIGN is set.

set -e
. "$(dirname "$0")/_common.sh"

now="$(now_epoch)"
hour=3600

if [ -n "${SIGN}" ]; then
    echo "Set device time via MQTT (ISO 8601 UTC)..."
    # Use a known epoch so the clock visibly jumps, then restore roughly-now
    publish_sign time/set '{"epoch": 1700000000}'
    sleep 5
    echo "Restore device time to approximately now..."
    publish_sign time/set "${now}"
    sleep 3
fi

echo "Test daytime (clock should be green)..."
publish_all solar \
    "$(printf '{"sunrise": %s, "sunset": %s}' "$((now - 4 * hour))" "$((now + 4 * hour))")"
sleep 10

echo "Test night (clock should be red)..."
publish_all solar \
    "$(printf '{"sunrise": %s, "sunset": %s}' "$((now + 10 * hour))" "$((now - 2 * hour))")"
sleep 10

echo "Test pre-sunset (clock should be orange)..."
publish_all solar \
    "$(printf '{"sunrise": %s, "sunset": %s}' "$((now - 4 * hour))" "$((now + 30 * 60))")"
sleep 10

echo "Test pre-sunrise (clock should be blue)..."
publish_all solar \
    "$(printf '{"sunrise": %s, "sunset": %s}' "$((now + 30 * 60))" "$((now + 8 * hour))")"
sleep 10

echo "Test Home Assistant next-event ordering during the day (clock should be green)..."
publish_all solar \
    "$(printf '{"sunrise": %s, "sunset": %s}' "$((now + 20 * hour))" "$((now + 6 * hour))")"
sleep 10
