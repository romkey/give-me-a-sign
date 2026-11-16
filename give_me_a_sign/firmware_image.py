# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""
give-me-a-sign/firmware_image - firmware image plumbing for OTA updates
=======================================================================

The byte-level half of :mod:`give_me_a_sign.ota`: UF2 unwrapping, pulling
the application out of a whole-flash image, and handing aligned blocks to
``dualbank``. None of it knows about the sign, MQTT or the display, so it
can be exercised on its own.

* Author: John Romkey
"""

import struct

try:
    import dualbank
except ImportError:  # pragma: no cover - only on boards without dualbank
    dualbank = None

UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_BLOCK_SIZE = 512
UF2_HEADER_SIZE = 32
UF2_DATA_SIZE = 476

#: Block is not meant for the main flash area (skip it).
UF2_FLAG_NOT_MAIN_FLASH = 0x00000001
#: Block is part of a file container, not a firmware image (skip it).
UF2_FLAG_FILE_CONTAINER = 0x00001000

#: esp_ota_write() wants 4 KiB-aligned writes, so buffer up to a flash page.
FLASH_BLOCK_SIZE = 4096

#: First byte of any ESP32 flash image (bootloader or app).
ESP_IMAGE_MAGIC = 0xE9

#: Where an ESP-IDF partition table lives in a whole-flash image.
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0x1000
PARTITION_ENTRY_SIZE = 32
#: ESP_PARTITION_MAGIC, as the two bytes 0xAA 0x50 read little-endian.
PARTITION_MAGIC = 0x50AA
PARTITION_TYPE_APP = 0x00
#: factory, ota_0 - the slots a freshly flashed board boots from.
PARTITION_APP_SUBTYPES = (0x00, 0x10)

#: Bytes held back while deciding whether an image is app-only or whole-flash.
PREFIX_SCAN_BYTES = PARTITION_TABLE_OFFSET + PARTITION_TABLE_SIZE


class OTAError(Exception):
    """Raised inside the updater when an image can't be downloaded or flashed."""


class FlashWriter:
    """
    Buffers a byte stream and hands it to ``dualbank`` in aligned blocks.

    ``dualbank.flash()`` writes at an offset into the inactive OTA partition;
    the ESP-IDF OTA writer wants those offsets to land on flash-page
    boundaries, so bytes are accumulated until a full block is available.
    """

    def __init__(self, flasher=None, block_size=FLASH_BLOCK_SIZE):
        """Create a writer.

        Args:
            flasher: callable ``f(buffer, offset)``; defaults to ``dualbank.flash``
            block_size (int): bytes to accumulate before each flash write
        """
        self._flasher = flasher
        self._block_size = block_size
        self._buffer = bytearray()
        self._offset = 0

    @property
    def bytes_written(self) -> int:
        """Total bytes handed to ``dualbank`` so far."""
        return self._offset

    @property
    def pending(self) -> int:
        """Bytes buffered but not yet flashed."""
        return len(self._buffer)

    def _flash(self, data) -> None:
        flasher = self._flasher
        if flasher is None:
            if dualbank is None:
                raise OTAError("dualbank not available on this board")
            flasher = dualbank.flash
        # dualbank.flash() declares offset keyword-only, so it must be passed
        # by name: positionally it raises TypeError on hardware.
        flasher(bytes(data), offset=self._offset)
        self._offset += len(data)

    def write(self, data) -> None:
        """Buffer *data*, flashing every whole block it completes."""
        if not data:
            return
        self._buffer.extend(data)
        size = self._block_size
        # CircuitPython's bytearray has no __delitem__, so the consumed head
        # is dropped by reslicing rather than `del buffer[:size]`.
        while len(self._buffer) >= size:
            self._flash(self._buffer[:size])
            self._buffer = self._buffer[size:]

    def finish(self) -> int:
        """Flash whatever is left over and return the total byte count."""
        if self._buffer:
            self._flash(self._buffer)
            self._buffer = bytearray()
        return self._offset


def find_app_partition(table):
    """
    Return ``(offset, size)`` of the first app partition in *table*.

    *table* is the 4 KiB partition-table region of a whole-flash image.
    Returns ``None`` when it holds no partition table or no app partition.
    """
    index = 0
    best_offset = None
    best_size = 0
    while index + PARTITION_ENTRY_SIZE <= len(table):
        magic, ptype, subtype, offset, size = struct.unpack_from("<HBBII", table, index)
        if magic != PARTITION_MAGIC:
            break
        if ptype == PARTITION_TYPE_APP and subtype in PARTITION_APP_SUBTYPES:
            if best_offset is None or offset < best_offset:
                best_offset = offset
                best_size = size
        index += PARTITION_ENTRY_SIZE
    if best_offset is None:
        return None
    return (best_offset, best_size)


