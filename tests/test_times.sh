#!/bin/sh

# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

echo "Test sunrise..."
curl -X POST -d '{ "time": 1685394000 }' http://$IP/set-time

echo "...should be green"
curl -X POST -d '{ "sunrise": 1685393000, "sunset": 1685405000}' http://$IP/solar

sleep 10

echo "...should be red"
curl -X POST -d '{ "time": 1685406000 }' http://$IP/set-time
sleep 10

echo "...should be orange (hour up to dusk) and then red"
curl -X POST -d '{ "time": 1685404990 }' http://$IP/set-time
sleep 10

echo "...should be blue (hour up to dawn) and then green"
curl -X POST -d '{ "time": 1685392990 }' http://$IP/set-time
sleep 10

echo "...should jump ahead an hour"
curl -X POST -d '{ "time": 1710064790 }' http://$IP/set-time
sleep 15

echo "...should drop behind an hour"
curl -X POST -d '{ "time": 1730624390 }' http://$IP/set-time
sleep 15
