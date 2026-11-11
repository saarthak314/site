"""Draw the social preview card: the home banner over the wordmark.

Writes static/images/social-card-cat.jpg at 1200x630, laid out like the top of the
home page: the cat-in-space dots from generate_cat.py, then the name and the
first line of the intro, in the site's own fonts and palette.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import generate_cat as cat  # noqa: E402

FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
OUTPUT = PROJECT_ROOT / "static" / "images" / "social-card-cat.jpg"

WIDTH, HEIGHT = 1200, 630
SCALE = 3  # drawn at 3x and scaled down, so the dots come out round

# the site's palette (static/index.css :root)
BG = "#0e1016"
INK = "#eef1f6"
INK_2 = "#b2b7c2"
INK_3 = "#7f8592"
INK_4 = "#525866"
ACCENT_2 = "#6f8fcf"

# the banner's tone classes, as the stylesheet colours them
TONES = {
  "t1": INK_4,
  "t2": INK_3,
  "t3": INK_2,
  "t4": INK,
  "b1": "#3f5a8c",
  "b2": ACCENT_2,
  "b3": "#9db8ef",
  "w1": "#7a5f4a",
  "w2": "#b08a66",
  "w3": "#e0bd92",
  "g": "#cfd27c",
}

TAGLINE = "systems engineer // inference, high perf computing, agentic workloads"


def _font(name: str, size: float) -> ImageFont.FreeTypeFont:
  return ImageFont.truetype(str(FONT_DIR / name), round(size * SCALE))


def draw_banner(draw: ImageDraw.ImageDraw, cols: int, rows: int, keep: int) -> float:
  """The banner across the card's full width, its top ``keep`` rows only;
  returns where it ends."""
  art, stars = cat.split_stars(cat.render(cols, rows))
  cell = WIDTH / cols * SCALE
  y0 = 0

  def dot(x: float, y: float, glyph: str, colour: str) -> None:
    cx = (x + cat.CENTRE_X - 0.25) * cell
    cy = y0 + (y + cat.CENTRE_Y[glyph]) * cell
    r = cat.RADIUS[glyph] * cell
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)

  for y, row in enumerate(art[:keep]):
    for x, (glyph, tone) in enumerate(row):
      if glyph != " ":
        dot(x, y, glyph, TONES[tone])
  for x, y, bright in stars:
    if y < keep:
      dot(x, y, "·", INK if bright else INK_3)
  return keep * WIDTH / cols


def draw_wordmark(draw: ImageDraw.ImageDraw, x: float, y: float, size: float) -> None:
  """sλrthak tomar: the serif with JetBrains Mono's λ, as in the header."""
  serif = _font("InstrumentSerif-Regular.ttf", size)
  mono = _font("JetBrainsMono-Regular.ttf", size * 0.82)
  x, y = x * SCALE, y * SCALE
  for text, font, dy in (
    ("s", serif, 0),
    ("λ", mono, size * 0.1 * SCALE),
    ("rthak tomar", serif, 0),
  ):
    draw.text((x, y + dy), text, font=font, fill=INK)
    x += font.getlength(text)


def render() -> Image.Image:
  image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), BG)
  draw = ImageDraw.Draw(image)
  cols = 180
  with Image.open(cat.SOURCE) as photo:
    width, height = photo.size
  left, top, right, bottom = cat.CROP
  rows = round(cols / ((width * (right - left)) / (height * (bottom - top))))
  # the banner's lowest rows are the suit's cuff, left off so the name fits
  banner_end = draw_banner(draw, cols, rows, keep=rows - 8)

  margin = 64
  plex = _font("IBMPlexMono-Regular.ttf", 22)
  name_top = banner_end + 8
  draw_wordmark(draw, margin, name_top, 58)
  url = "sarrthak.com"
  draw.text(
    ((WIDTH - margin) * SCALE - plex.getlength(url), (name_top + 36) * SCALE),
    url,
    font=plex,
    fill=INK_4,
  )
  draw.text((margin * SCALE, (name_top + 82) * SCALE), TAGLINE, font=plex, fill=INK_2)
  return image.resize((WIDTH, HEIGHT), Image.LANCZOS)


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--output", type=Path, default=OUTPUT)
  args = parser.parse_args()
  image = render()
  args.output.parent.mkdir(parents=True, exist_ok=True)
  image.save(args.output, "JPEG", quality=88, optimize=True, progressive=True)
  print(
    f"{args.output}: {image.size[0]}x{image.size[1]}, {args.output.stat().st_size} bytes"
  )


if __name__ == "__main__":
  main()
