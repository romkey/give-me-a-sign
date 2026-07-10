#!/bin/sh
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

set -e
. "$(dirname "$0")/_common.sh"

publish_sign display/set OFF
sleep 5
publish_sign display/set ON
