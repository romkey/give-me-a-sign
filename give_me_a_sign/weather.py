# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/weather - weather module for LED Matrix display
==============================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import adafruit_imageload
import displayio
import terminalio

from ._paths import ASSETS_DIR
from .complication import (
    EIGHTH,
    FULL,
    HALF_WIDE,
    QUARTER,
    Complication,
    place_top,
)
from .module import SignModule

OWM_ID_TO_ICON = {
    200: "11d",
    201: "11d",
    202: "11d",
    210: "11d",
    211: "11d",
    212: "11d",
    221: "11d",
    230: "11d",
    231: "11d",
    232: "11d",
    300: "09d",
    301: "09d",
    302: "09d",
    310: "09d",
    311: "09d",
    312: "09d",
    313: "09d",
    314: "09d",
    321: "09d",
    500: "10d",
    501: "10d",
    502: "10d",
    503: "10d",
    504: "10d",
    511: "13d",
    520: "09d",
    521: "09d",
    522: "09d",
    531: "09d",
    600: "13d",
    601: "13d",
    602: "13d",
    611: "13d",
    612: "13d",
    613: "13d",
    615: "13d",
    616: "13d",
    620: "13d",
    621: "13d",
    622: "13d",
    701: "50d",
    711: "50d",
    721: "50d",
    731: "50d",
    741: "50d",
    751: "50d",
    761: "50d",
    762: "50d",
    771: "50d",
    781: "50d",
    800: "01d",
    801: "02d",
    802: "03d",
    803: "04d",
    804: "04d",
}

_LEGACY_CONDITIONS_ICON = {
    "sunny": "01d",
    "clear": "01d",
    "clearnight": "01n",
    "cloudy": "03d",
    "partlycloudy": "02d",
    "rain": "10d",
    "rainy": "10d",
    "lightrain": "10d",
    "pouring": "09d",
    "thunder": "11d",
    "lightning": "11d",
    "lightningrainy": "11d",
    "thunderstorm": "11d",
    "snow": "13d",
    "snowyrainy": "13d",
    "hail": "13d",
    "mist": "50d",
    "fog": "50d",
    "windy": "50d",
    "windyvariant": "50d",
    "exceptional": "50d",
}


