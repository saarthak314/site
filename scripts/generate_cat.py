"""Convert the home banner photo into dot-matrix ASCII.

Reads assets/images/cat-in-space.jpg and writes templates/partials/cat.html.
Each cell is a dot sized by brightness (· •) on a square grid; the earth's
blues keep a blue tint, everything else sits on the site's ink ramp. Stars
that a cell average would wash out are kept by also looking at each cell's
brightest pixel. Stars alone in open sky go to a layer of their own laid over
the art, where CSS makes them twinkle; the rest stay put.

The art is a picture, so it is written as an inline SVG: every dot sits where
JetBrains Mono would put its "·" or "•" on the grid, drawn as a round cap of
the glyph's own size, one path per tone and size. The twinkling stars are
small HTML dots over it, so their animation stays on the compositor.
"""

from __future__ import annotations

import argparse
import colorsys
import html
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "assets" / "images" / "cat-in-space.jpg"
OUTPUT = PROJECT_ROOT / "templates" / "partials" / "cat.html"
LABEL = "ascii art of a cat in a spacesuit waving, the earth behind it"

# (left, top, right, bottom) as fractions of the photo: drop the empty sky
# above the helmet and the suit's cuff below the paw.
CROP = (0.0, 0.2, 1.0, 0.84)

# tone classes: t* the ink ramp, b* the earth, w* the cat's fur, g its eyes

# Where each glyph's ink sits in its cell, in cells (a cell is the 0.4em the
# art advances and steps down by). JetBrains Mono's ascent (1.02em) and descent
# (0.3em) put the baseline 0.56em into a 0.4em line; "·" is centred 0.341em
# above it with a 0.082em radius, "•" 0.365em above with 0.12em; both are
# centred 0.3em into their advance.
CENTRE_X = 0.75
CENTRE_Y = {"·": 0.5475, "•": 0.4875}
RADIUS = {"·": 0.205, "•": 0.3}


def _prepare(cols: int, rows: int) -> tuple[Image.Image, Image.Image]:
  image = Image.open(SOURCE).convert("RGB")
  width, height = image.size
  left, top, right, bottom = CROP
  image = image.crop(
    (int(width * left), int(height * top), int(width * right), int(height * bottom))
  )
  image = ImageOps.autocontrast(image, cutoff=0.5)
  image = image.filter(ImageFilter.UnsharpMask(radius=3, percent=120, threshold=2))
  image = ImageEnhance.Color(image).enhance(1.3)
  mean = image.resize((cols, rows), Image.BOX)
  # each cell's brightest pixel, so single-pixel stars survive the average
  cell = max(3, round(image.width / cols) | 1)
  peak = (
    image.convert("L")
    .filter(ImageFilter.MaxFilter(cell))
    .resize((cols, rows), Image.NEAREST)
  )
  return mean, peak


def _kind(r: int, g: int, b: int) -> str:
  hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
  if 0.5 <= hue <= 0.72 and sat > 0.3 and light > 0.1:
    return "blue"
  if hue < 0.11 and sat > 0.3 and light > 0.12:
    return "fur"
  if 0.11 <= hue <= 0.3 and sat > 0.35 and light > 0.12:
    return "eye"
  return "ink"


def _dot(lum: float) -> str:
  return "·" if lum < 0.4 else "•"


def _cell(rgb: tuple[int, int, int], peak: float) -> tuple[str, str]:
  r, g, b = rgb
  lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
  kind = _kind(r, g, b)
  if kind == "fur":
    # fur is darker than the suit around it; lift it so the face reads
    lum = min(1.0, lum * 1.5 + 0.08)
  # the sky's navy wash is blue too, but darker than any ocean
  if (kind == "ink" and lum < 0.15) or (kind == "blue" and lum < 0.17):
    # dark sky: a star only where one pixel is bright
    if peak > 0.4:
      return "·", "s2" if peak > 0.75 else "s1"
    return " ", ""
  if kind == "blue":
    return _dot(lum), "b1" if lum < 0.25 else "b2" if lum < 0.45 else "b3"
  if kind == "fur":
    return _dot(lum), "w1" if lum < 0.4 else "w2" if lum < 0.6 else "w3"
  if kind == "eye":
    return "•", "g"
  if lum < 0.25:
    return "·", "t1"
  if lum < 0.4:
    return "·", "t2"
  if lum < 0.55:
    return "•", "t2"
  if lum < 0.75:
    return "•", "t3"
  return "•", "t4"


