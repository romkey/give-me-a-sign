#!/bin/sh

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

# busy signal
curl -X POST -H "Content-Type: application/json" -d '{ "tones": [ { "frequency": 480, "duration": 0.5, "volume": 100 }, { "frequency": 620, "duration": 0.5, "volume": 100 }, { "frequency": 480, "duration": 0.5, "volume": 100 }, { "frequency": 620, "duration": 0.5, "volume": 100 },{ "frequency": 480, "duration": 0.5, "volume": 100 }, { "frequency": 620, "duration": 0.5, "volume": 100 },{ "frequency": 480, "duration": 0.5, "volume": 100 }, { "frequency": 620, "duration": 0.5, "volume": 100 },{ "frequency": 480, "duration": 0.5, "volume": 100 }, { "frequency": 620, "duration": 0.5, "volume": 100 },{ "frequency": 480, "duration": 0.5, "volume": 100 }, { "frequency": 620, "duration": 0.5, "volume": 100 } ] }' http://$IP/tones
