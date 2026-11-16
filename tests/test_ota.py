# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for the OTA firmware updater."""

import json
import struct
from types import SimpleNamespace

import pytest

from firmware_images import (
    NoDelBytearray,
    Sink,
    app_image,
    uf2_image,
    whole_flash_image,
)
from give_me_a_sign import firmware_image as image_module
from give_me_a_sign import ota as ota_module
from give_me_a_sign.module import ModuleStore
from give_me_a_sign.firmware_image import (
    FLASH_BLOCK_SIZE,
    AppImageFilter,
    FlashWriter,
    OTAError,
    UF2Unwrapper,
    looks_like_uf2,
)
from give_me_a_sign.ota import MIN_IMAGE_BYTES, OTA


class _Response:
    def __init__(self, body, status_code=200, chunk_size=None, headers=None):
        self.body = body
        self.status_code = status_code
        self._chunk_size = chunk_size
        self.headers = (
            {"content-length": str(len(body))} if headers is None else headers
        )
        self.closed = False

    def iter_content(self, chunk_size):
        size = self._chunk_size or chunk_size
        for start in range(0, len(self.body), size):
            yield self.body[start : start + size]

    def close(self):
        self.closed = True


class _Session:
    def __init__(self, response):
        self.response = response
        self.requested = None

    def get(self, url, stream=False):  # pylint: disable=unused-argument
        self.requested = url
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _Platform:
    def __init__(self, session=None):
        self.session = session
        self.published = []
        self.mqtt_base_topic = "givemeasign/sign/aa_bb"
        self.wifi_is_connected = True

    def get_requests_session(self):
        return self.session

    def mqtt_publish(self, topic, payload, retain=True, qos=1):
        self.published.append((topic, payload, retain, qos))
        return True


class _Logger:
    def __init__(self):
        self.errors = []
        self.infos = []

    def error(self, message):
        self.errors.append(message)

    def info(self, message):
        self.infos.append(message)


class _App:
    def __init__(self, platform):
        self.platform = platform
        self.active_interrupt = None
        self.system_screen = None
        self.logger = _Logger()
        self.canvas_width = 64
        self.canvas_height = 32
        self.shown = None

    def show_group(self, group):
        self.shown = group


def _make_ota(monkeypatch, session=None):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    monkeypatch.setattr(ModuleStore, "_save", lambda self: True)
    platform = _Platform(session)
    app = _App(platform)
    return OTA(app), platform


# ---------------------------------------------------------------- UF2 parsing


# ---------------------------------------------------------------- flash writer


# ---------------------------------------------------------------- the module


def _drain(ota, limit=2000):
    for _ in range(limit):
        if ota.state not in (ota_module.STATE_DOWNLOADING,):
            return
        ota.background()
    raise AssertionError("download never finished")


