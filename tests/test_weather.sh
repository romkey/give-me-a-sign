#!/bin/bash

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

curl -X POST -H "Content-Type: application/json" -d '{ "current": { "conditions": "bogon", "temperature": 79, "humidity": 45 }, "forecast": { "high": 81, "low": 55, "humidity": 48 } }' http://$IP/weather
echo "bogon"
sleep 30

curl -X POST -H "Content-Type: application/json" -d '{ "current": { "conditions": "sunny", "temperature": 79, "humidity": 45 }, "forecast": { "high": 81, "low": 55, "humidity": 48 } }' http://$IP/weather
echo "sunny"

sleep 30

curl -X POST -H "Content-Type: application/json" -d '{ "current": { "conditions": "cloudy", "temperature": 79, "humidity": 45 }, "forecast": { "high": 81, "low": 55, "humidity": 48 } }' http://$IP/weather
echo "cloudy"

sleep 30

curl -X POST -H "Content-Type: application/json" -d '{ "current": { "conditions": "partlycloudy", "temperature": 79, "humidity": 45 }, "forecast": { "high": 81, "low": 55, "humidity": 48 } }' http://$IP/weather
echo "partlycloudy"

sleep 30

curl -X POST -H "Content-Type: application/json" -d '{ "current": { "conditions": "clear-night", "temperature": 79, "humidity": 45 }, "forecast": { "high": 81, "low": 55, "humidity": 48 } }' http://$IP/weather
echo "clear-night"

sleep 30
