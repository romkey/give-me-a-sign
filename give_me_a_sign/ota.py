# SPDX-FileCopyrightText: 2023-2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/ota - over-the-air firmware updates via ``dualbank``
====================================================================

Downloads a CircuitPython firmware image (``.bin`` or ``.uf2``) over HTTP(S)
and writes it to the inactive OTA partition with the ESP32 ``dualbank``
module, then reboots into it after a short countdown.

The image plumbing lives in :mod:`give_me_a_sign.firmware_image`: UF2
unwrapping, pulling the application out of a whole-flash image, and the
aligned writes ``dualbank`` wants. This module is the state machine around
it - the MQTT endpoints, the matrix screen and the reboot countdown.

* Author: John Romkey
"""

import json
import sys
import time

import displayio
import terminalio
import microcontroller
from adafruit_display_text.label import Label

from .complication import FULL, Complication
from .firmware_image import (
    AppImageFilter,
    FlashWriter,
    OTAError,
    UF2Unwrapper,
    looks_like_uf2,
)
from .module import SignModule

try:
    import dualbank
except ImportError:  # pragma: no cover - only on boards without dualbank
    dualbank = None


#: Bytes pulled from the socket per ``iter_content`` step.
CHUNK_SIZE = 2048

#: Chunks to pull per main-loop pass, so the display keeps running.
CHUNKS_PER_PASS = 8

#: Seconds between "rebooting in N" ticks once the image is flashed.
REBOOT_COUNTDOWN_S = 5

#: Seconds a failed update holds the matrix before the rotation resumes.
FAILED_DISPLAY_S = 10

#: Minimum plausible firmware image; anything shorter is a broken download.
MIN_IMAGE_BYTES = 64 * 1024

#: Distinguishes "never published" from "published as empty".
_UNSET = object()

STATE_IDLE = "idle"
STATE_DOWNLOADING = "downloading"
STATE_COUNTDOWN = "countdown"
STATE_FAILED = "failed"


def firmware_version_from_url(url):
    """Best-effort version label from a firmware filename.

    CircuitPython builds are named like
    ``adafruit-circuitpython-<board>-<locale>-10.0.0.bin``, so the last
    dash-separated piece that starts with a digit is the version. Anything
    unrecognizable falls back to the bare filename, which still gives Home
    Assistant something that differs from the installed version.
    """
    if not url:
        return None
    name = url.split("?")[0].rstrip("/").split("/")[-1]
    for suffix in (".bin", ".uf2"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    for part in reversed(name.split("-")):
        if part and part[0].isdigit():
            return part
    return name[:32] or None


class OTA(SignModule):  # pylint: disable=too-many-instance-attributes
    """
    Downloads and installs CircuitPython firmware over the air.

    Home Assistant gets a text entity for the image URL, a button that starts
    the download, and a sensor carrying the result. The download runs a few
    chunks per main-loop pass so the sign keeps drawing and MQTT keeps
    flowing while it works.
    """

    NAME = "ota"
    KEY_URL = "ota_url"
    KEY_URL_MAIN = "ota_url_main"
    KEY_INSTALL = "ota_install"
    ENDPOINTS = (KEY_URL, KEY_URL_MAIN, KEY_INSTALL)
    PERSISTENT_KEYS = (KEY_URL, KEY_URL_MAIN)
    IS_INTERRUPT = True
    ACTIVE_RENDER = "loop"
    DEFAULT_DURATION = 5
    NEEDS_LOOP_ALWAYS = False

    STATE_SUFFIX = "ota/state"
    ATTRIBUTES_SUFFIX = "ota/attributes"
    URL_SUFFIX = "ota/url"
    UPDATE_SUFFIX = "ota/update"

    def __init__(self, app):
        super().__init__(app)
        self._complications = None
        self._state = STATE_IDLE
        self._message = "idle"
        self._error = None
        self._urls = {}
        self._active_url = None
        self._response = None
        self._chunks = None
        self._writer = None
        self._unwrapper = None
        self._filter = None
        self._head = bytearray()
        self._format = None
        self._received = 0
        self._total = 0
        self._reboot_at = 0
        self._last_tick = -1
        self._next_status_ns = 0
        self._status_dirty = True
        self._shown_message = None
        self._group = None
        self._failed_until_ns = 0
        self._published_url = _UNSET
        self._startup_status_sent = False

    # ------------------------------------------------------------------
    # MQTT entry points
    # ------------------------------------------------------------------

    def receive(self, endpoint, raw) -> None:
        # This overrides the base receive(), which is what logs
        # "module:<name>:receive(<endpoint>)" for every other module, so say
        # so here too — an update that reports nothing is indistinguishable
        # from one whose payload never arrived.
        self._app.logger.info(f"module:ota:receive({endpoint})")
        print(f"ota: {endpoint} <- {raw!r}")

        if endpoint in (OTA.KEY_URL, OTA.KEY_URL_MAIN):
            self._receive_url(endpoint, raw)
            return
        if endpoint == OTA.KEY_INSTALL:
            self._receive_install(raw)
            return
        self._app.logger.error(f"module:ota:receive unknown endpoint {endpoint}")

    def _receive_url(self, endpoint, raw) -> None:
        url = self._extract_url(raw)
        if url is None:
            self._app.logger.error(f"module:ota:{endpoint} bad payload")
            return
        self.store.set_item(endpoint, {"url": url})
        self.store.clear_updated(endpoint)
        self._urls[endpoint] = url
        self._app.logger.info(f"module:ota url set to {url}")
        print(f"ota: url set via {endpoint} to {url}")
        self._publish_url()
        if self._state in (STATE_IDLE, STATE_FAILED):
            self._set_state(STATE_IDLE, "idle", error=None)

    def _receive_install(self, raw) -> None:
        self.store.clear_updated(OTA.KEY_INSTALL)
        url = self._extract_url(raw)
        if url is None:
            url = self.url
            print(f"ota: install requested, using stored url {url!r}")
        else:
            print(f"ota: install requested with url {url!r}")
        platform = getattr(self._app, "platform", None)
        # Both halves held a quoted expression, and mpy-cross rejects two such
        # f-strings concatenated: one f-string, values worked out first.
        connected = getattr(platform, "wifi_is_connected", None)
        have_dualbank = "yes" if dualbank is not None else "no"
        print(f"ota: wifi connected={connected} dualbank={have_dualbank}")
        self.start_update(url)

    @staticmethod
    def _extract_url(raw):
        """Pull a URL out of a bare-string, ``{"url": …}``, or notify payload."""
        data = SignModule.normalize_text_payload(raw, "url")
        for key in ("url", "message", "text"):
            value = data.get(key)
            if isinstance(value, str):
                value = value.strip()
                if value.startswith("http://") or value.startswith("https://"):
                    return value
        return None

    @property
    def url(self):
        """The firmware URL to install, or ``None``.

        Two entities can supply it, so that one shaped like the working
        Message entity can be compared against one in Home Assistant's
        configuration section. The configuration entity wins when both hold
        a URL; otherwise whichever has one is used.
        """
        for key in (OTA.KEY_URL, OTA.KEY_URL_MAIN):
            value = self._stored_url(key)
            if value is not None:
                return value
        return None

    def _stored_url(self, key):
        """The URL held by one of the URL endpoints, or ``None``."""
        cached = self._urls.get(key)
        if cached:
            return cached
        stored = self.store.get_item(key)
        if isinstance(stored, dict):
            value = stored.get("url")
            if isinstance(value, str) and value:
                self._urls[key] = value
                return value
        return None

    @property
    def state(self) -> str:
        """Current updater state: idle, downloading, countdown, or failed."""
        return self._state

    @property
    def status_message(self) -> str:
        """Human-readable status, as published to the Home Assistant sensor."""
        return self._message

    # ------------------------------------------------------------------
    # update state machine
    # ------------------------------------------------------------------

    def start_update(self, url=None) -> bool:
        """Begin downloading *url* (or the stored URL). Return True if started."""
        if self._state == STATE_DOWNLOADING:
            self._app.logger.error("module:ota already downloading")
            return False
        if self._state == STATE_COUNTDOWN:
            self._app.logger.error("module:ota already rebooting")
            return False

        if url is None:
            url = self.url
        if url is None:
            base = self._base_topic() or "<prefix>/sign/<mac>"
            self._fail(f"no firmware URL set - publish one to {base}/module/ota_url")
            return False

        self._reset_transfer()
        self._active_url = url

        try:
            self._open_stream(url)
        except OTAError as error:
            self._fail(str(error))
            return False
        except Exception as error:  # pylint: disable=broad-exception-caught
            self._fail(f"download failed: {error}")
            return False

        self._set_state(STATE_DOWNLOADING, "downloading 0%", error=None)
        return True

    def _reset_transfer(self) -> None:
        self._close_response()
        self._chunks = None
        self._writer = None
        self._unwrapper = None
        self._filter = None
        self._head = bytearray()
        self._format = None
        self._received = 0
        self._total = 0
        self._last_tick = -1

    def _open_stream(self, url) -> None:
        if dualbank is None:
            raise OTAError("dualbank is not available on this board")

        platform = getattr(self._app, "platform", None)
        getter = getattr(platform, "get_requests_session", None)
        if getter is None:
            raise OTAError(
                "platform cannot make HTTP requests - stale give_me_a_sign install?"
            )
        try:
            session = getter()
        except OTAError:
            raise
        except Exception as error:  # pylint: disable=broad-exception-caught
            raise OTAError(f"no HTTP session: {error}") from error
        if session is None:
            raise OTAError("no HTTP session: wifi is not connected")

        self._app.logger.info(f"module:ota downloading {url}")
        response = session.get(url, stream=True)
        status = getattr(response, "status_code", 200)
        if status != 200:
            try:
                response.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            raise OTAError(f"HTTP {status}")

        self._response = response
        self._total = self._content_length(response)
        self._chunks = response.iter_content(CHUNK_SIZE)
        self._writer = FlashWriter()

    @staticmethod
    def _content_length(response) -> int:
        headers = getattr(response, "headers", None) or {}
        for key in ("content-length", "Content-Length"):
            if key in headers:
                try:
                    return int(headers[key])
                except (TypeError, ValueError):
                    return 0
        return 0

    def background(self) -> None:
        self._publish_url()
        if self._state == STATE_DOWNLOADING:
            self._pump()
        elif self._state == STATE_COUNTDOWN:
            self._countdown()

        # The status topic is retained, so a failure from before a reboot
        # would otherwise sit in Home Assistant looking current. Overwrite
        # it with this boot's idle state as soon as MQTT can carry it.
        if not self._startup_status_sent:
            if self._flush_status(force=True):
                self._startup_status_sent = True
            return

        self._flush_status()

    def _pump(self) -> None:
        for _ in range(CHUNKS_PER_PASS):
            try:
                chunk = next(self._chunks)
            except StopIteration:
                self._finish_download()
                return
            except OTAError as error:
                self._fail(str(error))
                return
            except Exception as error:  # pylint: disable=broad-exception-caught
                self._fail(f"download failed: {error}")
                return

            if not chunk:
                continue

            try:
                self._consume(chunk)
            except OTAError as error:
                self._fail(str(error))
                return
            except Exception as error:  # pylint: disable=broad-exception-caught
                self._fail(f"flash failed: {error}")
                return

        self._report_progress()

    def _consume(self, chunk) -> None:
        self._received += len(chunk)

        if self._format is None:
            self._head.extend(chunk)
            if len(self._head) < 8:
                return
            chunk = bytes(self._head)
            self._head = bytearray()
            self._filter = AppImageFilter(self._writer.write)
            if looks_like_uf2(chunk):
                self._format = "uf2"
                self._unwrapper = UF2Unwrapper(self._filter.feed)
            else:
                self._format = "bin"
            self._app.logger.info(f"module:ota image format {self._format}")

        if self._format == "uf2":
            self._unwrapper.feed(chunk)
        else:
            self._filter.feed(chunk)

    def _finish_download(self) -> None:
        try:
            if self._format is None:
                raise OTAError("empty download")
            if self._format == "uf2":
                self._unwrapper.feed(b"")
                self._unwrapper.finish()
            self._filter.finish()
            if self._filter.whole_flash:
                self._app.logger.info(
                    "module:ota whole-flash image, app taken from "
                    f"{self._filter.app_offset:#08x}"
                )
            written = self._writer.finish()
            if written < MIN_IMAGE_BYTES:
                raise OTAError(f"image too small ({written} bytes)")
            if self._total and self._received < self._total:
                raise OTAError(
                    f"download truncated ({self._received}/{self._total} bytes)"
                )
            dualbank.switch()
        except OTAError as error:
            self._fail(str(error))
            return
        except Exception as error:  # pylint: disable=broad-exception-caught
            self._fail(f"flash failed: {error}")
            return
        finally:
            self._close_response()

        self._app.logger.info("module:ota image flashed, rebooting")
        self._reboot_at = time.monotonic_ns() + REBOOT_COUNTDOWN_S * 1_000_000_000
        self._last_tick = -1
        self._set_state(
            STATE_COUNTDOWN, f"rebooting in {REBOOT_COUNTDOWN_S}s", error=None
        )

    def _countdown(self) -> None:
        remaining_ns = self._reboot_at - time.monotonic_ns()
        if remaining_ns <= 0:
            self._set_state(STATE_COUNTDOWN, "rebooting now", error=None)
            self._flush_status(force=True)
            microcontroller.reset()
            return

        # round up, so the first tick reads "5s" and the last reads "1s"
        seconds = int((remaining_ns + 999_999_999) // 1_000_000_000)
        if seconds != self._last_tick:
            self._last_tick = seconds
            self._set_state(STATE_COUNTDOWN, f"rebooting in {seconds}s", error=None)

    def _close_response(self) -> None:
        if self._response is None:
            return
        try:
            self._response.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self._response = None

    def _fail(self, reason) -> None:
        self._app.logger.error(f"module:ota failed: {reason}")
        self._failed_until_ns = time.monotonic_ns() + FAILED_DISPLAY_S * 1_000_000_000
        self._close_response()
        self._chunks = None
        self._writer = None
        self._unwrapper = None
        self._filter = None
        self._set_state(STATE_FAILED, f"failed: {reason}", error=reason)

    # ------------------------------------------------------------------
    # status reporting
    # ------------------------------------------------------------------

    @property
    def progress(self) -> int:
        """Percent of the image downloaded, or 0 when the size is unknown."""
        if not self._total:
            return 0
        return min(100, int(self._received * 100 / self._total))

    def _report_progress(self) -> None:
        if self._total:
            message = f"downloading {self.progress}%"
        else:
            message = f"downloading {self._received // 1024} KiB"
        if message != self._message:
            self._set_state(STATE_DOWNLOADING, message, error=self._error)

    def _set_state(self, state, message, error) -> None:
        if message != self._message or state != self._state:
            print(f"ota: {state} - {message}")
        self._state = state
        self._message = message
        self._error = error
        self._status_dirty = True

    def status_attributes(self) -> dict:
        """Structured status for the sensor's JSON attributes topic."""
        return {
            "state": self._state,
            "message": self._message,
            "url": self._active_url or self.url,
            "format": self._format,
            "progress": self.progress,
            "bytes_received": self._received,
            "bytes_total": self._total,
            "error": self._error,
        }

    def _base_topic(self):
        return getattr(self._app.platform, "mqtt_base_topic", None)

    def _publish(self, suffix, payload) -> bool:
        base = self._base_topic()
        if not base:
            return False
        publish = getattr(self._app.platform, "mqtt_publish", None)
        if publish is None:
            return False
        return bool(publish(f"{base}/{suffix}", payload))

    def _publish_url(self) -> None:
        """Mirror the stored URL to Home Assistant, including when it is empty.

        A text entity whose state topic has never been published keeps
        showing whatever was last typed into it, committed or not — so the
        box can read like a URL is set while the sign has none. Publishing
        the sign's own view, empty string included, makes the field agree
        with what an install would actually use.
        """
        url = self.url
        if url == self._published_url:
            return
        if self._publish(OTA.URL_SUFFIX, url or ""):
            self._published_url = url

    def _flush_status(self, force=False) -> bool:
        """Publish status, attributes and update state. True if they went out."""
        if not self._status_dirty and not force:
            return False

        now = time.monotonic_ns()
        # Throttle only the progress chatter; countdown ticks and final
        # results are each worth a message of their own.
        if (
            not force
            and self._state == STATE_DOWNLOADING
            and now < self._next_status_ns
        ):
            return False

        if not self._publish(OTA.STATE_SUFFIX, self._message[:255]):
            return False
        self._publish(OTA.ATTRIBUTES_SUFFIX, json.dumps(self.status_attributes()))
        self._publish(OTA.UPDATE_SUFFIX, json.dumps(self.update_attributes()))
        self._status_dirty = False
        self._next_status_ns = now + 1_000_000_000
        return True

    @staticmethod
    def _installed_version() -> str:
        """The running CircuitPython version, for the update entity."""
        try:
            return ".".join(str(part) for part in sys.implementation.version)
        except (AttributeError, TypeError):  # pragma: no cover - defensive
            return "unknown"

    def update_attributes(self) -> dict:
        """State for Home Assistant's update entity.

        Home Assistant offers Install when latest differs from installed, so
        with no URL set the two match and the entity reads as up to date.
        """
        installed = self._installed_version()
        url = self._active_url or self.url
        payload = {
            "installed_version": installed,
            "latest_version": firmware_version_from_url(url) or installed,
            "title": "CircuitPython firmware",
            "in_progress": self._state in (STATE_DOWNLOADING, STATE_COUNTDOWN),
        }
        if self._state == STATE_DOWNLOADING and self._total:
            payload["update_percentage"] = self.progress
        else:
            payload["update_percentage"] = None
        if url:
            payload["release_url"] = url
        return payload

    # ------------------------------------------------------------------
    # display
    # ------------------------------------------------------------------

    def _display_is_leased(self) -> bool:
        """True while another interrupt or a system screen holds the display.

        The main loop rescans the interrupt modules every pass, and Greet,
        Message, and Image each clear their updated flag inside ``show()``.
        An update that claimed unconditionally would therefore cut those
        screens down to a single pass and swallow them for the length of the
        flash, so it waits for the current lease to run out instead.
        """
        app = self._app
        if getattr(app, "system_screen", None) is not None:
            return True
        active = getattr(app, "active_interrupt", None)
        return active is not None and active is not self

    def wants_interrupt(self) -> bool:
        # An update owns the matrix for as long as it runs: progress that
        # vanishes back into the rotation after five seconds is worse than no
        # progress at all, and with no Content-Length the text never changes
        # to win the display back. Redraw cost is handled in show(), which
        # reuses its group until the text changes — ownership and repainting
        # are separate questions.
        if self._state in (STATE_DOWNLOADING, STATE_COUNTDOWN):
            return not self._display_is_leased()
        if self._state == STATE_FAILED:
            if self._display_is_leased():
                return False
            # A failure gets a bounded spot on the screen, then the rotation
            # carries on; the status sensor keeps the detail.
            return time.monotonic_ns() < self._failed_until_ns
        return False

    def should_show(self) -> bool:
        return self._state != STATE_IDLE

    def duration(self) -> int:
        """Seconds to hold the display when the rotation hands it over.

        Each re-entry resets the interrupt lease, so a fixed five seconds
        would keep a failure on screen for up to five seconds past its
        window. Asking for only the time left makes the lease end with the
        window, give or take the one-second granularity of the countdown.
        """
        if self._state == STATE_FAILED:
            remaining_ns = self._failed_until_ns - time.monotonic_ns()
            if remaining_ns <= 0:
                return 1
            return int((remaining_ns + 999_999_999) // 1_000_000_000)
        return OTA.DEFAULT_DURATION

    def _build_group(self):
        group = displayio.Group()

        title = Label(terminalio.FONT, color=0x00A0FF, text="firmware")
        title.x = 0
        title.y = 6
        group.append(title)

        color = 0xFF0000 if self._state == STATE_FAILED else 0xFFFFFF
        body = Label(terminalio.FONT, color=color, text=self._short_message())
        body.x = 0
        body.y = self._app.canvas_height // 2 + 6
        group.append(body)

        return group

    def _short_message(self) -> str:
        """Trim the status to something that fits a 64-pixel-wide screen."""
        if self._state == STATE_DOWNLOADING:
            return f"{self.progress}%" if self._total else "dl..."
        if self._state == STATE_COUNTDOWN:
            return f"boot {max(0, self._last_tick)}"
        if self._state == STATE_FAILED:
            return "failed"
        return "idle"

    def show(self) -> bool:
        # The main loop calls this every pass while the update owns the
        # screen, so rebuilding the labels here would churn the heap for the
        # length of a multi-megabyte flash. Keep the group and repaint it;
        # only new text costs an allocation.
        message = self._short_message()
        if self._group is None or message != self._shown_message:
            self._group = self._build_group()
            self._shown_message = message
        self._app.show_group(self._group)
        return True

    def loop(self) -> None:
        self.show()

    def ha_entities(self):
        return [
            {
                "component": "text",
                "key": "ota_url",
                "config": {
                    "name": "Firmware URL",
                    "endpoint": OTA.KEY_URL,
                    "icon": "mdi:link-variant",
                    "state_topic_suffix": OTA.URL_SUFFIX,
                    "entity_category": "config",
                    "max": 255,
                    "notify": False,
                    # Retained: the broker redelivers the URL when the sign
                    # resubscribes, so it survives a reboot without needing
                    # the /data.json write that USB mass storage blocks.
                    "retain": True,
                },
            },
            {
                # Deliberately shaped exactly like the Message entity, which
                # commits reliably: no entity_category (so it lands in the
                # main controls rather than the device page's configuration
                # block), and no state_topic (so Home Assistant is optimistic
                # and keeps what was typed instead of waiting for an echo).
                "component": "text",
                "key": "ota_url_main",
                "config": {
                    "name": "Firmware URL (controls)",
                    "endpoint": OTA.KEY_URL_MAIN,
                    "icon": "mdi:link-variant",
                    "notify": False,
                },
            },
            {
                "component": "update",
                "key": "ota_update",
                "config": {
                    "name": "Firmware",
                    "endpoint": OTA.KEY_INSTALL,
                    "state_topic_suffix": OTA.UPDATE_SUFFIX,
                    "payload_install": "install",
                    "device_class": "firmware",
                },
            },
            {
                "component": "button",
                "key": "ota_install",
                "config": {
                    "name": "Install Firmware",
                    "endpoint": OTA.KEY_INSTALL,
                    "payload_press": "install",
                    "icon": "mdi:cloud-download",
                    "entity_category": "config",
                },
            },
            {
                "component": "sensor",
                "key": "ota_status",
                "config": {
                    "name": "Firmware Update Status",
                    "state_topic_suffix": OTA.STATE_SUFFIX,
                    "json_attributes_topic_suffix": OTA.ATTRIBUTES_SUFFIX,
                    "icon": "mdi:package-down",
                    "entity_category": "diagnostic",
                },
            },
        ]

    def complications(self):
        if self._complications is None:
            self._complications = [
                Complication("full", FULL[0], FULL[1], self._build_group),
            ]
        return self._complications
