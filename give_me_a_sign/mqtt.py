# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/mqtt - MQTT support for Give Me A Sign
=====================================================

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

from .home_assistant import HomeAssistant

MQTT_RETRY_MIN_S = 5
MQTT_RETRY_MAX_S = 120
MQTT_FAILURES_BEFORE_RESET = 20


def _get_setting(key, default):
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
    SignMQTT subscribes to an MQTT broker and dispatches data to modules.
    """

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
        self._subscribed_endpoints = set()

        if self._platform.wifi_is_connected:
            print("WiFi connected!")
        else:
            print("WiFi NOT connected!")

        self._maybe_retry_mqtt()

    def _build_mqtt_client(self):
        socket = self._platform.get_socket()

        self._mqtt = MQTT.MQTT(
            broker=os.getenv("MQTT_BROKER"),
            port=_get_setting("MQTT_PORT", 1883),
            is_ssl=_get_setting("MQTT_SSL", False),
            client_id=os.getenv("MQTT_CLIENTID"),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            socket_pool=socket,
            socket_timeout=0.25,
            connect_retries=1,
        )
        self._mqtt_loop_timeout = 0.25

        print("MQTT Connect")
        self._mqtt.will_set(
            f"{self._ha_sign_base}/available", "offline", retain=True, qos=1
        )

    def _subscribe_all_topics(self):
        self._subscribed_endpoints = set()
        for module in self._app.modules.modules():
            for endpoint in module.ENDPOINTS:
                if endpoint in self._subscribed_endpoints:
                    continue
                self._subscribed_endpoints.add(endpoint)
                for topic in (
                    f"{self._topic_prefix}/all/module/{endpoint}",
                    f"{self._ha_sign_base}/module/{endpoint}",
                ):
                    self._mqtt.subscribe(topic)
                    self._mqtt.add_topic_callback(
                        topic,
                        lambda client, topic, message, key=endpoint: self._dispatch(
                            key, message
                        ),
                    )

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

        self._mqtt.subscribe(self._time_command_topic)
        self._mqtt.add_topic_callback(self._time_command_topic, self._on_time_command)

        self._mqtt.subscribe(self._data_publish_topic)
        self._mqtt.add_topic_callback(
            self._data_publish_topic, self._on_publish_data_command
        )

    def _dispatch(self, endpoint, message):
        module = self._app.modules.by_endpoint(endpoint)
        if module is None:
            self._app.logger.error(f"mqtt: no module for endpoint {endpoint}")
            return
        raw = self._decode_mqtt_payload(message)
        module.receive(endpoint, raw)

    def _mqtt_connect_and_subscribe(self):
        self._mqtt.connect()
        self._subscribe_all_topics()
        print("MQTT Connected")
        if self._home_assistant is None:
            self._home_assistant = HomeAssistant(
                self._app.platform.wifi_mac_address, self._mqtt, self._ha_sign_base
            )
            self._home_assistant.set_modules(self._app.modules)
        else:
            self._home_assistant.set_mqtt_client(self._mqtt)
            self._home_assistant.set_modules(self._app.modules)
        self._home_assistant.publish_online_status()
        self.publish_display_state()
        self.publish_time_state()
        self._mqtt_failures = 0
        self._mqtt_backoff_s = MQTT_RETRY_MIN_S
        self._mqtt_next_retry_at = 0

    def _on_mqtt_failure(self):
        self._mqtt_next_retry_at = time.monotonic_ns() + int(self._mqtt_backoff_s * 1e9)
        self._mqtt_backoff_s = min(self._mqtt_backoff_s * 2, MQTT_RETRY_MAX_S)
        self._mqtt_failures += 1
        if self._mqtt_failures >= MQTT_FAILURES_BEFORE_RESET:
            print("MQTT: too many consecutive failures, resetting MCU")
            microcontroller.reset()

    def _teardown_client(self):
        try:
            if self._mqtt is not None:
                self._mqtt.disconnect()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self._mqtt = None

    def _maybe_retry_mqtt(self):
        if time.monotonic_ns() < self._mqtt_next_retry_at:
            return
        try:
            if self._mqtt is None:
                self._build_mqtt_client()
            self._mqtt_connect_and_subscribe()
        except Exception as error:  # pylint: disable=broad-exception-caught
            print("MQTT connect failed:", error)
            self._teardown_client()
            self._on_mqtt_failure()

    def _rebuild_mqtt_after_wifi(self):
        self._teardown_client()
        self._mqtt_backoff_s = MQTT_RETRY_MIN_S
        self._mqtt_next_retry_at = 0
        self._maybe_retry_mqtt()

    def is_connected_to_broker(self) -> bool:
        """True when an MQTT client exists and reports a live connection."""
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
        text = text.strip()
        if not text or text[0] < "0" or text[0] > "9":
            return None

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

        if "." in body:
            body = body.split(".", 1)[0]

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
            return int(time.mktime(struct)) - offset_seconds
        except (ValueError, OverflowError, TypeError):
            return None

    def _parse_time_payload(self, message):
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
        self.publish_data_store()

    def publish_display_state(self):
        """Publish the current display on/off state to the broker."""
        if not self.is_connected_to_broker():
            return
        payload = "ON" if self._app.display_enabled else "OFF"
        self._mqtt.publish(self._display_state_topic, payload, retain=True, qos=1)

    def publish_time_state(self, epoch=None):
        """Publish the device time (defaulting to now) as ISO 8601 UTC."""
        if not self.is_connected_to_broker():
            return
        if epoch is None:
            epoch = time.time()
        payload = self._epoch_to_iso_utc(epoch)
        self._mqtt.publish(self._time_state_topic, payload, retain=True, qos=1)

    def publish_data_store(self):
        """Publish every module's stored endpoint data to ``data/state``."""
        if not self.is_connected_to_broker():
            return
        combined = {}
        for module in self._app.modules.modules():
            for endpoint in module.ENDPOINTS:
                if module.store.has_item(endpoint):
                    combined[endpoint] = module.store.all().get(endpoint)
        try:
            payload = json.dumps(combined)
        except (TypeError, ValueError) as error:
            print("mqtt:data/publish serialize failed:", error)
            return
        self._mqtt.publish(self._data_state_topic, payload, retain=True, qos=1)
        print("mqtt: published full data store")

    def _publish_diagnostics(self):
        if not self._app.platform.wifi_is_connected:
            print("MQTT - disconnected, not publishing diagnostics")
            return

        flash = os.statvfs("/")
        flash_size = flash[0] * flash[2]
        flash_free = flash[0] * flash[3]

        now_utc = time.time()
        clock = self._app.modules.get("clock")
        timezone_offset = clock.timezone_offset if clock is not None else 0

        info = {
            "uptime": time.monotonic_ns() / 1e9,
            "time_utc": now_utc,
            "time_utc_iso": self._epoch_to_iso_utc(now_utc),
            "timezone_offset": timezone_offset,
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
        """Service the MQTT connection: reconnect, poll, and publish as needed."""
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
                self.publish_time_state()
                self._next_diagnostic_time = time.monotonic_ns() + int(60e9)

            self._mqtt.loop(self._mqtt_loop_timeout)
        except Exception as error:  # pylint: disable=broad-exception-caught
            print("MQTT loop error:", error)
            self._teardown_client()
            self._on_mqtt_failure()
