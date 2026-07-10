#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

# Run all MQTT integration scripts against a live sign.
#
# Usage:
#   export BROKER=mqtt.example.com
#   export PREFIX=givemeasign          # optional
#   export SIGN=givemeasign/sign/aa_bb_cc_dd_ee_ff   # required for some tests
#   ./tests/mqtt/run_all.sh
#
# Set SKIP_REBOOT=1 to skip test_reset.sh (which reboots the sign).

set -e

dir="$(dirname "$0")"

run() {
    script="$1"
    echo "=== ${script} ==="
    sh "${dir}/${script}"
}

run test_message.sh
run test_greet.sh
run test_weather.sh
run test_aqi.sh
run test_uv.sh
run test_pollen.sh
run test_tones.sh
run test_times.sh
run test_timezone_offsets.sh

if [ -n "${SIGN}" ]; then
    run test_data.sh
    run test_display.sh
    run test_info.sh
    if [ -z "${SKIP_REBOOT}" ]; then
        run test_reset.sh
    else
        echo "=== test_reset.sh (skipped, SKIP_REBOOT is set) ==="
    fi
else
    echo "=== SIGN not set: skipping test_data.sh, test_display.sh, test_info.sh, test_reset.sh ==="
fi

echo "MQTT integration scripts finished."
