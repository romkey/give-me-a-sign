# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for weather helper methods."""

from give_me_a_sign.weather import Weather


def test_image_stem_icon_wins():
    current = {"icon": "01n", "condition_id": 800}
    assert Weather._image_stem(current) == "01n"


def test_image_stem_condition_id_mapping():
    current = {"condition_id": 500}
    assert Weather._image_stem(current) == "10d"


def test_image_stem_numeric_conditions():
    assert Weather._image_stem({"conditions": 200}) == "11d"
    assert Weather._image_stem({"conditions": 200.0}) == "11d"
    assert Weather._image_stem({"conditions": "500"}) == "10d"


def test_image_stem_legacy_name():
    current = {"conditions": "Partly Cloudy"}
    assert Weather._image_stem(current) == "02d"


def test_image_stem_unknown_string():
    current = {"conditions": "nosuchthing"}
    assert Weather._image_stem(current) == "nosuchthing"


def test_image_stem_default():
    assert Weather._image_stem({}) == "50d"


def test_temp_color_boundaries():
    assert Weather._temp_color(49) == 0x0000FF
    assert Weather._temp_color(50) == 0x0D98BA
    assert Weather._temp_color(69) == 0x0D98BA
    assert Weather._temp_color(70) == 0x00FF00
    assert Weather._temp_color(79) == 0x00FF00
    assert Weather._temp_color(80) == 0xFFA500
    assert Weather._temp_color(89) == 0xFFA500
    assert Weather._temp_color(90) == 0xFF0000


def test_forecast_text_with_forecast():
    text = Weather._forecast_text({"low": 55, "high": 79}, 45)
    assert text == "45% 55->79"


def test_forecast_text_without_forecast():
    assert Weather._forecast_text(None, 45) == "45%"
    assert Weather._forecast_text({"low": "x"}, 45) == "45%"
