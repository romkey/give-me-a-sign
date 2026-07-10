# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Unit tests for pollen count parsing."""

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
