"""Convert the home-page portrait into tinted block-character ASCII.

Reads assets/images/asuka.jpg and writes templates/partials/portrait.html. Hair
(orange hues) is mapped onto the lavender accent tones; everything else onto the
ink ramp by luminance, so the drawing sits inside the site's palette.
"""

from __future__ import annotations

import argparse
import colorsys
import html
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "assets" / "images" / "asuka.jpg"
OUTPUT = PROJECT_ROOT / "templates" / "partials" / "portrait.html"

INK = ("#5b5955", "#85827c", "#b3b0a8", "#f2f0ea")
LAVENDER = ("#8f7fc4", "#b4a3e6", "#d9cffa")
SHADES = " ░▒▓█"
QUADRANTS = {
  0b0000: " ",
  0b1000: "▘",
  0b0100: "▝",
  0b0010: "▖",
  0b0001: "▗",
  0b1100: "▀",
  0b0011: "▄",
  0b1010: "▌",
  0b0101: "▐",
  0b1001: "▚",
  0b0110: "▞",
  0b1110: "▛",
  0b1101: "▜",
  0b1011: "▙",
  0b0111: "▟",
  0b1111: "█",
}


def _classify(r: int, g: int, b: int) -> str:
  """hair (saturated orange/red), eye (saturated blue), wall (dark olive), or skin."""
  hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
  if (hue <= 0.13 or hue >= 0.95) and sat > 0.5 and light < 0.5:
    return "hair"
  if 0.55 <= hue <= 0.75 and sat > 0.4 and light < 0.5:
    return "eye"
  if 0.14 <= hue <= 0.45 and sat < 0.5 and light < 0.35:
    return "wall"
  return "skin"


def _lit(kind: str, lum: float, threshold: float) -> bool:
  if kind == "wall":
    return False
  if kind == "hair":
    return lum > 0.06
  if kind == "eye":
    return lum > 0.15
  return lum > threshold


def _tone(lum: float, kind: str) -> str:
  if kind == "hair":
    return LAVENDER[0] if lum < 0.22 else LAVENDER[1] if lum < 0.45 else LAVENDER[2]
  if kind == "eye":
    return LAVENDER[2]
  return (
    INK[0] if lum < 0.3 else INK[1] if lum < 0.55 else INK[2] if lum < 0.8 else INK[3]
  )


def _prepare(cols: int, rows: int, contrast: float, scale: int) -> Image.Image:
  image = Image.open(SOURCE).convert("RGB")
  width, height = image.size
  image = image.crop(
    (int(width * 0.09), int(height * 0.03), width, height - int(height * 0.03))
  )
  image = image.resize((width, width))
  image = ImageOps.autocontrast(image, cutoff=1)
  image = ImageEnhance.Contrast(image).enhance(contrast)
  return image.resize((cols * scale, rows * scale), Image.LANCZOS)


def render_shades(
  cols: int, rows: int, contrast: float = 1.25
) -> list[list[tuple[str, str]]]:
  image = _prepare(cols, rows, contrast, 1)
  gray = image.convert("L")
  cells: list[list[tuple[str, str]]] = []
  for y in range(rows):
    row = []
    for x in range(cols):
      lum = gray.getpixel((x, y)) / 255
      kind = _classify(*image.getpixel((x, y)))
      if not _lit(kind, lum, 0.12):
        row.append((" ", INK[0]))
        continue
      level = max(
        1,
        min(
          len(SHADES) - 1,
          int((lum if kind != "hair" else max(lum, 0.35)) * len(SHADES)),
        ),
      )
      row.append((SHADES[level], _tone(lum, kind)))
    cells.append(row)
  return cells


def render_quadrants(
  cols: int, rows: int, contrast: float = 1.35, threshold: float = 0.42
) -> list[list[tuple[str, str]]]:
  image = _prepare(cols, rows, contrast, 2)
  gray = image.convert("L")
  cells: list[list[tuple[str, str]]] = []
  for y in range(rows):
    row = []
    for x in range(cols):
      bits = 0
      lums = []
      kinds = []
      for index, (dx, dy) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
        px, py = x * 2 + dx, y * 2 + dy
        lum = gray.getpixel((px, py)) / 255
        kind = _classify(*image.getpixel((px, py)))
        if _lit(kind, lum, threshold):
          bits |= 1 << (3 - index)
          lums.append(lum)
          kinds.append(kind)
      if not lums:
        row.append((" ", INK[0]))
        continue
      lum = sum(lums) / len(lums)
      kind = max(set(kinds), key=kinds.count)
      row.append((QUADRANTS[bits], _tone(lum, kind)))
    cells.append(row)
  return cells


def to_html(cells: list[list[tuple[str, str]]], cols: int, label: str) -> str:
  palette = {color: f"p{index}" for index, color in enumerate((*INK, *LAVENDER))}
  lines = []
  for row in cells:
    parts = []
    current_class = None
    buffer = ""
    for glyph, color in row:
      cls = palette[color] if glyph != " " else current_class
      if cls != current_class and buffer:
        parts.append(
          f'<span class="{current_class}">{html.escape(buffer)}</span>'
          if current_class
          else html.escape(buffer)
        )
        buffer = ""
      current_class = cls
      buffer += glyph
    if buffer:
      parts.append(
        f'<span class="{current_class}">{html.escape(buffer)}</span>'
        if current_class
        else html.escape(buffer)
      )
    lines.append("".join(parts).rstrip())
  body = "\n".join(lines)
  return (
    f'<pre class="portrait" role="img" aria-label="{html.escape(label)}" '
    f'style="--cols: {cols}">{body}</pre>\n'
  )


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--mode", choices=("shades", "quadrants"), default="quadrants")
  parser.add_argument("--cols", type=int, default=120)
  parser.add_argument("--output", type=Path, default=OUTPUT)
  args = parser.parse_args()
  rows = round(args.cols * 0.5)
  cells = (
    render_shades(args.cols, rows)
    if args.mode == "shades"
    else render_quadrants(args.cols, rows)
  )
  markup = to_html(
    cells,
    args.cols,
    "ascii portrait of asuka langley soryu, chin on her hand, unimpressed",
  )
  args.output.write_text(markup)
  spans = markup.count("<span")
  print(
    f"{args.output.relative_to(PROJECT_ROOT) if args.output.is_relative_to(PROJECT_ROOT) else args.output}: {args.cols}x{rows}, {spans} spans, {len(markup)} bytes"
  )


if __name__ == "__main__":
  main()
