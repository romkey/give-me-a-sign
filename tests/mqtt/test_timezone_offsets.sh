#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

set -e
. "$(dirname "$0")/_common.sh"

now="$(now_epoch)"
payload="$(printf \
    '{"timezone": "America/Los_Angeles", "transitions": [{"timestamp": %s, "offset": -28800}, {"timestamp": %s, "offset": -25200}]}' \
    "$((now - 86400))" "$((now + 86400))")"

publish_all timezone "${payload}"
