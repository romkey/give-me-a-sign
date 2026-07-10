# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/mqtt - MQTT support for Give Me A Sign
====================================================

* Author: John Romkey
"""
import os
import json
import time
import gc
import sys
import board
import microcontroller
import supervisor

import adafruit_minimqtt.adafruit_minimqtt as MQTT

from .aqi import AQI
from .clock import Clock
from .greet import Greet
from .image import Image
from .message import Message
from .pollen import Pollen
from .tones import Tones
from .trimet import Trimet
from .uv import UV
from .weather import Weather
from .home_assistant import HomeAssistant

MQTT_RETRY_MIN_S = 5
MQTT_RETRY_MAX_S = 120
MQTT_FAILURES_BEFORE_RESET = 20


def _get_setting(key, default):
    """
    Read a typed value from settings.toml.

    Uses supervisor.get_setting() where available (CircuitPython 10.2+),
    otherwise falls back to os.getenv() and coerces the value to the type
    of the default.
    """
    getter = getattr(supervisor, "get_setting", None)
    if getter is not None:
        return getter(key, default)

    value = os.getenv(key)
    if value is None:
        return default
    if isinstance(default, bool):
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default
    return value


class SignMQTT:  # pylint: disable=too-many-instance-attributes
    """
    SignMQTT subscribes to an MQTT broker in order to receive data on various topics
    that map to modules that display the data.
    """

    STORE_ENDPOINTS = [
        AQI.KEY,
        "debug",
        "forecast",
        Greet.KEY,
        Image.KEY,
        "lunar",
        Message.KEY,
        Pollen.KEY,
        Clock.KEY_SOLAR,
        Clock.KEY_TIMEZONE,
        Tones.KEY,
        Trimet.KEY,
        UV.KEY,
        Weather.KEY,
    ]

    def __init__(self, app, platform):
        self._app = app
        self._platform = platform
        self._id = self._platform.wifi_mac_address.replace(":", "_")
        self._next_diagnostic_time = 0
        self._topic_prefix = os.getenv("MQTT_TOPIC_PREFIX") or "givemeasign"
        self._ha_sign_base = f"{self._topic_prefix}/sign/{self._id}"
        self._display_state_topic = f"{self._ha_sign_base}/display/state"
        self._display_command_topic = f"{self._ha_sign_base}/display/set"
        self._time_state_topic = f"{self._ha_sign_base}/time/state"
        self._time_command_topic = f"{self._ha_sign_base}/time/set"
        self._data_state_topic = f"{self._ha_sign_base}/data/state"
        self._data_publish_topic = f"{self._ha_sign_base}/data/publish"

        self._mqtt = None
        self._mqtt_loop_timeout = 1
        self._home_assistant = None
        self._mqtt_failures = 0
        self._mqtt_next_retry_at = 0
        self._mqtt_backoff_s = MQTT_RETRY_MIN_S

        if self._platform.wifi_is_connected:
            print("WiFi connected!")
        else:
            print("WiFi NOT connected!")

        # one connect path for initial connect, retries and rebuilds
        self._maybe_retry_mqtt()

    def _build_mqtt_client(self):
        socket = self._platform.get_socket()

        # A small socket timeout keeps loop() from stalling the display
        # loop for seconds at a time. It's also used as the TCP connect
        # timeout, so don't make it too small.
        self._mqtt = MQTT.MQTT(
            broker=os.getenv("MQTT_BROKER"),
            port=_get_setting("MQTT_PORT", 1883),
            is_ssl=_get_setting("MQTT_SSL", False),
            client_id=os.getenv("MQTT_CLIENTID"),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            socket_pool=socket,
            socket_timeout=0.25,
            # a single bounded attempt per connect() call; otherwise
            # MiniMQTT retries internally with sleeps of up to ~30s each,
            # freezing the display. SignMQTT owns the retry/backoff policy.
            connect_retries=1,
        )
        self._mqtt_loop_timeout = 0.25

        print("MQTT Connect")
        self._mqtt.will_set(
            f"{self._ha_sign_base}/available", "offline", retain=True, qos=1
        )

    def _subscribe_all_topics(self):
        for endpoint in self.STORE_ENDPOINTS:
            # broadcast topic (all signs) and per-device topic (used by the
            # Home Assistant text entities)
            for topic in (
                f"{self._topic_prefix}/all/module/{endpoint}",
                f"{self._ha_sign_base}/module/{endpoint}",
            ):
                self._mqtt.subscribe(topic)
                self._mqtt.add_topic_callback(
                    topic,
                    lambda client, topic, message, key=endpoint: self.store_data(
                        key, message
                    ),
                )

        # matches the Home Assistant reboot button's command_topic
        topic = f"{self._ha_sign_base}/reboot"
        self._mqtt.subscribe(topic)
        self._mqtt.add_topic_callback(
            topic,
            lambda client, topic, message, key=None: microcontroller.reset(),
        )

        self._mqtt.subscribe(self._display_command_topic)
        self._mqtt.add_topic_callback(
            self._display_command_topic, self._on_display_command
        )

        # Home Assistant datetime entity + programmatic epoch/JSON payloads
        self._mqtt.subscribe(self._time_command_topic)
        self._mqtt.add_topic_callback(self._time_command_topic, self._on_time_command)

        # Home Assistant "Publish Data" button dumps the in-memory store
        self._mqtt.subscribe(self._data_publish_topic)
        self._mqtt.add_topic_callback(
            self._data_publish_topic, self._on_publish_data_command
        )

    def _mqtt_connect_and_subscribe(self):
        self._mqtt.connect()
        self._subscribe_all_topics()
        print("MQTT Connected")
        if self._home_assistant is None:
            self._home_assistant = HomeAssistant(
                self._app.platform.wifi_mac_address, self._mqtt, self._ha_sign_base
            )
        else:
            self._home_assistant.set_mqtt_client(self._mqtt)
        # the LWT may have retained "offline"; clear it right away rather than
        # waiting for the hourly advertisement cycle
        self._home_assistant.publish_online_status()
        self.publish_display_state()
        self.publish_time_state()
        self._mqtt_failures = 0
        self._mqtt_backoff_s = MQTT_RETRY_MIN_S
        self._mqtt_next_retry_at = 0

    def _on_mqtt_failure(self):
        # monotonic_ns doesn't lose precision over long uptimes like monotonic does
        self._mqtt_next_retry_at = time.monotonic_ns() + int(self._mqtt_backoff_s * 1e9)
        self._mqtt_backoff_s = min(self._mqtt_backoff_s * 2, MQTT_RETRY_MAX_S)
        self._mqtt_failures += 1
        if self._mqtt_failures >= MQTT_FAILURES_BEFORE_RESET:
            print("MQTT: too many consecutive failures, resetting MCU")
            microcontroller.reset()

    def _teardown_client(self):
        """Discard the MQTT client; _maybe_retry_mqtt() will build a fresh one."""
        try:
            if self._mqtt is not None:
                self._mqtt.disconnect()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self._mqtt = None

    def _maybe_retry_mqtt(self):
        """
        (Re)connect if the backoff timer allows it. This is the only path
        that connects, so a failure can never wedge the caller: it just
        schedules the next attempt.
        """
        if time.monotonic_ns() < self._mqtt_next_retry_at:
            return
        try:
            if self._mqtt is None:
                self._build_mqtt_client()
            self._mqtt_connect_and_subscribe()
        except Exception as error:  # pylint: disable=broad-exception-caught
            print("MQTT connect failed:", error)
            # a half-connected client can't be trusted; rebuild next attempt
            self._teardown_client()
            self._on_mqtt_failure()

    def _rebuild_mqtt_after_wifi(self):
        """WiFi came back: the old sockets are dead, so start over immediately."""
        self._teardown_client()
        self._mqtt_backoff_s = MQTT_RETRY_MIN_S
        self._mqtt_next_retry_at = 0
        self._maybe_retry_mqtt()

    def is_connected_to_broker(self) -> bool:
        """Return whether the MQTT client is currently connected."""
        if self._mqtt is None:
            return False
        try:
            return self._mqtt.is_connected()
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    @staticmethod
    def _decode_mqtt_payload(message):
        if isinstance(message, memoryview):
            message = bytes(message)
        if isinstance(message, bytes):
            return message.decode()
        return str(message)

    def _on_display_command(self, _client, _topic, message):
        """Home Assistant switch: ON = show content, OFF = blank the matrix."""
        text = self._decode_mqtt_payload(message).strip().upper()
        if text == "ON":
            self._app.display_enabled = True
        elif text == "OFF":
            self._app.display_enabled = False
        else:
            return
        self.publish_display_state()

    @staticmethod
    def _epoch_to_iso_utc(epoch):
        """Format a Unix epoch as ISO 8601 UTC for the HA datetime entity."""
        utc_tm = time.localtime(int(epoch))
        return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}+00:00".format(
            utc_tm.tm_year,
            utc_tm.tm_mon,
            utc_tm.tm_mday,
            utc_tm.tm_hour,
            utc_tm.tm_min,
            utc_tm.tm_sec,
        )

    @staticmethod
    def _parse_iso8601_utc(text):  # pylint: disable=too-many-return-statements
        """
        Parse an ISO 8601 UTC datetime string into a Unix epoch.

        Accepts the formats Home Assistant's MQTT datetime entity sends, e.g.
        2026-07-10T05:00:00, ...Z, ...+00:00, and optional fractional seconds.
        Non-UTC offsets are applied so the result is still a UTC epoch.
        """
        text = text.strip()
        if not text or text[0] < "0" or text[0] > "9":
            return None

        # Split timezone suffix: Z / z / ±HH:MM / ±HHMM
        offset_seconds = 0
        body = text
        if body.endswith("Z") or body.endswith("z"):
            body = body[:-1]
        elif len(body) >= 6 and (body[-6] in "+-" and body[-3] == ":"):
            sign = 1 if body[-6] == "+" else -1
            try:
                offset_seconds = sign * (int(body[-5:-3]) * 3600 + int(body[-2:]) * 60)
            except ValueError:
                return None
            body = body[:-6]
        elif len(body) >= 5 and body[-5] in "+-":
            sign = 1 if body[-5] == "+" else -1
            try:
                offset_seconds = sign * (int(body[-4:-2]) * 3600 + int(body[-2:]) * 60)
            except ValueError:
                return None
            body = body[:-5]

        # Drop fractional seconds if present
        if "." in body:
            body = body.split(".", 1)[0]

        # YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS
        body = body.replace(" ", "T", 1)
        parts = body.split("T")
        if len(parts) != 2:
            return None
        try:
            year_s, month_s, day_s = parts[0].split("-")
            time_parts = parts[1].split(":")
            if len(time_parts) < 2:
                return None
            hour_s = time_parts[0]
            minute_s = time_parts[1]
            second_s = time_parts[2] if len(time_parts) > 2 else "0"
            struct = time.struct_time(
                (
                    int(year_s),
                    int(month_s),
                    int(day_s),
                    int(hour_s),
                    int(minute_s),
                    int(float(second_s)),
                    0,
                    0,
                    -1,
                )
            )
            # RTC/time source is UTC; mktime treats the struct as local (= UTC here)
            return int(time.mktime(struct)) - offset_seconds
        except (ValueError, OverflowError, TypeError):
            return None

    def _parse_time_payload(self, message):
        """
        Accept HA ISO datetime strings, a bare epoch, or JSON {"epoch": ...}.
        Returns a Unix epoch int, or None if the payload is unusable.
        """
        text = self._decode_mqtt_payload(message).strip()
        if not text:
            return None

        try:
            data = json.loads(text)
        except ValueError:
            data = None

        if isinstance(data, (int, float)):
            return int(data)
        if isinstance(data, dict) and "epoch" in data:
            try:
                return int(data["epoch"])
            except (TypeError, ValueError):
                return None
        if isinstance(data, str):
            text = data.strip()

        try:
            return int(float(text))
        except ValueError:
            pass

        return self._parse_iso8601_utc(text)

    def _on_time_command(self, _client, _topic, message):
        """Set the device RTC from an MQTT time payload (HA datetime or epoch)."""
        epoch = self._parse_time_payload(message)
        if epoch is None:
            self._app.logger.error(
                f"mqtt:time/set bad payload: {self._decode_mqtt_payload(message)}"
            )
            return

        try:
            self._app.rtc.datetime = time.localtime(epoch)
        except OSError as error:
            print("failed to set RTC from MQTT:", error)
            return

        print(f"mqtt:time/set epoch={epoch}")
        self.publish_time_state(epoch)

    def _on_publish_data_command(self, _client, _topic, _message):
        """Home Assistant button: publish the full in-memory Data store."""
        self.publish_data_store()

    def publish_display_state(self):
        """Publish retained display switch state for Home Assistant."""
        if not self.is_connected_to_broker():
            return
        payload = "ON" if self._app.display_enabled else "OFF"
        self._mqtt.publish(self._display_state_topic, payload, retain=True, qos=1)

    def publish_time_state(self, epoch=None):
        """Publish retained ISO 8601 UTC time for the Home Assistant datetime entity."""
        if not self.is_connected_to_broker():
            return
        if epoch is None:
            epoch = time.time()
        payload = self._epoch_to_iso_utc(epoch)
        self._mqtt.publish(self._time_state_topic, payload, retain=True, qos=1)

    def publish_data_store(self):
        """Publish the full Data store JSON to the data/state topic."""
        if not self.is_connected_to_broker():
            return
        try:
            payload = json.dumps(self._app.data.all())
        except (TypeError, ValueError) as error:
            print("mqtt:data/publish serialize failed:", error)
            return
        self._mqtt.publish(self._data_state_topic, payload, retain=True, qos=1)
        print("mqtt: published full data store")

    def store_data(self, key, message):
        """
        Generic endpoint used to store a received message using the specified key. Attempts to
        parse the message as JSON and stores it on success. Logs an error on failure.

        Home Assistant text entities for greet/message publish plain text (not JSON).
        Fall back to {"person": ...} / {"text": ...} for those keys so typing a name
        or message in HA works without requiring a JSON object.
        """
        print(f"mqtt store_data! {key}", message)
        try:
            data = json.loads(message)
        except ValueError:
            data = None

        if key in ("message", "greet") and not isinstance(data, dict):
            text = message if data is None else data
            if not isinstance(text, str):
                text = str(text)
            data = {"text": text} if key == "message" else {"person": text}
        elif key == "message" and isinstance(data, dict):
            # HA notify payloads commonly use {"message": "..."}.
            if "text" not in data and isinstance(data.get("message"), str):
                data = {"text": data["message"]}
        elif data is None:
            self._app.logger.error(
                f"server:store_data({key}) store_data failed: {message}"
            )
            return

        self._app.data.set_item(key, data)

        self._app.logger.info(f"server:store_data({key}) got JSON")
        self._app.logger.info(data)

    def _publish_diagnostics(self):
        """
        Periodically publish diagnostic information about the state of the sign
        """
        if not self._app.platform.wifi_is_connected:
            print("MQTT - disconnected, not publishing diagnostics")
            return

        flash = os.statvfs("/")
        flash_size = flash[0] * flash[2]
        flash_free = flash[0] * flash[3]

        now_utc = time.time()

        info = {
            "uptime": time.monotonic_ns() / 1e9,
            "time_utc": now_utc,
            "time_utc_iso": self._epoch_to_iso_utc(now_utc),
            "timezone_offset": self._app.clock.timezone_offset,
            "free_memory": gc.mem_free(),  # pylint: disable=no-member
            "flash_free": flash_free,
            "flash_size": flash_size,
            "rtc": "software"
            if self._app.rtc.__class__.__name__ == "RTC"
            else self._app.rtc.__class__.__name__,
            "wifi_ssid": self._app.platform.wifi_ssid,
            "wifi_bssid": self._app.platform.wifi_bssid,
            "wifi_rssi": self._app.platform.wifi_rssi,
            "mac_address": self._app.platform.wifi_mac_address,
            "ipv4address": str(self._app.platform.wifi_ip_address),
            "python_version": sys.version,
            "circuitpython_version": ".".join([str(i) for i in sys.implementation[1]]),
            "platform": sys.platform,
            "board": board.board_id,
            "display_height": self._app.display.height,
            "display_width": self._app.display.width,
        }

        self._mqtt.publish(f"{self._ha_sign_base}/diagnostics", json.dumps(info))

    def loop(self):
        """
        Perform housekeeping tasks in the loop
        Makes sure we're still connected to the broker,
        and gives the protocol engine a chance to run.
        """
        if (
            hasattr(self._platform, "wifi_just_restored")
            and self._platform.wifi_just_restored()
        ):
            print("WiFi restored, rebuilding MQTT client")
            self._rebuild_mqtt_after_wifi()

        if not self._platform.wifi_is_connected:
            return

        if self._mqtt is None or not self.is_connected_to_broker():
            self._maybe_retry_mqtt()
            return

        try:
            self._home_assistant.loop()

            if time.monotonic_ns() > self._next_diagnostic_time:
                print("MQTT publishing diagnostics")
                self._publish_diagnostics()
                # keep the HA datetime entity aligned with NTP/RTC drift
                self.publish_time_state()
                self._next_diagnostic_time = time.monotonic_ns() + int(60e9)

            self._mqtt.loop(self._mqtt_loop_timeout)
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Any failure here (dead socket, wedged client, bad ap_info race)
            # gets the same treatment: drop the client and reconnect with
            # backoff. Never let it escape and starve the display loop.
            print("MQTT loop error:", error)
            self._teardown_client()
            self._on_mqtt_failure()
