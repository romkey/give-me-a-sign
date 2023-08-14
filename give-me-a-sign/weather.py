# SPDX-FileCopyrightText: 2023 John Romkey
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

    def show(self) -> bool:
        """
        Display the current weather conditions if valid.

        Conditions are stored in Data under the key "weather"

        Data structure should look like:

        .. code-block:: python
        current weather:
           {
             conditions: 'sunny|cloudy|rain|thunder|snow',
             temperature: 79,
             humidity: 45,
             pressure: 1112
           }
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

        image_filename = f"/assets/w/{weather['current']['conditions']}.bmp"

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
            high_low_text = adafruit_display_text.label.Label(
                terminalio.FONT,
                color=0x00FF00,
                text=f'{int(weather["current"]["humidity"])}% {int(weather["forecast"]["low"])}->{int(weather["forecast"]["high"])}',  # pylint: disable=line-too-long
            )
        except KeyError:
            return False

        high_low_text.x = 0
        high_low_text.y = 24
        group.append(high_low_text)

        self._app.display.show(group)
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
