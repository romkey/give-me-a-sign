# SPDX-FileCopyrightText: 2020 John Park for Adafruit Industries
#
# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/clock - clock module for LED Matrix display
==========================================================

* Author: John Romkey
"""

import time

import displayio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label

from ._paths import ASSETS_DIR
from .complication import EIGHTH, FULL, HALF_WIDE, QUARTER, Complication
from .module import SignModule


class Clock(SignModule):
    """
    Clock class

    - gets the current time via NTP
    - calculates the current time considering the timezone offset
    - displays the current time on the LED matrix
    """

    # pylint: disable=too-many-instance-attributes

    NAME = "clock"
    KEY = "clock"
    KEY_NTP = "ntp"
    KEY_TIMEZONE = "timezone"
    KEY_SOLAR = "solar"
    ENDPOINTS = (KEY_SOLAR, KEY_TIMEZONE, KEY_NTP)
    PERSISTENT_KEYS = (KEY_TIMEZONE,)
    DEFAULT_DURATION = 20
    ACTIVE_RENDER = "loop"

    DEFAULT_NTP_REFRESH_INTERVAL = 60 * 60 * 6
    NTP_FAILURE_RETRY_INTERVAL = 5 * 60
    NO_SOLAR_COLOR = 0xFFAA00
    COLOR_DAY = 0x00FF00
    COLOR_NIGHT = 0xFF0000
    COLOR_PRE_SUNRISE = 0x0000FF
    COLOR_PRE_SUNSET = 0xFFA500

    def __init__(self, app):
        super().__init__(app)

        self._group = displayio.Group()
        self._full_font = bitmap_font.load_font(
            ASSETS_DIR + "/IBMPlexMono-Medium-24_jep.bdf"
        )
        self._clock_label = Label(self._full_font)
        self._group.append(self._clock_label)
        self._mini_font = None
        self._small_font = None

        self._next_ntp_attempt = 0
        self._ntp_update()

        self._last_update_time = None
        self._timezone_breaks = None
        self._timezone_cache_until = 0
        self._timezone_cached_offset = 0
        self._solar_prev_sunrise = None
        self._complications = None

    def clock(self, label) -> None:
        """Set *label* to the current local time and time-of-day color."""
        label.color = self._calculate_color(time.time())
        now = time.localtime(self.get_local_time())
        colon = ":" if now[5] % 2 else " "
        label.text = f"{now[3]}{colon}{now[4]:02d}"

    def update_time(self):
        """Refresh the full-size clock label, center it, and show it."""
        self.clock(self._clock_label)
        bb_width = self._clock_label.bounding_box[2]
        self._clock_label.x = round(self._app.canvas_width / 2 - bb_width / 2)
        self._clock_label.y = self._app.canvas_height // 2
        self._app.show_group(self._group)

    def _mini_font_loaded(self):
        if self._mini_font is None:
            self._mini_font = bitmap_font.load_font(
                ASSETS_DIR + "/fonts/intelone-mono-font-family-regular-6.bdf"
            )
        return self._mini_font

    def _small_font_loaded(self):
        if self._small_font is None:
            self._small_font = bitmap_font.load_font(
                ASSETS_DIR + "/fonts/intelone-mono-font-family-regular-6.bdf"
            )
        return self._small_font

    def _make_time_label(self, font):
        label = Label(font)
        self.clock(label)
        return label

    def mini_clock(self) -> Label:
        """Return a small clock label for use as a complication."""
        return self._make_time_label(self._mini_font_loaded())

    def show(self) -> bool:
        self.update_time()
        return True

    def background(self):
        """Resync NTP on schedule, whether or not the clock is on screen."""
        if time.monotonic_ns() >= self._next_ntp_attempt:
            print("NTP update")
            self._ntp_update()

    def loop(self):
        self.background()

        if (
            self._last_update_time is None
            or time.monotonic_ns() > self._last_update_time + 1_000_000_000
        ):
            self._last_update_time = time.monotonic_ns()
            self.update_time()

    def get_local_time(self):
        """Return the current epoch time adjusted to the configured timezone."""
        now = time.time()
        self._check_timezone_offset()
        return now + self._timezone_cached_offset

    def _check_timezone_offset(self) -> None:
        now = time.time()

        if self.store.has_item(Clock.KEY_TIMEZONE) and self.store.is_updated(
            Clock.KEY_TIMEZONE
        ):
            self._timezone_cache_until = 0
            self.store.clear_updated(Clock.KEY_TIMEZONE)

        if (
            self._timezone_cache_until != 0 and now < self._timezone_cache_until
        ) or not self.store.has_item(Clock.KEY_TIMEZONE):
            return

        try:
            self._timezone_breaks = self.store.get_item(Clock.KEY_TIMEZONE)

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
        solar = self.store.get_item(Clock.KEY_SOLAR)
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

        cross_midnight_pair = sunrise > sunset
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
        """Cached offset in seconds from UTC to local time."""
        return self._timezone_cached_offset

    @property
    def is_sundown(self) -> bool:
        """True when it is after sunset (or close to it), from pushed solar data."""
        solar = self.store.get_item(Clock.KEY_SOLAR)
        if solar is None:
            return False

        now = time.time()

        try:
            sunrise = solar["sunrise"]
            sunset = solar["sunset"]
        except KeyError:
            return False

        if sunset - 30 * 60 <= now <= sunset:
            return True

        if sunrise > sunset:
            return False

        return now < sunrise or now > sunset

    def _ntp_update(self) -> None:
        print("NTP Update")

        ntp_data = self.store.get_item(
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
            try:
                self._app.rtc.datetime = updated_time
            except OSError as error:
                print("failed to set RTC:", error)
                next_attempt = Clock.NTP_FAILURE_RETRY_INTERVAL
        else:
            next_attempt = Clock.NTP_FAILURE_RETRY_INTERVAL

        self._next_ntp_attempt = time.monotonic_ns() + next_attempt * 1_000_000_000

    def _render_full(self):
        group = displayio.Group()
        label = self._make_time_label(self._full_font)
        bb_width = label.bounding_box[2]
        label.x = round(FULL[0] / 2 - bb_width / 2)
        label.y = FULL[1] // 2
        group.append(label)
        return group

    def _render_half(self):
        group = displayio.Group()
        label = self._make_time_label(self._mini_font_loaded())
        bb_width = label.bounding_box[2]
        label.x = round(HALF_WIDE[0] / 2 - bb_width / 2)
        label.y = HALF_WIDE[1] // 2
        group.append(label)
        return group

    def _render_quarter(self):
        group = displayio.Group()
        label = self._make_time_label(self._small_font_loaded())
        bb_width = label.bounding_box[2]
        label.x = round(QUARTER[0] / 2 - bb_width / 2)
        label.y = QUARTER[1] // 2
        group.append(label)
        return group

    def _render_mini(self):
        group = displayio.Group()
        label = self.mini_clock()
        label.x = 0
        # Label y is the text's vertical center, so center it in the slot.
        label.y = EIGHTH[1] // 2
        group.append(label)
        return group

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication("full", FULL[0], FULL[1], self._render_full),
                Complication("half", HALF_WIDE[0], HALF_WIDE[1], self._render_half),
                Complication("quarter", QUARTER[0], QUARTER[1], self._render_quarter),
                Complication("mini", EIGHTH[0], EIGHTH[1], self._render_mini),
            ]
        return self._complications

    @staticmethod
    def append_mini_clock(app, group):
        """Append the mini clock to *group* in the top right corner, if available."""
        clock = app.modules.get("clock")
        if clock is None:
            return
        label = clock.mini_clock()
        label.x = app.canvas_width - label.bounding_box[2]
        # Label y is the text's vertical center, so half its height sits it
        # flush against the top edge. A smaller y clips the top row of pixels.
        label.y = label.bounding_box[3] // 2
        group.append(label)
