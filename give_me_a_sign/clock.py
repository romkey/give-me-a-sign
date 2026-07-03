# SPDX-FileCopyrightText: 2020 John Park for Adafruit Industries
#
# SPDX-FileCopyrightText: 2023-2026 John Romkey
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

from ._paths import ASSETS_DIR


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
    NTP_FAILURE_RETRY_INTERVAL = 5 * 60
    # Shown when solar JSON is missing or invalid (distinct from intentional night green)
    NO_SOLAR_COLOR = 0xFFAA00
    COLOR_DAY = 0x00FF00
    COLOR_NIGHT = 0xFF0000
    COLOR_PRE_SUNRISE = 0x0000FF
    COLOR_PRE_SUNSET = 0xFFA500

    def __init__(self, app):
        """
        :param app: the GiveMeASign object this belongs to
        :param ntp_socket_number: the socket number for use by the NTP client
        """
        self._app = app

        self._group = displayio.Group()

        font = bitmap_font.load_font(ASSETS_DIR + "/IBMPlexMono-Medium-24_jep.bdf")
        self._clock_label = Label(font)
        self._group.append(self._clock_label)
        self._mini_font = None

        self._next_ntp_attempt = 0
        self._ntp_update()

        self._last_update_time = None

        self._timezone_breaks = None
        self._timezone_cache_until = 0
        self._timezone_cached_offset = 0
        self._solar_prev_sunrise = None

    def clock(self, label) -> None:
        """Put the clock into the given label"""
        # Solar sunrise/sunset from MQTT are Unix UTC seconds; match time.time().
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
        self._app.display.root_group = self._group

    def mini_clock(self) -> Label:
        """Create and return a label with the current time rendered into it in a small font"""
        if self._mini_font is None:
            # loading a BDF font is slow and allocates; do it once and reuse
            self._mini_font = bitmap_font.load_font(
                ASSETS_DIR + "/fonts/intelone-mono-font-family-regular-6.bdf"
            )
        label = Label(self._mini_font)

        self.clock(label)

        return label

    def loop(self):
        """
        Do loop processing:

        - call NTP if needed
        - update the display if needed (once per second)
        """
        if time.monotonic_ns() >= self._next_ntp_attempt:
            print("NTP update")
            self._ntp_update()

        if (
            self._last_update_time is None
            or time.monotonic_ns() > self._last_update_time + 1e9
        ):
            self._last_update_time = time.monotonic_ns()
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
            self._timezone_cache_until != 0 and now < self._timezone_cache_until
        ) or not self._app.data.has_item(Clock.KEY_TIMEZONE):
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

    def _calculate_color(self, now):  # pylint: disable=too-many-return-statements
        """
        Colors by solar phase. Expects ``solar`` in Data with ``sunrise`` and ``sunset``
        as Unix epoch seconds in UTC (same basis as ``time.time()``).

        When ``sunrise > sunset`` (HA: next sunset still today, next sunrise tomorrow),
        ``now < sunrise - 1h`` is true for almost all of the local *day* because ``sunrise``
        is tomorrow afternoon in Unix terms — that must not select night (red).

        For ``now <= sunset`` in that case, use ``now > sunrise - 24h`` as "past the prior
        dawn" → daytime (green) until sunset.

        ``_solar_prev_sunrise`` + ``morning_after_roll`` still suppress stale pre-dawn blue
        right after the sunrise field rolls forward.
        """
        solar = self._app.data.get_item(Clock.KEY_SOLAR)
        if solar is None:
            return Clock.NO_SOLAR_COLOR

        try:
            sunrise = solar["sunrise"]
            sunset = solar["sunset"]
        except KeyError:
            self._app.logger.error("clock:_calculate_color missing keys")
            return Clock.NO_SOLAR_COLOR

        hour = 60 * 60
        prev = self._solar_prev_sunrise
        self._solar_prev_sunrise = sunrise

        # HA-style: next sunset today, next sunrise tomorrow → unix sunrise > sunset
        cross_midnight_pair = sunrise > sunset
        # Publisher advanced ``sunrise`` to the next dawn; we're past the previous one → daytime
        morning_after_roll = (
            prev is not None and prev + 3600 < sunrise and prev < now <= sunset
        )

        if sunset - hour <= now <= sunset:
            return Clock.COLOR_PRE_SUNSET
        if sunrise - hour <= now <= sunrise and not morning_after_roll:
            return Clock.COLOR_PRE_SUNRISE

        if cross_midnight_pair:
            if now <= sunset:
                if now > sunrise - 24 * hour:
                    return Clock.COLOR_DAY
                return Clock.COLOR_NIGHT
            if sunrise - hour <= now <= sunrise and not morning_after_roll:
                return Clock.COLOR_PRE_SUNRISE
            return Clock.COLOR_NIGHT

        if sunrise >= sunset:
            self._app.logger.error("clock:solar sunrise >= sunset, ignoring")
            return Clock.NO_SOLAR_COLOR
        if sunrise < now < sunset - hour:
            return Clock.COLOR_DAY
        if now > sunset or now < sunrise - hour:
            return Clock.COLOR_NIGHT
        return Clock.COLOR_DAY

    @property
    def timezone_offset(self) -> int:
        """Returns the current timezone offset - used outside of the class for debugging"""
        return self._timezone_cached_offset

    @property
    def is_sundown(self) -> bool:
        """
        Return True if the sun is currently down (or will be within 30 minutes),
        False if it's up or we don't have solar data

        Handles HA-style data where sunrise/sunset are the *next* events, so
        after sunset rolls forward both timestamps are in the future and
        ``sunrise < sunset`` means it's currently night.

        Depends on "solar" being set in Data
        """
        solar = self._app.data.get_item(Clock.KEY_SOLAR)
        if solar is None:
            return False

        now = time.time()

        try:
            sunrise = solar["sunrise"]
            sunset = solar["sunset"]
        except KeyError:
            return False

        # last 30 minutes of daylight count as sundown
        if sunset - 30 * 60 <= now <= sunset:
            return True

        if sunrise > sunset:
            # next sunrise is after next sunset: it's currently daytime
            return False

        # normal ordering (e.g. static data with today's times): night if
        # before sunrise or after sunset
        return now < sunrise or now > sunset

    def _ntp_update(self) -> None:
        """
        Attempt an NTP sync and schedule the next attempt: after
        refresh_interval on success, or NTP_FAILURE_RETRY_INTERVAL on failure
        """
        print("NTP Update")

        ntp_data = self._app.data.get_item(
            Clock.KEY_NTP,
            {
                "refresh_interval": Clock.DEFAULT_NTP_REFRESH_INTERVAL,
                "server": "pool.ntp.org",
            },
        )

        try:
            refresh_interval = int(ntp_data["refresh_interval"])
        except (KeyError, TypeError, ValueError):
            refresh_interval = Clock.DEFAULT_NTP_REFRESH_INTERVAL

        if refresh_interval <= 0:
            refresh_interval = Clock.DEFAULT_NTP_REFRESH_INTERVAL

        updated_time = self._app.platform.ntp_sync()
        print(f"ntp_sync {updated_time}")
        if updated_time is not None:
            next_attempt = refresh_interval
            # a flaky hardware RTC (I2C) must not escape: an uncaught error
            # here would leave _next_ntp_attempt unset and retry every pass
            try:
                self._app.rtc.datetime = updated_time
            except OSError as error:
                print("failed to set RTC:", error)
                next_attempt = Clock.NTP_FAILURE_RETRY_INTERVAL
        else:
            next_attempt = Clock.NTP_FAILURE_RETRY_INTERVAL

        self._next_ntp_attempt = time.monotonic_ns() + next_attempt * 1_000_000_000
