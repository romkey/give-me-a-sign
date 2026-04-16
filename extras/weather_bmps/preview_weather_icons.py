#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2023-2026 John Romkey
# SPDX-License-Identifier: MIT
"""
Create a quick contact sheet preview for the 18 canonical weather BMP icons.

Run from repo root:
  python3 extras/weather_bmps/preview_weather_icons.py

Output:
  examples/assets/w/weather_icons_preview.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICONS = (
    "01d",
    "01n",
    "02d",
    "02n",
    "03d",
    "03n",
    "04d",
    "04n",
    "09d",
    "09n",
    "10d",
    "10n",
    "11d",
    "11n",
    "13d",
    "13n",
    "50d",
    "50n",
)

CELL_W = 32
CELL_H = 16
LABEL_H = 10
COLS = 6
PADDING = 4
BG = (0, 0, 0)
FG = (200, 200, 200)


def main() -> None:  # pylint: disable=too-many-locals
    """Generate a PNG contact sheet for the canonical weather icon set."""
    root = Path(__file__).resolve().parents[2]
    assets_dir = root / "give_me_a_sign" / "assets" / "w"
    out_path = root / "examples" / "assets" / "w" / "weather_icons_preview.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = (len(ICONS) + COLS - 1) // COLS
    canvas_w = COLS * (CELL_W + PADDING) + PADDING
    canvas_h = rows * (CELL_H + LABEL_H + PADDING) + PADDING
    sheet = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for idx, stem in enumerate(ICONS):
        col = idx % COLS
        row = idx // COLS
        x = PADDING + col * (CELL_W + PADDING)
        y = PADDING + row * (CELL_H + LABEL_H + PADDING)

        bmp_path = assets_dir / f"{stem}.bmp"
        if not bmp_path.is_file():
            draw.text((x, y), "missing", fill=(255, 80, 80), font=font)
            draw.text((x, y + LABEL_H), stem, fill=FG, font=font)
            continue

        icon = Image.open(bmp_path).convert("RGB")
        if icon.size != (CELL_W, CELL_H):
            icon = icon.resize((CELL_W, CELL_H), Image.Resampling.NEAREST)
        sheet.paste(icon, (x, y))
        draw.text((x, y + CELL_H), stem, fill=FG, font=font)

    sheet.save(out_path, "PNG")
    print(f"wrote {out_path.relative_to(root)}")


if __name__ == "__main__":
    main()