def _smooth(row: list[tuple[str, str]]) -> list[tuple[str, str]]:
  """Give a grey dot its neighbours' grey when both agree and it alone differs.

  Each lone flip costs two spans in the markup; on the suit they read as noise.
  Colours (earth, fur, eyes) are left exactly as drawn.
  """
  out = list(row)
  for x in range(1, len(row) - 1):
    (before, left), (glyph, tone), (after, right) = row[x - 1], row[x], row[x + 1]
    if " " in (before, glyph, after) or left != right or tone == left:
      continue
    if tone.startswith("t") and left.startswith("t"):
      out[x] = (glyph, left)
  return out


def render(cols: int, rows: int) -> list[list[tuple[str, str]]]:
  mean, peak = _prepare(cols, rows)
  return [
    _smooth(
      [_cell(mean.getpixel((x, y)), peak.getpixel((x, y)) / 255) for x in range(cols)]
    )
    for y in range(rows)
  ]


def split_stars(
  cells: list[list[tuple[str, str]]],
) -> tuple[list[list[tuple[str, str]]], list[tuple[int, int, bool]]]:
  """Take the stars alone in open sky out of the art, to twinkle on their own.

  A star with anything but other stars near it is a glint on the suit or
  visor, not sky; it stays in the art as a still grey dot.
  """
  rows, cols = len(cells), len(cells[0])
  art = [list(row) for row in cells]
  stars = []
  for y in range(rows):
    for x in range(cols):
      glyph, tone = cells[y][x]
      if not tone.startswith("s"):
        continue
      near = sum(
        1
        for ny in range(max(0, y - 2), min(rows, y + 3))
        for nx in range(max(0, x - 3), min(cols, x + 4))
        if (nx, ny) != (x, y)
        and cells[ny][nx][0] != " "
        and not cells[ny][nx][1].startswith("s")
      )
      if near == 0:
        stars.append((x, y, tone == "s2"))
        art[y][x] = (" ", "")
      else:
        art[y][x] = (glyph, "t2" if tone == "s2" else "t1")
  return art, stars


def stars_html(stars: list[tuple[int, int, bool]], cols: int, rows: int) -> str:
  """The twinkling stars, on the art's grid: one small dot each, with one of
  six rhythms picked from its place so neighbours never pulse together."""
  dots = []
  for x, y, bright in sorted(stars, key=lambda star: (star[1], star[0])):
    rhythm = (x * 7 + y * 13) % 6 + 1
    classes = f"s{rhythm} hi" if bright else f"s{rhythm}"
    dots.append(f'<i class="{classes}" style="--x: {x}; --y: {y}"></i>')
  return (
    f'<span class="cat-stars" aria-hidden="true" '
    f'style="--cols: {cols}; --rows: {rows}">{"".join(dots)}</span>\n'
  )


def _path(dots: list[tuple[int, int]], glyph: str) -> str:
  """Path data for dots of one glyph: a zero-length segment at each centre
  (its round cap is the dot), each a whole number of cells from the last."""
  parts = []
  px = py = None
  for x, y in dots:
    if px is None:
      parts.append(f"M{x + CENTRE_X:g} {y + CENTRE_Y[glyph]:g}h0")
    else:
      parts.append(f"m{x - px} {y - py}h0")
    px, py = x, y
  return "".join(parts)


def to_svg(cells: list[list[tuple[str, str]]], cols: int, rows: int) -> str:
  """A labelled inline SVG: one path for each tone and glyph size."""
  groups: dict[tuple[str, str], list[tuple[int, int]]] = {}
  for y, row in enumerate(cells):
    for x, (glyph, tone) in enumerate(row):
      if glyph != " ":
        groups.setdefault((tone, glyph), []).append((x, y))
  paths = []
  for (tone, glyph), dots in sorted(groups.items()):
    classes = tone if glyph == "·" else f"{tone} l"
    paths.append(f'<path class="{classes}" d="{_path(dots, glyph)}"/>')
  return (
    f'<svg class="cat" viewBox="0 0 {cols} {rows}" role="img" '
    f'aria-label="{html.escape(LABEL)}" focusable="false">{"".join(paths)}</svg>\n'
  )


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--cols", type=int, default=180)
  parser.add_argument("--output", type=Path, default=OUTPUT)
  args = parser.parse_args()
  with Image.open(SOURCE) as image:
    width, height = image.size
  left, top, right, bottom = CROP
  aspect = (width * (right - left)) / (height * (bottom - top))
  rows = round(args.cols / aspect)
  art, stars = split_stars(render(args.cols, rows))
  markup = to_svg(art, args.cols, rows) + stars_html(stars, args.cols, rows)
  args.output.write_text(markup)
  output = (
    args.output.relative_to(PROJECT_ROOT)
    if args.output.is_relative_to(PROJECT_ROOT)
    else args.output
  )
  print(
    f"{output}: {args.cols}x{rows}, {markup.count('<path')} paths, "
    f"{markup.count('h0')} dots, {len(markup.encode())} bytes"
  )


if __name__ == "__main__":
  main()
