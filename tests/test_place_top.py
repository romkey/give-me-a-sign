# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for the place_top label helper."""

import pytest

from give_me_a_sign.complication import place_top


class _Label:
    def __init__(self, top, height):
        self.y = None
        self.bounding_box = [0, top, 30, height]


@pytest.mark.parametrize(
    "top,height",
    [
        (-2, 6),  # intelone-mono-6, measured
        (-5, 12),  # terminalio.FONT, measured
        (0, 8),  # a font whose y already is its top edge
    ],
)
def test_place_top_lands_the_first_pixel_row_on_the_target(top, height):
    label = _Label(top, height)

    place_top(label)
    assert label.y + label.bounding_box[1] == 0

    place_top(label, 16)
    assert label.y + label.bounding_box[1] == 16


def test_place_top_matches_the_hand_tuned_mini_clock_value():
    """
    append_mini_clock used a hardcoded y of 2, which was correct for the 6px
    mini font. place_top must reproduce it rather than shift the clock.
    """
    label = _Label(-2, 6)
    place_top(label)
    assert label.y == 2