class Weather(SignModule):
    """
    Manages the display of weather conditions and forecast.
    """

    NAME = "weather"
    KEY = "weather"
    ENDPOINTS = ("weather", "forecast")
    STALE_SECONDS = 60 * 60

    def __init__(self, app):
        super().__init__(app)
        self._complications = None

    @staticmethod
    def _image_stem(current) -> str:
        icon = current.get("icon")
        if isinstance(icon, str):
            stem = icon.strip().lower()
            if len(stem) == 3 and stem[:2].isdigit() and stem[2] in ("d", "n"):
                return stem

        cid = current.get("condition_id")
        raw = current.get("conditions")
        if cid is None and isinstance(raw, int):
            cid = raw
        if cid is None and isinstance(raw, float) and raw == int(raw):
            cid = int(raw)
        if cid is None and isinstance(raw, str) and raw.isdigit():
            cid = int(raw)

        if cid is not None:
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                cid = None
            else:
                mapped = OWM_ID_TO_ICON.get(cid)
                if mapped is not None:
                    return mapped

        if isinstance(raw, str):
            key = raw.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
            if key in _LEGACY_CONDITIONS_ICON:
                return _LEGACY_CONDITIONS_ICON[key]
            raw_stem = raw.strip().lower()
            if (
                len(raw_stem) == 3
                and raw_stem[:2].isdigit()
                and raw_stem[2] in ("d", "n")
            ):
                return raw_stem
            return raw.strip()

        return "50d"

    @staticmethod
    def _forecast_text(forecast, humidity) -> str:
        text = f"{humidity}%"
        try:
            low = int(forecast["low"])
            high = int(forecast["high"])
            text = f"{humidity}% {low}->{high}"
        except (KeyError, TypeError, ValueError):
            pass
        return text

    def should_show(self) -> bool:
        if not self.store.has_item("weather"):
            return False
        if (
            self.STALE_SECONDS is not None
            and self.store.age("weather") > self.STALE_SECONDS
        ):
            return False
        return True

    def _current_data(self):
        weather = self.store.get_item("weather")
        forecast = self.store.get_item("forecast")
        if not isinstance(weather, dict) or not isinstance(
            weather.get("current"), dict
        ):
            return None, None, None

        current = weather["current"]
        try:
            temperature = int(current["temperature"])
            humidity = int(current["humidity"])
        except (KeyError, TypeError, ValueError):
            return None, None, None

        return current, forecast, (temperature, humidity)

    def _append_icon(self, group, current, x=0, y=0):
        image_filename = f"{ASSETS_DIR}/w/{Weather._image_stem(current)}.bmp"
        try:
            bitmap, palette = adafruit_imageload.load(
                image_filename,
                bitmap=displayio.Bitmap,
                palette=displayio.Palette,
            )
            tile_group = displayio.TileGrid(bitmap, pixel_shader=palette)
            tile_group.x = x
            tile_group.y = y
            group.append(tile_group)
            return True
        except OSError:
            print(f"weather conditions {image_filename} - file not found")
        except NotImplementedError:
            self._app.logger.error(f"Image {image_filename} unsupported")
        return False

    def _build_group(self, layout):
        current, forecast, values = self._current_data()
        if current is None:
            return None

        temperature, humidity = values
        group = displayio.Group()

        if layout == "full":
            self._append_icon(group, current)
            temp_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=Weather._temp_color(temperature),
                text=str(temperature),
            )
            temp_text.x = 40
            temp_text.y = 10
            group.append(temp_text)
            forecast_text = Weather._forecast_text(forecast, humidity)
            high_low_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=0x00FF00,
                text=forecast_text,
            )
            high_low_text.x = 0
            high_low_text.y = 24
            group.append(high_low_text)
        elif layout == "half":
            self._append_icon(group, current)
            temp_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=Weather._temp_color(temperature),
                text=str(temperature),
            )
            temp_text.x = 40
            temp_text.y = 4
            group.append(temp_text)
        elif layout == "quarter":
            self._append_icon(group, current, x=0, y=0)
            temp_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=Weather._temp_color(temperature),
                text=str(temperature),
            )
            temp_text.x = 18
            temp_text.y = 8
            group.append(temp_text)
        elif layout == "temp8":
            temp_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=Weather._temp_color(temperature),
                text=f"{temperature}F",
            )
            temp_text.x = 0
            place_top(temp_text)
            group.append(temp_text)
        elif layout == "humidity8":
            label = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=0x00FF00,
                text=f"{humidity}%",
            )
            label.x = 0
            place_top(label)
            group.append(label)

        return group

    def show(self) -> bool:
        self.store.clear_updated("weather")
        self.store.clear_updated("forecast")
        group = self._build_group("full")
        if group is None:
            return False
        self._app.show_group(group)
        return True

    @staticmethod
    def _temp_color(temp) -> int:
        if temp < 50:
            return 0x0000FF
        if temp < 70:
            return 0x0D98BA
        if temp > 89:
            return 0xFF0000
        if temp > 79:
            return 0xFFA500
        return 0x00FF00

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication(
                    "full", FULL[0], FULL[1], lambda: self._build_group("full")
                ),
                Complication(
                    "half",
                    HALF_WIDE[0],
                    HALF_WIDE[1],
                    lambda: self._build_group("half"),
                ),
                Complication(
                    "quarter",
                    QUARTER[0],
                    QUARTER[1],
                    lambda: self._build_group("quarter"),
                ),
                Complication(
                    "temp8", EIGHTH[0], EIGHTH[1], lambda: self._build_group("temp8")
                ),
                Complication(
                    "humidity8",
                    EIGHTH[0],
                    EIGHTH[1],
                    lambda: self._build_group("humidity8"),
                ),
            ]
        return self._complications
