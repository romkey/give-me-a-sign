#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

set -e
. "$(dirname "$0")/_common.sh"

# busy signal
publish_all tones \
    '{"tones": [
        {"frequency": 480, "duration": 0.5, "volume": 100},
        {"frequency": 620, "duration": 0.5, "volume": 100},
        {"frequency": 480, "duration": 0.5, "volume": 100},
        {"frequency": 620, "duration": 0.5, "volume": 100},
        {"frequency": 480, "duration": 0.5, "volume": 100},
        {"frequency": 620, "duration": 0.5, "volume": 100},
        {"frequency": 480, "duration": 0.5, "volume": 100},
        {"frequency": 620, "duration": 0.5, "volume": 100},
        {"frequency": 480, "duration": 0.5, "volume": 100},
        {"frequency": 620, "duration": 0.5, "volume": 100},
        {"frequency": 480, "duration": 0.5, "volume": 100},
        {"frequency": 620, "duration": 0.5, "volume": 100}
    ]}'
