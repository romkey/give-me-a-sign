# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for AQI color thresholds."""

from give_me_a_sign.aqi import AQI


def test_aqi_color_boundaries():
    assert AQI._aqi_color(50) == 0x00FF00
    assert AQI._aqi_color(51) == 0xFFFF00
    assert AQI._aqi_color(100) == 0xFFFF00
    assert AQI._aqi_color(101) == 0xFFA500
    assert AQI._aqi_color(150) == 0xFFA500
    assert AQI._aqi_color(151) == 0xFF0000
    assert AQI._aqi_color(200) == 0xFF0000
    assert AQI._aqi_color(201) == 0x800080
    assert AQI._aqi_color(300) == 0x800080
    assert AQI._aqi_color(301) == 0x800000
