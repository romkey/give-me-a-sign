# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for firmware image parsing: UF2, partition tables, flashing."""

import struct
from types import SimpleNamespace

import pytest

from firmware_images import (
    NoDelBytearray,
    REAL_PARTITION_TABLE,
    Sink,
    app_image,
    partition_entry,
    uf2_block,
    uf2_image,
    whole_flash_image,
)
from give_me_a_sign import firmware_image as image_module
from give_me_a_sign import ota as ota_module
from give_me_a_sign.firmware_image import (
    FLASH_BLOCK_SIZE,
    AppImageFilter,
    FlashWriter,
    OTAError,
    UF2Unwrapper,
    looks_like_uf2,
)


def test_looks_like_uf2_detects_magic():
    assert looks_like_uf2(uf2_block(b"\x01\x02", 0x10000, 0, 1)[:8])
    assert not looks_like_uf2(b"\xe9\x00\x00\x00\x00\x00\x00\x00")
    assert not looks_like_uf2(b"\x55")


def test_uf2_unwrapper_strips_headers():
    payloads = [bytes([index]) * 256 for index in range(4)]
    sink = Sink()
    unwrapper = UF2Unwrapper(sink)
    unwrapper.feed(uf2_image(payloads))
    unwrapper.finish()

    assert bytes(sink.data) == b"".join(payloads)
    assert unwrapper.blocks == 4
    assert unwrapper.base_address == 0x10000


def test_uf2_unwrapper_handles_split_chunks():
    payloads = [bytes([index]) * 256 for index in range(3)]
    image = uf2_image(payloads)
    sink = Sink()
    unwrapper = UF2Unwrapper(sink)
    for start in range(0, len(image), 37):
        unwrapper.feed(image[start : start + 37])
    unwrapper.finish()

    assert bytes(sink.data) == b"".join(payloads)


def test_uf2_unwrapper_skips_non_flash_blocks():
    payloads = [b"\xaa" * 256, b"\xbb" * 256, b"\xcc" * 256]
    image = uf2_image(
        payloads,
        flags_for=lambda index: image_module.UF2_FLAG_NOT_MAIN_FLASH
        if index == 1
        else 0,
    )
    sink = Sink()
    unwrapper = UF2Unwrapper(sink)
    unwrapper.feed(image)
    unwrapper.finish()

    assert bytes(sink.data) == payloads[0] + payloads[2]
    assert unwrapper.blocks == 2


def test_uf2_unwrapper_pads_address_gaps():
    sink = Sink()
    unwrapper = UF2Unwrapper(sink)
    unwrapper.feed(uf2_block(b"\xaa" * 16, 0x10000, 0, 2))
    unwrapper.feed(uf2_block(b"\xbb" * 16, 0x10020, 1, 2))
    unwrapper.finish()

    assert bytes(sink.data) == b"\xaa" * 16 + b"\xff" * 16 + b"\xbb" * 16


def test_uf2_unwrapper_rejects_bad_magic():
    block = bytearray(uf2_block(b"\x00" * 16, 0x10000, 0, 1))
    block[0] = 0
    unwrapper = UF2Unwrapper(Sink())
    with pytest.raises(OTAError):
        unwrapper.feed(bytes(block))


def test_uf2_unwrapper_rejects_truncated_image():
    unwrapper = UF2Unwrapper(Sink())
    unwrapper.feed(uf2_block(b"\x00" * 16, 0x10000, 0, 1)[:300])
    with pytest.raises(OTAError):
        unwrapper.finish()


def test_flash_writer_aligns_blocks():
    writes = []
    writer = FlashWriter(lambda buffer, *, offset: writes.append((offset, len(buffer))))
    writer.write(b"\x01" * (FLASH_BLOCK_SIZE + 10))
    assert writes == [(0, FLASH_BLOCK_SIZE)]
    assert writer.pending == 10

    total = writer.finish()
    assert writes == [(0, FLASH_BLOCK_SIZE), (FLASH_BLOCK_SIZE, 10)]
    assert total == FLASH_BLOCK_SIZE + 10
    assert writer.bytes_written == total


def test_flash_writer_without_dualbank_raises(monkeypatch):
    monkeypatch.setattr(ota_module, "dualbank", None)
    writer = FlashWriter()
    with pytest.raises(OTAError):
        writer.write(b"\x00" * FLASH_BLOCK_SIZE)


