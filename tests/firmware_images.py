# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Builders for the firmware images the OTA tests feed to the updater."""

import struct

from give_me_a_sign import firmware_image as image_module


def uf2_block(payload, target_address, block_no, num_blocks, flags=0):
    block = bytearray(512)
    struct.pack_into(
        "<8I",
        block,
        0,
        image_module.UF2_MAGIC_START0,
        image_module.UF2_MAGIC_START1,
        flags,
        target_address,
        len(payload),
        block_no,
        num_blocks,
        0,
    )
    block[32 : 32 + len(payload)] = payload
    struct.pack_into("<I", block, 508, image_module.UF2_MAGIC_END)
    return bytes(block)


def uf2_image(payloads, base=0x10000, flags_for=None):
    blocks = []
    address = base
    for index, payload in enumerate(payloads):
        flags = 0 if flags_for is None else flags_for(index)
        blocks.append(uf2_block(payload, address, index, len(payloads), flags))
        if not flags:
            address += len(payload)
    return b"".join(blocks)


def app_image(body):
    """An app-only ESP32 image: the same bytes, with the image magic in front.

    Every image the updater accepts has to start with 0xE9, so test bodies
    that stand in for firmware carry it too.
    """
    return bytes([image_module.ESP_IMAGE_MAGIC]) + bytes(body)[1:]


class Sink:
    def __init__(self):
        self.data = bytearray()

    def __call__(self, chunk):
        self.data.extend(chunk)


class NoDelBytearray(bytearray):
    """A bytearray without __delitem__, as CircuitPython's bytearray is.

    CPython allows ``del buf[:n]``; CircuitPython raises TypeError, which
    the broad except in _pump() reported as "flash failed".
    """

    def __delitem__(self, key):
        raise TypeError("'bytearray' object doesn't support item deletion")


def partition_entry(name, ptype, subtype, offset, size):
    entry = bytearray(32)
    struct.pack_into(
        "<HBBII", entry, 0, image_module.PARTITION_MAGIC, ptype, subtype, offset, size
    )
    entry[12 : 12 + len(name)] = name.encode()
    return bytes(entry)


def whole_flash_image(app, app_offset=0x10000, app_size=0x200000):
    """A CircuitPython-style image: bootloader, partition table, then the app.

    This is the shape of every artifact on downloads.circuitpython.org - the
    .bin and the .uf2 alike - so it is the shape OTA actually has to eat.
    """
    image = bytearray(b"\xff" * app_offset)
    image[0:1] = bytes([image_module.ESP_IMAGE_MAGIC])
    image[1:24] = b"\x03\x02?" + b"\x5a" * 20  # bootloader header bytes
    table = (
        partition_entry("nvs", 0x01, 0x02, 0x9000, 0x5000)
        + partition_entry("otadata", 0x01, 0x00, 0xE000, 0x2000)
        + partition_entry("ota_0", 0x00, 0x10, app_offset, app_size)
        + partition_entry("ota_1", 0x00, 0x11, app_offset + app_size, app_size)
    )
    offset = image_module.PARTITION_TABLE_OFFSET
    image[offset : offset + len(table)] = table
    return bytes(image) + app


#: The first three partition entries of
#: adafruit-circuitpython-adafruit_matrixportal_s3-en_US-11.0.0-alpha.3.bin,
#: read straight out of the published file at offset 0x8000.
REAL_PARTITION_TABLE = bytes.fromhex(
    "aa50010200900000005000006e76730000000000000000000000000000000000"
    "aa50010000e00000002000006f74616461746100000000000000000000000000"
    "aa50001000000100000020006f74615f30000000000000000000000000000000"
)
