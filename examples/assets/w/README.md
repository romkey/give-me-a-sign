# Weather BMPs (32×16)

Weather icon BMPs for [`weather.py`](../../give_me_a_sign/weather.py) ship inside the library at
`give_me_a_sign/assets/w/` (on the device: `/lib/give_me_a_sign/assets/w/`). Regenerate them with
`python3 extras/weather_bmps/generate_from_openweather.py` from the repo root (writes into that folder).

## Contents

- **`01d.bmp` … `50n.bmp`** — 18 canonical weather stems (day `d` / night `n`) generated from
  [Meteocons](https://github.com/basmilius/meteocons) SVG artwork by Bas Milius.
- **`200.bmp` … `804.bmp`** — Same pixels as the mapped icon, one file per [condition `id`](https://openweathermap.org/weather-conditions) so payloads can use raw `weather[0].id` as the filename stem.

Regenerate (downloads Meteocons SVGs and rasterizes to full-bleed `32×16` RGB BMP):

```bash
python3 extras/weather_bmps/generate_from_openweather.py --id-copies
```

Use a venv with [Pillow](https://pypi.org/project/pillow/) and [CairoSVG](https://pypi.org/project/CairoSVG/) installed.

Create a quick visual review sheet of the 18 canonical icons:

```bash
python3 extras/weather_bmps/preview_weather_icons.py
```

This writes `examples/assets/w/weather_icons_preview.png`.

## Integration

Prefer sending in `weather.current`:

- **`icon`** — e.g. `"10n"` (needed for clear sky at night: `01n` vs `01d` for id `800`).
- **`condition_id`** or numeric **`conditions`** — mapped via `OWM_ID_TO_ICON` in `weather.py` if `icon` is omitted.

Legacy names like `sunny` / `rain` still map to icons.

## Attribution

Artwork is adapted from [Meteocons](https://github.com/basmilius/meteocons) by Bas Milius and is used
under the [MIT License](https://raw.githubusercontent.com/basmilius/meteocons/main/LICENSE).