def test_flash_writer_without_delitem(fake_dualbank, monkeypatch):
    """The writer's own block buffer must not need del either."""
    # pylint: disable=unused-argument
    monkeypatch.setattr(image_module, "bytearray", NoDelBytearray, raising=False)
    sink = Sink()

    def flasher(data, *, offset):  # pylint: disable=unused-argument
        sink(data)

    writer = image_module.FlashWriter(flasher=flasher)
    for _ in range(5):
        writer.write(b"\xa5" * 3000)
    assert writer.finish() == 15000
    assert bytes(sink.data) == b"\xa5" * 15000


def test_find_app_partition_picks_the_first_app_slot():
    table = (
        partition_entry("nvs", 0x01, 0x02, 0x9000, 0x5000)
        + partition_entry("ota_1", 0x00, 0x11, 0x210000, 0x200000)
        + partition_entry("ota_0", 0x00, 0x10, 0x010000, 0x200000)
    )
    assert image_module.find_app_partition(table) == (0x010000, 0x200000)


def test_find_app_partition_without_a_table():
    assert image_module.find_app_partition(b"\x00" * 64) is None


def test_app_image_filter_strips_a_whole_flash_image():
    app = bytes(range(256)) * 40
    sink = Sink()
    image_filter = AppImageFilter(sink)
    image = whole_flash_image(app)
    for start in range(0, len(image), 1111):
        image_filter.feed(image[start : start + 1111])
    image_filter.finish()

    assert bytes(sink.data) == app
    assert image_filter.whole_flash is True
    assert image_filter.app_offset == 0x10000


def test_app_image_filter_stops_at_the_app_partition_end():
    app = bytes(range(256)) * 8
    sink = Sink()
    image_filter = AppImageFilter(sink)
    image_filter.feed(whole_flash_image(app, app_size=512) + b"\xcc" * 4096)
    image_filter.finish()

    assert bytes(sink.data) == app[:512]


def test_app_image_filter_passes_an_app_only_image_through():
    app = bytes([image_module.ESP_IMAGE_MAGIC]) + bytes(range(256)) * 300
    sink = Sink()
    image_filter = AppImageFilter(sink)
    for start in range(0, len(app), 997):
        image_filter.feed(app[start : start + 997])
    image_filter.finish()

    assert bytes(sink.data) == app
    assert image_filter.whole_flash is False


def test_app_image_filter_passes_a_short_image_through():
    app = bytes([image_module.ESP_IMAGE_MAGIC]) + b"\x11" * 100
    sink = Sink()
    image_filter = AppImageFilter(sink)
    image_filter.feed(app)
    image_filter.finish()

    assert bytes(sink.data) == app


def test_app_image_filter_rejects_a_non_esp_image():
    image_filter = AppImageFilter(Sink())
    with pytest.raises(OTAError) as error:
        image_filter.feed(b"<!DOCTYPE html>" * 100)
        image_filter.finish()
    assert "not an ESP32 firmware image" in str(error.value)


def test_app_image_filter_rejects_a_table_without_an_app():
    sink = Sink()
    image_filter = AppImageFilter(sink)
    image = bytearray(whole_flash_image(b"\x00" * 16))
    offset = image_module.PARTITION_TABLE_OFFSET
    # keep the table magic, drop the app entries
    image[offset + 64 : offset + 128] = b"\x00" * 64
    image[offset : offset + 64] = partition_entry(
        "nvs", 0x01, 0x02, 0x9000, 0x5000
    ) + partition_entry("otadata", 0x01, 0x00, 0xE000, 0x2000)
    with pytest.raises(OTAError) as error:
        image_filter.feed(bytes(image))
    assert "no app partition" in str(error.value)


def test_partition_magic_is_the_little_endian_word_on_disk():
    """0xAA 0x50 on disk reads as 0x50AA - getting this backwards made every
    whole-flash image look app-only."""
    assert image_module.PARTITION_MAGIC == 0x50AA
    assert struct.unpack_from("<H", b"\xaa\x50", 0)[0] == image_module.PARTITION_MAGIC


def test_find_app_partition_reads_a_real_published_table():
    """Parse the bytes a real CircuitPython .bin carries, not our own."""
    assert image_module.find_app_partition(REAL_PARTITION_TABLE) == (
        0x010000,
        0x200000,
    )
