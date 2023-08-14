#!/bin/sh

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT


curl -X POST -H "Content-Type: application/json" -d '{ "person": "Random X Hacker", "door": "front" }' "http://$IP/greet"
sleep 20
curl -X POST -H "Content-Type: application/json" -d '{ "person": "Person A.", "door": "front" }' "http://$IP/greet"
sleep 20
