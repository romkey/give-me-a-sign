# SPDX-FileCopyrightText: 2020 John Park for Adafruit Industries
#
# SPDX-FileCopyrightText: 2023 John Romkey
#
# SPDX-License-Identifier: MIT

# based on https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/code-the-matrix-clock

"""
give-me-a-sign/clock - clock module for LED Matrix display
====================================================

* Author: John Romkey
"""

import time

import displayio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label


class Clock:
    """
    Clock class

    - gets the current time via NTP
    - calculates the current time considering the timezone offset
    - displays the current time on the LED matrix
    """

    KEY = "clock"
    KEY_NTP = "ntp"
    KEY_TIMEZONE = "timezone"
    KEY_SOLAR = "solar"

    DEFAULT_NTP_REFRESH_INTERVAL = 60 * 60 * 6
    DEFAULT_COLOR = 0x00FF00

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        :param ntp_socket_number: the socket number for use by the NTP client
        """
        self._app = app

        self._group = displayio.Group()

        font = bitmap_font.load_font("/assets/IBMPlexMono-Medium-24_jep.bdf")
        self._clock_label = Label(font)
        self._group.append(self._clock_label)

        self._last_ntp_check = None
        self._ntp_update()

        self._last_update_time = None

        self._timezone_breaks = None
        self._timezone_cache_until = 0
        self._timezone_cached_offset = 0

    def clock(self, label) -> None:
        """Put the clock into the given label"""
        label.color = self._calculate_color(time.time())
        now = time.localtime(self.get_local_time())

        colon = ":" if now[5] % 2 else " "

        label.text = f"{now[3]}{colon}{now[4]:02d}"

    def update_time(self):
        """Updates the display with the current time; blinks the colon once per second"""
        self.clock(self._clock_label)

        # returns [x, y, width, height]
        bb_width = self._clock_label.bounding_box[2]

        self._clock_label.x = round(self._app.display.width / 2 - bb_width / 2)
        self._clock_label.y = self._app.display.height // 2
        self._app.display.show(self._group)

    def mini_clock(self) -> Label:
        """Create and return a label with the current time rendered into it in a small font"""
        font = bitmap_font.load_font(
            "/assets/fonts/intelone-mono-font-family-regular-6.bdf"
        )
        #        font = bitmap_font.load_font("/assets/fonts/Segment7Standard.bdf")
        label = Label(font)

        self.clock(label)

        return label

    def loop(self):
        """
        Do loop processing:

        - call NTP if needed
        - update the display if needed (once per second)
        """
        if (
            self._last_ntp_check is None
            or time.time() > self._last_ntp_check + 60 * 60 * 3
        ):
            print("NTP update")
            self._ntp_update()
            self._last_ntp_check = time.time()

        # one clock update per second
        # something's wrong with this conditional, the clock is not updating
        if (
            self._last_update_time is None
            or time.monotonic_ns() > self._last_update_time + 1e9
        ):
            self._last_update_time = time.monotonic_ns()
            self.update_time()

        self.update_time()

    def get_local_time(self):
        """Returns the local time in seconds since Jan 1 1970, adjusted by the timezone offset"""
        now = time.time()
        self._check_timezone_offset()
        return now + self._timezone_cached_offset

    def _check_timezone_offset(self) -> None:
        """
        Gets the timezone offset for the current time.

        Caches the offset until the next transition.

        Timezone offsets are stored in Data under the key "timezone"

        They shoud be moved to Data with an endpoint to set them
        """
        now = time.time()

        if (
            self._timezone_cache_until != 0
            and now < self._timezone_cache_until
            or not self._app.data.has_item(Clock.KEY_TIMEZONE)
        ):
            return

        try:
            self._timezone_breaks = self._app.data.get_item(Clock.KEY_TIMEZONE)

            if len(self._timezone_breaks["transitions"]) == 0:
                return

            prev_time = 0
            self._timezone_cache_until = now + 1e12
            for transition in self._timezone_breaks["transitions"]:
                if (
                    transition["timestamp"] > now
                    and transition["timestamp"] < self._timezone_cache_until
                ):
                    self._timezone_cache_until = transition["timestamp"]

                if transition["timestamp"] > now or transition["timestamp"] < prev_time:
                    continue

                self._timezone_cached_offset = transition["offset"]

            self._app.logger.info(
                f"clock:_check_timezone_offset -> {self._timezone_cached_offset}"
            )
        except KeyError:
            self._app.logger.error("clock:_check_timezone_offset failed")

            self._timezone_breaks = None

    def _calculate_color(self, now):
        """
        Return different colors depending on the time's relationship to dawn or dusk.

        Depends on "solar" being set in Data
        """
        solar = self._app.data.get_item(Clock.KEY_SOLAR)
        if solar is None:
            return Clock.DEFAULT_COLOR

        try:
            if solar["sunset"] - 60 * 60 <= now <= solar["sunset"]:
                return 0xFFA500  # orange

            if solar["sunrise"] - 60 * 60 <= now <= solar["sunrise"]:
                return 0x0000FF  # blue

            if solar["sunset"] < solar["sunrise"] and now <= solar["sunset"]:
                return 0x00FF00  # green

            return 0xFF0000  # red
        except KeyError:
            self._app.logger.error("clock:_calculate_color failed")

            return Clock.DEFAULT_COLOR

    @property
    def timezone_offset(self) -> int:
        """Returns the current timezone offset - used outside of the class for debugging"""
        return self._timezone_cached_offset

    @property
    def is_sundown(self) -> bool:
        """
        Return True if the sun is currently down

        Depends on "solar" being set in Data
        """
        solar = self._app.data.get_item("solar")
        if solar is None:
            return None

        now = time.time()

        try:
            if solar["sunset"] - 30 * 60 <= now <= solar["sunset"]:
                return True

            if now <= solar["sunset"]:
                return False

            return True
        except KeyError:
            return False

    def _ntp_update(self) -> None:
        ntp_data = self._app.data.get_item(
            Clock.KEY_NTP,
            {
                "refresh_interval": Clock.DEFAULT_NTP_REFRESH_INTERVAL,
                "server": "pool.ntp.org",
            },
        )

        try:
            refresh_interval = ntp_data["refresh_interval"]
        except KeyError:
            refresh_interval = Clock.DEFAULT_NTP_REFRESH_INTERVAL

        if (
            self._last_ntp_check is not None
            and refresh_interval != 0
            and time.time() - self._last_ntp_check < refresh_interval
        ):
            return

        #        try:
        #            server = ntp_data["server"]
        #            ntp = NTP(self._app.esp, server)
        #        except KeyError:
        #            ntp = NTP(self._app.esp)

        updated_time = self._app.platform.ntp_sync()
        print(f"ntp_sync {updated_time}")
        if updated_time is not None:
            self._last_ntp_check = time.time()
            self._app.rtc.datetime = updated_time
