#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

set -e
. "$(dirname "$0")/_common.sh"

FORECAST='{"low": 55, "high": 81}'

publish_all weather \
    '{"current": {"conditions": "bogon", "temperature": 79, "humidity": 45}}'
publish_all forecast "${FORECAST}"
echo "bogon"
sleep 30

publish_all weather \
    '{"current": {"conditions": "sunny", "temperature": 79, "humidity": 45}}'
publish_all forecast "${FORECAST}"
echo "sunny"
sleep 30

publish_all weather \
    '{"current": {"conditions": "cloudy", "temperature": 79, "humidity": 45}}'
publish_all forecast "${FORECAST}"
echo "cloudy"
sleep 30

publish_all weather \
    '{"current": {"conditions": "partlycloudy", "temperature": 79, "humidity": 45}}'
publish_all forecast "${FORECAST}"
echo "partlycloudy"
sleep 30

publish_all weather \
    '{"current": {"conditions": "clearnight", "temperature": 79, "humidity": 45}}'
publish_all forecast "${FORECAST}"
echo "clearnight"
sleep 30