def test_install_bin_flashes_and_switches(monkeypatch, fake_dualbank):
    image = app_image(bytes(range(256)) * (MIN_IMAGE_BYTES // 256 + 1))
    session = _Session(_Response(image))
    ota, platform = _make_ota(monkeypatch, session)

    ota.receive("ota_url", "https://example.invalid/firmware.bin")
    ota.receive("ota_install", "install")
    _drain(ota)

    assert session.requested == "https://example.invalid/firmware.bin"
    assert b"".join(data for _, data in fake_dualbank.writes) == image
    assert [offset for offset, _ in fake_dualbank.writes][:2] == [0, FLASH_BLOCK_SIZE]
    assert fake_dualbank.switched
    assert ota.state == ota_module.STATE_COUNTDOWN
    assert ota.status_message.startswith("rebooting in")
    assert session.response.closed

    topics = [topic for topic, _, _, _ in platform.published]
    assert f"{platform.mqtt_base_topic}/ota/state" in topics
    assert f"{platform.mqtt_base_topic}/ota/url" in topics


def test_install_uf2_strips_headers_before_flashing(monkeypatch, fake_dualbank):
    payloads = [bytes([index % 256]) * 256 for index in range(MIN_IMAGE_BYTES // 256)]
    payloads[0] = app_image(payloads[0])
    session = _Session(_Response(uf2_image(payloads), chunk_size=1000))
    ota, _ = _make_ota(monkeypatch, session)

    ota.receive("ota_install", "https://example.invalid/firmware.uf2")
    _drain(ota)

    flashed = b"".join(data for _, data in fake_dualbank.writes)
    assert flashed == b"".join(payloads)
    assert fake_dualbank.switched
    assert ota.state == ota_module.STATE_COUNTDOWN


def test_countdown_reboots_after_five_seconds(monkeypatch, fake_dualbank):
    image = app_image(b"\x5a" * (MIN_IMAGE_BYTES + 32))
    ota, platform = _make_ota(monkeypatch, _Session(_Response(image)))

    now = [1_000_000_000]
    monkeypatch.setattr(ota_module.time, "monotonic_ns", lambda: now[0])
    resets = []
    monkeypatch.setattr(
        ota_module.microcontroller, "reset", lambda: resets.append(True)
    )

    ota.receive("ota_install", "https://example.invalid/firmware.bin")
    _drain(ota)
    assert ota.status_message == "rebooting in 5s"

    for remaining in (4, 3, 2, 1):
        now[0] += 1_000_000_000
        ota.background()
        assert ota.status_message == f"rebooting in {remaining}s"
        assert not resets

    now[0] += 1_000_000_000
    ota.background()
    assert resets == [True]
    assert ota.status_message == "rebooting now"
    assert fake_dualbank.switched

    states = [
        payload
        for topic, payload, _, _ in platform.published
        if topic.endswith("/ota/state")
    ]
    assert "rebooting in 5s" in states
    assert states[-1] == "rebooting now"


def test_http_error_reports_failure(monkeypatch, fake_dualbank):
    session = _Session(_Response(b"nope", status_code=404))
    ota, platform = _make_ota(monkeypatch, session)

    ota.receive("ota_install", "https://example.invalid/missing.bin")

    assert ota.state == ota_module.STATE_FAILED
    assert ota.status_message == "failed: HTTP 404"
    assert not fake_dualbank.switched

    ota.background()
    attributes = [
        json.loads(payload)
        for topic, payload, _, _ in platform.published
        if topic.endswith("/ota/attributes")
    ]
    assert attributes[-1]["state"] == "failed"
    assert attributes[-1]["error"] == "HTTP 404"


def test_short_image_is_rejected(monkeypatch, fake_dualbank):
    ota, _ = _make_ota(monkeypatch, _Session(_Response(app_image(b"\x00" * 1024))))

    ota.receive("ota_install", "https://example.invalid/tiny.bin")
    _drain(ota)

    assert ota.state == ota_module.STATE_FAILED
    assert "too small" in ota.status_message
    assert not fake_dualbank.switched


def test_install_without_url_fails(monkeypatch, fake_dualbank):
    ota, _ = _make_ota(monkeypatch, _Session(_Response(b"")))

    ota.receive("ota_install", "install")

    assert ota.state == ota_module.STATE_FAILED
    assert ota.status_message.startswith("failed: no firmware URL set")
    # the message has to say how to fix it, not just that it is broken
    assert "module/ota_url" in ota.status_message
    assert not fake_dualbank.switched


def test_url_accepts_json_and_bare_text(monkeypatch):
    ota, _ = _make_ota(monkeypatch)

    ota.receive("ota_url", '{"url": "https://example.invalid/a.bin"}')
    assert ota.url == "https://example.invalid/a.bin"

    ota.receive("ota_url", "https://example.invalid/b.uf2")
    assert ota.url == "https://example.invalid/b.uf2"

    ota.receive("ota_url", "not-a-url")
    assert ota.url == "https://example.invalid/b.uf2"
    assert ota._app.logger.errors  # pylint: disable=protected-access


def test_missing_dualbank_fails_cleanly(monkeypatch):
    monkeypatch.setattr(ota_module, "dualbank", None)
    ota, _ = _make_ota(
        monkeypatch, _Session(_Response(app_image(b"\x00" * MIN_IMAGE_BYTES)))
    )

    ota.receive("ota_install", "https://example.invalid/firmware.bin")

    assert ota.state == ota_module.STATE_FAILED
    assert "dualbank" in ota.status_message


def test_progress_tracks_content_length(monkeypatch, fake_dualbank):
    image = app_image(b"\x11" * (MIN_IMAGE_BYTES * 2))
    ota, _ = _make_ota(monkeypatch, _Session(_Response(image)))

    ota.receive("ota_install", "https://example.invalid/firmware.bin")
    assert ota.state == ota_module.STATE_DOWNLOADING
    ota.background()
    assert 0 < ota.progress < 100
    assert ota.status_message.startswith("downloading ")

    _drain(ota)
    assert ota.progress == 100


def test_update_owns_the_display_without_rebuilding(monkeypatch, fake_dualbank):
    """Ownership is level-triggered; repainting is not.

    The main loop asks every pass, so the update must keep the matrix for the
    whole download — but it must reuse its group until the text changes, or a
    multi-megabyte flash rebuilds labels thousands of times.
    """
    image = app_image(b"\x33" * (MIN_IMAGE_BYTES * 4))
    ota, _ = _make_ota(monkeypatch, _Session(_Response(image)))
    app = ota._app

    assert not ota.wants_interrupt()

    ota.receive("ota_install", "https://example.invalid/firmware.bin")
    assert ota.wants_interrupt()

    assert ota.show()
    group = app.shown
    assert group is not None

    # Same text on later passes: the group is repainted, never rebuilt.
    message = ota.status_message
    for _ in range(5):
        ota.show()
        assert app.shown is group
    assert ota.status_message == message
    assert ota.wants_interrupt()

    # New text earns exactly one rebuild.
    while ota.state == ota_module.STATE_DOWNLOADING and (ota.status_message == message):
        ota.background()
    ota.show()
    assert app.shown is not group
    rebuilt = app.shown
    ota.show()
    assert app.shown is rebuilt


def test_display_is_held_with_no_content_length(monkeypatch, fake_dualbank):
    """Without Content-Length the text is static, and must still hold the screen."""
    image = app_image(b"\x44" * (MIN_IMAGE_BYTES + 512))
    response = _Response(image, headers={})
    ota, _ = _make_ota(monkeypatch, _Session(response))

    ota.receive("ota_install", "https://example.invalid/firmware.bin")
    assert ota.progress == 0  # no total to measure against

    # Paint once, so the "has the text changed?" question answers "no" from
    # here on: the static text must not cost the update its screen.
    ota.show()
    for _ in range(3):
        ota.background()
        if ota.state != ota_module.STATE_DOWNLOADING:
            break
        assert ota.wants_interrupt()

    _drain(ota)
    assert ota.state == ota_module.STATE_COUNTDOWN
    assert fake_dualbank.switched


def test_failure_holds_the_matrix_then_releases_it(monkeypatch, fake_dualbank):
    now = [5_000_000_000]
    monkeypatch.setattr(ota_module.time, "monotonic_ns", lambda: now[0])
    ota, _ = _make_ota(monkeypatch, _Session(_Response(b"nope", status_code=404)))

    ota.receive("ota_install", "https://example.invalid/missing.bin")
    assert ota.state == ota_module.STATE_FAILED
    assert ota.wants_interrupt()
    ota.show()
    assert ota.wants_interrupt()  # still ours, unlike a one-shot edge trigger

    now[0] += (ota_module.FAILED_DISPLAY_S + 1) * 1_000_000_000
    assert not ota.wants_interrupt()
    assert not fake_dualbank.switched

    # A repeat failure with identical text must win the screen back.
    ota.receive("ota_install", "https://example.invalid/missing.bin")
    assert ota.wants_interrupt()


def test_update_defers_to_another_live_interrupt(monkeypatch, fake_dualbank):
    """A message mid-download must get its full turn, not a single pass.

    Greet, Message, and Image clear their updated flag inside show(), so an
    update that claimed the matrix unconditionally would swallow them for the
    length of the flash.
    """
    image = app_image(b"\x77" * (MIN_IMAGE_BYTES * 2))
    ota, _ = _make_ota(monkeypatch, _Session(_Response(image)))
    app = ota._app

    ota.receive("ota_install", "https://example.invalid/firmware.bin")
    assert ota.wants_interrupt()

    other = object()
    app.active_interrupt = other
    assert not ota.wants_interrupt()

    # The download carries on regardless of who owns the screen.
    received_before = ota.status_attributes()["bytes_received"]
    ota.background()
    assert ota.status_attributes()["bytes_received"] > received_before

    app.active_interrupt = None
    assert ota.wants_interrupt()

    # Being the active interrupt itself is not a reason to stand down.
    app.active_interrupt = ota
    assert ota.wants_interrupt()


def test_update_defers_to_button_screens(monkeypatch, fake_dualbank):
    ota, _ = _make_ota(
        monkeypatch, _Session(_Response(app_image(b"\x77" * (MIN_IMAGE_BYTES + 16))))
    )
    app = ota._app

    ota.receive("ota_install", "https://example.invalid/firmware.bin")

    for screen in ("ip", "splash"):
        app.system_screen = screen
        assert not ota.wants_interrupt()
    app.system_screen = None
    assert ota.wants_interrupt()


def test_failure_lease_matches_its_window(monkeypatch, fake_dualbank):
    """duration() must not extend the hold past FAILED_DISPLAY_S."""
    now = [9_000_000_000]
    monkeypatch.setattr(ota_module.time, "monotonic_ns", lambda: now[0])
    ota, _ = _make_ota(monkeypatch, _Session(_Response(b"nope", status_code=404)))

    ota.receive("ota_install", "https://example.invalid/missing.bin")
    assert ota.state == ota_module.STATE_FAILED
    assert ota.duration() == ota_module.FAILED_DISPLAY_S

    now[0] += 7 * 1_000_000_000
    assert ota.duration() == 3
    assert ota.wants_interrupt()

    # The last lease granted can't outlast the window by more than the
    # one-second granularity of the main loop's countdown.
    now[0] += 3 * 1_000_000_000
    assert not ota.wants_interrupt()
    assert ota.duration() == 1

    # A download, by contrast, keeps the ordinary lease.
    ota._state = ota_module.STATE_DOWNLOADING
    assert ota.duration() == OTA.DEFAULT_DURATION


def test_every_install_request_reports_on_the_console(monkeypatch, capsys):
    """Silence is the one unacceptable outcome: the module overrides the base
    receive(), so it has to say what arrived and what it decided itself."""
    ota, _ = _make_ota(monkeypatch, _Session(_Response(b"")))

    ota.receive("ota_install", "install")
    out = capsys.readouterr().out

    assert "ota: ota_install <-" in out  # the payload arrived
    assert "install requested" in out  # and what it resolved to
    assert "no firmware URL set" in out  # and why it stopped
    assert ota._app.logger.infos  # base-style receive line, as other modules


def test_url_set_and_state_changes_report(monkeypatch, fake_dualbank, capsys):
    image = app_image(b"\x21" * (MIN_IMAGE_BYTES + 64))
    ota, _ = _make_ota(monkeypatch, _Session(_Response(image)))

    ota.receive("ota_url", "https://example.invalid/firmware.bin")
    assert "ota: url set via ota_url to https://example.invalid/firmware.bin" in (
        capsys.readouterr().out
    )

    ota.receive("ota_install", "install")
    _drain(ota)
    out = capsys.readouterr().out
    assert "ota: downloading" in out
    assert "ota: countdown" in out


def test_url_state_is_published_even_when_empty(monkeypatch):
    """Home Assistant's text box shows uncommitted typing until the device
    publishes its own view, so an empty URL has to be published too."""
    ota, platform = _make_ota(monkeypatch)

    ota.background()
    urls = [
        payload
        for topic, payload, _, _ in platform.published
        if topic.endswith("/ota/url")
    ]
    assert urls == [""]  # the sign has no URL, and says so

    # Unchanged on later passes: no retained-message spam.
    for _ in range(3):
        ota.background()
    assert len([t for t, _, _, _ in platform.published if t.endswith("/ota/url")]) == 1

    ota.receive("ota_url", "https://example.invalid/firmware.bin")
    urls = [
        payload
        for topic, payload, _, _ in platform.published
        if topic.endswith("/ota/url")
    ]
    assert urls == ["", "https://example.invalid/firmware.bin"]

    ota.background()
    assert len([t for t, _, _, _ in platform.published if t.endswith("/ota/url")]) == 2


def test_either_url_entity_can_supply_the_url(monkeypatch):
    """Two entities, so the one shaped like Message can be compared against
    the one in the configuration section. Configuration wins if both are set.
    """
    ota, _ = _make_ota(monkeypatch)
    assert ota.url is None

    ota.receive("ota_url_main", "https://example.invalid/from-controls.bin")
    assert ota.url == "https://example.invalid/from-controls.bin"

    ota.receive("ota_url", "https://example.invalid/from-config.bin")
    assert ota.url == "https://example.invalid/from-config.bin"


def test_install_uses_whichever_url_entity_is_set(monkeypatch, fake_dualbank):
    session = _Session(_Response(app_image(b"\x81" * (MIN_IMAGE_BYTES + 8))))
    ota, _ = _make_ota(monkeypatch, session)

    ota.receive("ota_url_main", "https://example.invalid/from-controls.bin")
    ota.receive("ota_install", "install")
    _drain(ota)

    assert session.requested == "https://example.invalid/from-controls.bin"
    assert fake_dualbank.switched


def test_firmware_version_is_read_from_the_url():
    from give_me_a_sign.ota import (  # pylint: disable=import-outside-toplevel
        firmware_version_from_url,
    )

    assert (
        firmware_version_from_url(
            "https://downloads.circuitpython.org/bin/adafruit_matrixportal_s3/"
            "en_US/adafruit-circuitpython-adafruit_matrixportal_s3-en_US-10.0.0.bin"
        )
        == "10.0.0"
    )
    assert firmware_version_from_url("http://h/firmware.uf2") == "firmware"
    assert firmware_version_from_url("http://h/build-9.2.1-beta.bin") == "9.2.1"
    assert firmware_version_from_url(None) is None


def test_update_entity_offers_install_only_with_a_url(monkeypatch):
    ota, platform = _make_ota(monkeypatch)

    idle = ota.update_attributes()
    assert idle["installed_version"] == idle["latest_version"]  # nothing to do
    assert idle["in_progress"] is False
    assert idle["update_percentage"] is None

    ota.receive("ota_url", "https://example.invalid/fw-10.0.0.bin")
    offered = ota.update_attributes()
    assert offered["latest_version"] == "10.0.0"
    assert offered["latest_version"] != offered["installed_version"]
    assert offered["release_url"] == "https://example.invalid/fw-10.0.0.bin"

    ota.background()
    assert any(topic.endswith("/ota/update") for topic, _, _, _ in platform.published)


def test_update_entity_reports_progress(monkeypatch, fake_dualbank):
    image = app_image(b"\x55" * (MIN_IMAGE_BYTES * 3))
    ota, _ = _make_ota(monkeypatch, _Session(_Response(image)))

    ota.receive("ota_install", "https://example.invalid/fw-10.0.0.bin")
    ota.background()

    progress = ota.update_attributes()
    assert progress["in_progress"] is True
    assert 0 < progress["update_percentage"] < 100


def test_status_is_cleared_on_startup(monkeypatch):
    """The status topic is retained, so a failure must not outlive a reboot."""
    ota, platform = _make_ota(monkeypatch)

    ota.background()
    states = [p for t, p, _, _ in platform.published if t.endswith("/ota/state")]
    assert states == ["idle"]

    attributes = [
        json.loads(p)
        for t, p, _, _ in platform.published
        if t.endswith("/ota/attributes")
    ]
    assert attributes[0]["error"] is None
    assert attributes[0]["state"] == "idle"
    assert attributes[0]["progress"] == 0


def test_start_update_reports_wifi_down(monkeypatch, fake_dualbank):
    """A None session means WiFi, not a mystery: say which."""
    # pylint: disable=unused-argument
    ota, platform = _make_ota(monkeypatch, session=None)
    platform.wifi_is_connected = False

    ota.receive("ota_install", "https://example.invalid/firmware.bin")

    assert ota.state == ota_module.STATE_FAILED
    assert "wifi is not connected" in ota.status_message


def test_start_update_reports_stale_platform(monkeypatch, fake_dualbank):
    """An install without get_requests_session is a half-updated library."""
    # pylint: disable=unused-argument
    ota, _platform = _make_ota(monkeypatch, session=None)
    monkeypatch.delattr(_Platform, "get_requests_session")

    ota.receive("ota_install", "https://example.invalid/firmware.bin")

    assert ota.state == ota_module.STATE_FAILED
    assert "stale give_me_a_sign install" in ota.status_message


def test_start_update_surfaces_session_error(monkeypatch, fake_dualbank):
    """A missing adafruit_requests should name itself in the status."""
    # pylint: disable=unused-argument
    ota, _platform = _make_ota(monkeypatch, session=None)

    def boom(self):  # pylint: disable=unused-argument
        raise RuntimeError("no module named 'adafruit_requests'")

    monkeypatch.setattr(_Platform, "get_requests_session", boom)

    ota.receive("ota_install", "https://example.invalid/firmware.bin")

    assert ota.state == ota_module.STATE_FAILED
    assert "adafruit_requests" in ota.status_message


def test_download_never_deletes_from_a_bytearray(monkeypatch, fake_dualbank):
    """A whole UF2 download has to run without del on any bytearray."""
    payloads = [bytes([index % 251]) * 256 for index in range(300)]
    payloads[0] = app_image(payloads[0])
    image = uf2_image(payloads)
    session = _Session(_Response(image, chunk_size=777))
    ota, _platform = _make_ota(monkeypatch, session)
    monkeypatch.setattr(image_module, "bytearray", NoDelBytearray, raising=False)
    monkeypatch.setattr(ota_module, "MIN_IMAGE_BYTES", 1024)

    ota.receive("ota_install", "https://example.invalid/firmware.uf2")
    for _ in range(200):
        ota.background()
        if ota.state != ota_module.STATE_DOWNLOADING:
            break

    assert ota.state == ota_module.STATE_COUNTDOWN, ota.status_message
    flashed = b"".join(data for _offset, data in fake_dualbank.writes)
    assert flashed == b"".join(payloads)


# ------------------------------------------------- whole-flash image handling


def test_download_strips_a_whole_flash_bin(monkeypatch, fake_dualbank):
    """The .bin on downloads.circuitpython.org is a whole-flash image: the
    bootloader at 0, the partition table at 0x8000, the app at 0x10000."""
    app = bytes(range(251)) * 500
    image = whole_flash_image(app)
    session = _Session(_Response(image))
    ota, _platform = _make_ota(monkeypatch, session)
    monkeypatch.setattr(ota_module, "MIN_IMAGE_BYTES", 1024)

    ota.receive("ota_install", "https://example.invalid/firmware.bin")
    for _ in range(400):
        ota.background()
        if ota.state != ota_module.STATE_DOWNLOADING:
            break

    assert ota.state == ota_module.STATE_COUNTDOWN, ota.status_message
    flashed = b"".join(data for _offset, data in fake_dualbank.writes)
    assert flashed == app
    assert fake_dualbank.writes[0][0] == 0


def test_download_strips_a_whole_flash_uf2(monkeypatch, fake_dualbank):
    """A .uf2 whose blocks are addressed from 0 in the whole flash, rather
    than from 0 in the app partition, has to be stripped the same way."""
    app = bytes(range(251)) * 500
    image = whole_flash_image(app)
    payloads = [image[start : start + 256] for start in range(0, len(image), 256)]
    session = _Session(_Response(uf2_image(payloads, base=0x0), chunk_size=1024))
    ota, _platform = _make_ota(monkeypatch, session)
    monkeypatch.setattr(ota_module, "MIN_IMAGE_BYTES", 1024)

    ota.receive("ota_install", "https://example.invalid/firmware.uf2")
    for _ in range(2000):
        ota.background()
        if ota.state != ota_module.STATE_DOWNLOADING:
            break

    assert ota.state == ota_module.STATE_COUNTDOWN, ota.status_message
    flashed = b"".join(data for _offset, data in fake_dualbank.writes)
    assert flashed.startswith(app)


def test_download_strips_an_app_only_uf2(monkeypatch, fake_dualbank):
    """CircuitPython's .uf2 addresses blocks from 0 inside the app partition,
    so its payload is already app-only and must pass through untouched."""
    app = app_image(bytes(range(251)) * 500)
    payloads = [app[start : start + 256] for start in range(0, len(app), 256)]
    session = _Session(_Response(uf2_image(payloads, base=0x0), chunk_size=1024))
    ota, _platform = _make_ota(monkeypatch, session)
    monkeypatch.setattr(ota_module, "MIN_IMAGE_BYTES", 1024)

    ota.receive("ota_install", "https://example.invalid/firmware.uf2")
    for _ in range(2000):
        ota.background()
        if ota.state != ota_module.STATE_DOWNLOADING:
            break

    assert ota.state == ota_module.STATE_COUNTDOWN, ota.status_message
    flashed = b"".join(data for _offset, data in fake_dualbank.writes)
    assert flashed == app


def test_a_new_url_replaces_the_failed_attempt(monkeypatch, fake_dualbank):
    """A failed install must not keep advertising its own version.

    _active_url outlived the attempt, and both the status sensor and the
    update entity preferred it over the stored URL, so after a 404 the
    Firmware entity went on offering the version from the bad URL however
    many times the user corrected the field.
    """
    ota, _platform = _make_ota(monkeypatch, _Session(_Response(b"nope", 404)))

    ota.receive("ota_install", "https://example.invalid/fw-9.9.9.bin")
    assert ota.state == ota_module.STATE_FAILED
    assert ota.update_attributes()["latest_version"] == "9.9.9"

    ota.receive("ota_url", "https://example.invalid/fw-10.0.0.bin")

    assert ota.state == ota_module.STATE_IDLE
    assert ota.update_attributes()["latest_version"] == "10.0.0"
    assert (
        ota.update_attributes()["release_url"]
        == "https://example.invalid/fw-10.0.0.bin"
    )
    assert ota.status_attributes()["url"] == "https://example.invalid/fw-10.0.0.bin"


def test_a_running_download_keeps_its_own_url(monkeypatch, fake_dualbank):
    """...but a URL set mid-download must not rewrite what is installing."""
    image = app_image(b"\x42" * (MIN_IMAGE_BYTES * 2))
    ota, _platform = _make_ota(monkeypatch, _Session(_Response(image)))

    ota.receive("ota_install", "https://example.invalid/fw-10.0.0.bin")
    assert ota.state == ota_module.STATE_DOWNLOADING

    ota.receive("ota_url", "https://example.invalid/fw-11.0.0.bin")

    assert ota.state == ota_module.STATE_DOWNLOADING
    assert ota.update_attributes()["latest_version"] == "10.0.0"