class AppImageFilter:
    """
    Feeds only the application image to a sink, whatever the file holds.

    ``dualbank`` writes one OTA app partition, so it wants an app-only
    image. The artifacts CircuitPython publishes per board - both the
    ``.bin`` and the ``.uf2`` - are instead whole-flash images: the
    second-stage bootloader at 0, the partition table at 0x8000, then the
    app at whatever offset that table gives (0x10000 on a MatrixPortal S3).
    Flashing those bytes straight into an OTA slot would write a bootloader
    where an app belongs.

    So the leading bytes are held back until the partition table's position
    can be checked. A table there means whole-flash: everything before the
    app partition is dropped and the app is passed through. No table there
    means the file is already app-only and every byte is passed through.
    """

    def __init__(self, sink, scan_bytes=PREFIX_SCAN_BYTES):
        """Create a filter that calls ``sink(bytes)`` with app bytes only."""
        self._sink = sink
        self._scan_bytes = scan_bytes
        self._prefix = bytearray()
        self._decided = False
        self._skip = 0
        self._remaining = None
        self._app_offset = None
        self._whole_flash = False

    @property
    def app_offset(self):
        """Flash offset the app was found at, or ``None`` before deciding."""
        return self._app_offset

    @property
    def whole_flash(self) -> bool:
        """True when the image turned out to carry a whole flash layout."""
        return self._whole_flash

    def feed(self, data) -> None:
        """Consume *data*, passing on whatever part of it is app image."""
        if not self._decided:
            if data:
                self._prefix.extend(data)
            if len(self._prefix) < self._scan_bytes:
                return
            self._decide()
            return
        if data:
            self._emit(data)

    def finish(self) -> None:
        """Decide on a file shorter than the scan window and flush it."""
        if not self._decided:
            self._decide()

    def _decide(self) -> None:
        prefix = self._prefix
        self._prefix = bytearray()
        self._decided = True

        if not prefix:
            raise OTAError("empty image")
        if prefix[0] != ESP_IMAGE_MAGIC:
            raise OTAError(f"not an ESP32 firmware image (first byte {prefix[0]:#04x})")

        table = prefix[PARTITION_TABLE_OFFSET : PARTITION_TABLE_OFFSET + 2]
        if len(table) < 2 or struct.unpack_from("<H", table, 0)[0] != PARTITION_MAGIC:
            # app-only image: nothing to strip
            self._emit(prefix)
            return

        app = find_app_partition(
            prefix[
                PARTITION_TABLE_OFFSET : PARTITION_TABLE_OFFSET + PARTITION_TABLE_SIZE
            ]
        )
        if app is None:
            raise OTAError("whole-flash image has no app partition")

        offset, size = app
        self._whole_flash = True
        self._app_offset = offset
        self._remaining = size
        if offset <= len(prefix):
            self._emit(prefix[offset:])
        else:
            self._skip = offset - len(prefix)

    def _emit(self, data) -> None:
        if self._skip:
            if len(data) <= self._skip:
                self._skip -= len(data)
                return
            data = data[self._skip :]
            self._skip = 0
        if self._remaining is not None:
            if self._remaining <= 0:
                return
            if len(data) > self._remaining:
                data = data[: self._remaining]
            self._remaining -= len(data)
        if data:
            self._sink(bytes(data))


class UF2Unwrapper:
    """
    Strips UF2 block headers from a stream, passing payloads to a sink.

    Blocks arrive in whatever sized pieces the socket produces, so partial
    blocks are held until the full 512 bytes are in hand. Payloads are
    written in target-address order; a gap between two blocks is filled with
    ``0xFF`` so the image stays positionally correct.
    """

    def __init__(self, sink):
        """Create an unwrapper that calls ``sink(bytes)`` with payload data."""
        self._sink = sink
        self._tail = bytearray()
        self._base_address = None
        self._next_address = None
        self._blocks = 0

    @property
    def blocks(self) -> int:
        """Number of UF2 blocks whose payload was written."""
        return self._blocks

    @property
    def base_address(self):
        """Target address of the first flashed block, or ``None``."""
        return self._base_address

    def feed(self, data) -> None:
        """Consume *data*, emitting the payload of every complete block."""
        if data:
            self._tail.extend(data)
        while len(self._tail) >= UF2_BLOCK_SIZE:
            block = bytes(self._tail[:UF2_BLOCK_SIZE])
            self._tail = self._tail[UF2_BLOCK_SIZE:]
            self._block(block)

    def finish(self) -> None:
        """Assert the stream ended on a block boundary."""
        if self._tail:
            raise OTAError(f"UF2 image truncated: {len(self._tail)} trailing bytes")
        if self._blocks == 0:
            raise OTAError("UF2 image contained no flashable blocks")

    def _block(self, block) -> None:
        (
            magic0,
            magic1,
            flags,
            target_address,
            payload_size,
            _block_no,
            _num_blocks,
            _file_size,
        ) = struct.unpack_from("<8I", block, 0)
        (magic_end,) = struct.unpack_from("<I", block, UF2_BLOCK_SIZE - 4)

        if (
            magic0 != UF2_MAGIC_START0
            or magic1 != UF2_MAGIC_START1
            or magic_end != UF2_MAGIC_END
        ):
            raise OTAError("bad UF2 block magic")

        if flags & (UF2_FLAG_NOT_MAIN_FLASH | UF2_FLAG_FILE_CONTAINER):
            return

        if payload_size > UF2_DATA_SIZE:
            raise OTAError(f"bad UF2 payload size {payload_size}")

        if self._base_address is None:
            self._base_address = target_address
            self._next_address = target_address
        elif target_address < self._next_address:
            raise OTAError("UF2 blocks are out of order")
        elif target_address > self._next_address:
            gap = target_address - self._next_address
            self._sink(b"\xff" * gap)
            self._next_address = target_address

        payload = block[UF2_HEADER_SIZE : UF2_HEADER_SIZE + payload_size]
        self._sink(payload)
        self._next_address += payload_size
        self._blocks += 1


def looks_like_uf2(head) -> bool:
    """True when *head* (at least 8 bytes) starts with the UF2 magic words."""
    if len(head) < 8:
        return False
    magic0, magic1 = struct.unpack_from("<2I", head, 0)
    return magic0 == UF2_MAGIC_START0 and magic1 == UF2_MAGIC_START1
