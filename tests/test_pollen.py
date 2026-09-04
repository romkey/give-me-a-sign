# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for pollen count parsing."""

from give_me_a_sign.complication import HALF_WIDE
from give_me_a_sign.module import ModuleStore
from give_me_a_sign.pollen import Pollen


def test_parse_counts_both():
    assert Pollen._parse_counts({"tree": 7, "grass": 3}) == (7, 3)


def test_parse_counts_tree_only():
    assert Pollen._parse_counts({"tree": 5}) == (5, None)


def test_parse_counts_grass_only():
    assert Pollen._parse_counts({"grass": 2}) == (None, 2)


def test_parse_counts_invalid():
    assert Pollen._parse_counts({"tree": "x", "grass": None}) == (None, None)
    assert Pollen._parse_counts({"pollen": 7}) == (None, None)


class _App:
    def __init__(self):
        self.canvas_width = 64
        self.canvas_height = 32


def _pollen(monkeypatch, counts):
    monkeypatch.setattr(ModuleStore, "_restore", lambda self: False)
    module = Pollen(_App())
    module.store.set_item(Pollen.KEY, counts)
    return module


def test_half_layout_puts_grass_in_the_right_column(monkeypatch):
    """Grass belongs beside tree in the 64x16 slot, not 32 pixels below it."""
    module = _pollen(monkeypatch, {"tree": 7, "grass": 3})
    group = module._build_group("half")

    tree_icon, tree_label, grass_icon, grass_label = group

    assert (tree_icon.x, tree_icon.y) == (0, 0)
    assert (grass_icon.x, grass_icon.y) == (32, 0)
    assert grass_label.x > tree_label.x
    assert tree_label.y == grass_label.y == HALF_WIDE[1] // 2

    for item in group:
        assert 0 <= item.y < HALF_WIDE[1]


def test_eighth_layouts_put_the_count_at_the_top_of_the_slot(monkeypatch):
    """y = 0 would hang the text above the group, where it is clipped."""
    module = _pollen(monkeypatch, {"tree": 7, "grass": 3})

    for layout in ("tree", "grass"):
        _icon, label = module._build_group(layout)
        assert label.y + label.bounding_box[1] == 0
