# SPDX-FileCopyrightText: 2026 John Romkey
#
# SPDX-License-Identifier: MIT

"""Sphinx configuration for the Give Me A Sign documentation."""

import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------

project = "Give Me A Sign"
author = "John Romkey"
copyright = f"2023-{datetime.date.today().year} John Romkey"  # pylint: disable=redefined-builtin

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]

# CircuitPython-only modules are not installable on the machines that build
# these docs (Read the Docs, CI), so autodoc imports them as stubs instead.
autodoc_mock_imports = [
    "adafruit_bitmap_font",
    "adafruit_debouncer",
    "adafruit_display_text",
    "adafruit_ds3231",
    "adafruit_imageload",
    "adafruit_logging",
    "adafruit_minimqtt",
    "adafruit_ntp",
    "adafruit_pcf8523",
    "board",
    "digitalio",
    "displayio",
    "framebufferio",
    "microcontroller",
    "neopixel",
    "pwmio",
    "rgbmatrix",
    "rtc",
    "socketpool",
    "storage",
    "supervisor",
    "terminalio",
    "wifi",
]

autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "circuitpython": ("https://docs.circuitpython.org/en/latest/", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "TEST_PLAN.md"]

source_suffix = ".rst"
master_doc = "index"

todo_include_todos = False

# -- Options for HTML output -------------------------------------------------

try:
    import sphinx_rtd_theme  # noqa: F401  pylint: disable=unused-import

    html_theme = "sphinx_rtd_theme"
except ImportError:
    html_theme = "default"

html_static_path = []
htmlhelp_basename = "GiveMeASignLibrarydoc"
