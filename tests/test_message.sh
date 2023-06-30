#!/bin/sh

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

curl -X POST -H "Content-Type: application/json" -d '{ "text": "Red alert!", "color": 16711680 }' http://$IP/message
