# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/weather - weather module for LED Matrix display
====================================================

* Author: John Romkey
"""

import adafruit_display_text.label
import adafruit_imageload
import displayio
import terminalio

from ._paths import ASSETS_DIR

# OpenWeatherMap ``weather[].id`` -> icon filename stem.
# See openweathermap.org/weather-conditions.
# Night clear sky uses icon ``01n`` from the API.
# Include ``"icon": "01n"`` in ``current`` when id is 800.
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
    "cloudy": "03d",
    "partlycloudy": "02d",
    "partly_cloudy": "02d",
    "rain": "10d",
    "lightrain": "10d",
    "thunder": "11d",
    "thunderstorm": "11d",
    "snow": "13d",
    "mist": "50d",
    "fog": "50d",
}


class Weather:
    """
    Manages the display of weather conditions and forecast

    The server receives weather conditions them in the Data store under the key "weather".
    This class retrieves the conditions and displays them.

    Display includes a color coded current temperature, as well as humidity,
    forecast high and low, and an image indicating current conditions (sunny, cloudy, etc).
    """

    KEY = "weather"

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        """
        self._app = app

    @staticmethod
    def _image_stem(current) -> str:
        """
        Resolve the icon stem for ``assets/w/{stem}.bmp`` (bundled under the
        ``give_me_a_sign`` package) from OpenWeatherMap-style fields or legacy names.

        Priority: ``icon`` (e.g. ``10n``), ``condition_id`` + map, numeric ``conditions``,
        legacy string ``conditions``, else literal ``conditions`` stem.
        """
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
            key = raw.strip().lower().replace(" ", "").replace("-", "")
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

    def show(self) -> bool:
        """
        Display the current weather conditions if valid.

        Conditions are stored in Data under the key "weather"

        Data structure should look like:

        .. code-block:: python
        current weather (OpenWeatherMap-friendly):
           {
             conditions: 500,
             icon: "10d",
             condition_id: 500,
             temperature: 79,
             humidity: 45,
             pressure: 1112
           }

        Use ``icon`` from the API when present (required for clear night ``01n`` vs ``01d``).
        ``conditions`` may be a legacy name (``sunny``) or numeric condition id string.
        forecast:
           {
             conditions: 'sunny|cloudy|rain|thunder|snow',
             low_temperature: 55,
             high_temperature: 79,
             humidity: 45,
             pressure: 1112
            }

        Temperatures and humidity may be floating point. Pressure is optional
        """
        weather = self._app.data.get_item("weather")
        forecast = self._app.data.get_item("forecast")
        if weather is None and forecast is None:
            return False

        self._app.data.clear_updated("weather")
        self._app.data.clear_updated("forecast")

        group = displayio.Group()

        image_filename = f"{ASSETS_DIR}/w/{Weather._image_stem(weather['current'])}.bmp"

        try:
            bitmap, palette = adafruit_imageload.load(
                image_filename,
                bitmap=displayio.Bitmap,
                palette=displayio.Palette,
            )
            tile_group = displayio.TileGrid(bitmap, pixel_shader=palette)

            group.append(tile_group)
        except OSError:
            print(f"weather conditions {image_filename} - file not found")
        except NotImplementedError:
            self._app.logger.error(f"Image {image_filename} unsupported")
            return False

        try:
            temp_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=Weather._temp_color(int(weather["current"]["temperature"])),
                text=str(int(weather["current"]["temperature"])),
            )
        except KeyError:
            return False

        temp_text.x = 40
        temp_text.y = 10
        group.append(temp_text)

        try:
            forecast_text = (
                f'{int(weather["current"]["humidity"])}% '
                f'{int(forecast["low"])}->{int(forecast["high"])}'
            )
            high_low_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=0x00FF00,
                text=forecast_text,
            )
        except KeyError:
            return False

        high_low_text.x = 0
        high_low_text.y = 24
        group.append(high_low_text)

        self._app.display.root_group = group
        return True

    @staticmethod
    def _temp_color(temp) -> int:
        """
        Returns an RGB color corresponding to the temperature

        :param int temp - temperature in degrees F
        """
        if temp < 50:
            return 0x0000FF

        if temp < 70:
            return 0x0D98BA

        if temp > 89:
            return 0xFF0000

        if temp > 79:
            return 0xFFA500

        return 0x00FF00

    def loop(self) -> None:  # pylint: disable=no-self-use
        """
        loop function does any needed incremental processing like scrolling
        not currently used or called
        """

        return
