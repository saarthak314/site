"""Draw the social preview card: the wordmark beside the ascii portrait.

Writes static/images/social-card.jpg at 1200x630 using the same portrait
conversion as the home page and the site's own fonts and palette.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import generate_portrait as portrait  # noqa: E402

FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
OUTPUT = PROJECT_ROOT / "static" / "images" / "social-card.jpg"

BG = "#16151a"
INK = "#f2f0ea"
INK_2 = "#b3b0a8"
INK_3 = "#85827c"
INK_4 = "#5b5955"
WIDTH, HEIGHT = 1200, 630


def draw_wordmark(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> int:
  serif = ImageFont.truetype(str(FONT_DIR / "InstrumentSerif-Regular.ttf"), size)
  mono = ImageFont.truetype(
    str(FONT_DIR / "JetBrainsMono-Regular.ttf"), int(size * 0.82)
  )
  draw.text((x, y), "s", font=serif, fill=INK)
  x += serif.getlength("s")
  draw.text((x, y + size * 0.1), "λ", font=mono, fill=INK)
  x += mono.getlength("λ")
  draw.text((x, y), "rthak", font=serif, fill=INK)
  return int(x + serif.getlength("rthak"))


def draw_portrait(image: Image.Image, x0: int, y0: int, cols: int, cell: int) -> None:
  rows = round(cols * 0.5)
  cells = portrait.render_quadrants(cols, rows)
  font = ImageFont.truetype(
    str(FONT_DIR / "JetBrainsMono-Regular.ttf"), int(cell * 1.67)
  )
  draw = ImageDraw.Draw(image)
  for row_index, row in enumerate(cells):
    for col_index, (glyph, color) in enumerate(row):
      if glyph == " ":
        continue
      draw.text(
        (x0 + col_index * cell, y0 + row_index * cell * 1.67),
        glyph,
        font=font,
        fill=color,
      )


def main() -> None:
  image = Image.new("RGB", (WIDTH, HEIGHT), BG)
  draw = ImageDraw.Draw(image)
  plex = ImageFont.truetype(str(FONT_DIR / "IBMPlexMono-Regular.ttf"), 26)
  small = ImageFont.truetype(str(FONT_DIR / "IBMPlexMono-Regular.ttf"), 22)

  draw_wordmark(draw, 88, 150, 150)
  draw.text((92, 330), "sarthak tomar", font=plex, fill=INK_3)
  draw.text((92, 372), "systems, models, machines.", font=plex, fill=INK_2)
  draw.text((92, 540), "sarrthak.com", font=small, fill=INK_4)

  cols = 72
  cell = 7
  draw_portrait(image, WIDTH - 88 - cols * cell, 93, cols, cell)

  OUTPUT.parent.mkdir(parents=True, exist_ok=True)
  image.save(OUTPUT, "JPEG", quality=88, optimize=True, progressive=True)
  print(
    f"{OUTPUT.relative_to(PROJECT_ROOT)}: {image.size[0]}x{image.size[1]}, {OUTPUT.stat().st_size} bytes"
  )


if __name__ == "__main__":
  main()
