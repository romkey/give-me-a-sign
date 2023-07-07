#!/bin/bash

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

curl -X POST -H 'Content-type: application/json' --data-binary "@timezone-offsets.json" "http://$IP/timezone"
