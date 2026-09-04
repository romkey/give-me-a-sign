# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for message payload normalization."""

import pytest

from give_me_a_sign.message import Message
from give_me_a_sign.module import ModuleStore


class _App:
    def __init__(self):
        self.canvas_width = 64
        self.canvas_height = 32


@pytest.fixture
def message(monkeypatch):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    return Message(_App())


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"text": "hello"}', {"text": "hello"}),
        ("hello", {"text": "hello"}),
        ('{"message": "hello"}', {"text": "hello"}),
        ('{"text": "hi", "message": "ignored"}', {"text": "hi", "message": "ignored"}),
        ('{"color": 255, "text": "hi"}', {"color": 255, "text": "hi"}),
    ],
)
def test_normalize_payload(message, raw, expected):
    """Plain text, a JSON object, and Home Assistant's "message" key."""
    assert message.normalize_payload(Message.KEY, raw) == expected
