#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

set -e
. "$(dirname "$0")/_common.sh"

publish_all greet '{"person": "Random X Hacker", "door": "front"}'
sleep 20
publish_all greet '{"person": "Person A.", "door": "front"}'
sleep 20
