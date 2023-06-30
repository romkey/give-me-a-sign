#!/bin/bash

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

curl -X POST -H "Content-Type: application/json" -d '{ "aqi": 58 }' http://$IP/aqi
