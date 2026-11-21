"""Draw the social preview cards: the home banner over the wordmark.

Writes static/images/social-card-cat.jpg at 1200x630, laid out like the top of the
home page: the cat-in-space dots from generate_cat.py, then the name and the
first line of the intro, in the site's own fonts and palette.

With --posts it also draws a card for every post, at
static/images/cards/<slug>.jpg: the banner as a band across the top, then the
post's title, then the name and date. The build gives a post its card whenever
that file exists, so run this again after adding a post or changing a title or
date (a test fails until you do).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import generate_cat as cat  # noqa: E402

FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
OUTPUT = PROJECT_ROOT / "static" / "images" / "social-card-cat.jpg"
CARDS = PROJECT_ROOT / "static" / "images" / "cards"
# what each post's card shows, kept out of static/ so it isn't published
CARD_NOTES = PROJECT_ROOT / "assets" / "cards.json"
BLOGS = PROJECT_ROOT / "content" / "blogs"

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


class TitleFace:
  """Instrument Serif at one size, with JetBrains Mono's λ (the serif has
  none), set as the wordmark sets it."""

  def __init__(self, size: float) -> None:
    self.size = size
    self.serif = _font("InstrumentSerif-Regular.ttf", size)
    self.mono = _font("JetBrainsMono-Regular.ttf", size * 0.82)

  def length(self, text: str) -> float:
    parts = text.split("\u03bb")
    lambdas = (len(parts) - 1) * self.mono.getlength("\u03bb")
    return sum(self.serif.getlength(part) for part in parts) + lambdas

  def draw(self, draw: ImageDraw.ImageDraw, x: float, y: float, text: str) -> None:
    for number, part in enumerate(text.split("\u03bb")):
      if number:
        draw.text((x, y + self.size * 0.1 * SCALE), "\u03bb", font=self.mono, fill=INK)
        x += self.mono.getlength("\u03bb")
      draw.text((x, y), part, font=self.serif, fill=INK)
      x += self.serif.getlength(part)


def _wrap(text: str, face: TitleFace, width: float) -> list[str]:
  """Words onto lines no wider than ``width``; a word wider than a whole line
  is broken where it runs out of room."""
  lines: list[str] = []
  for word in text.split():
    while face.length(word) > width:
      cut = len(word) - 1
      while cut > 1 and face.length(word[:cut]) > width:
        cut -= 1
      lines.append(word[:cut])
      word = word[cut:]
    if lines and face.length(f"{lines[-1]} {word}") <= width:
      lines[-1] = f"{lines[-1]} {word}"
    else:
      lines.append(word)
  return lines


def draw_byline(draw: ImageDraw.ImageDraw, x: float, y: float, text: str) -> None:
  """A line in IBM Plex Mono that has no λ: that letter comes from JetBrains
  Mono, as it does in the header."""
  plex = _font("IBMPlexMono-Regular.ttf", 22)
  mono = _font("JetBrainsMono-Regular.ttf", 22)
  x, y = x * SCALE, y * SCALE
  for number, part in enumerate(text.split("\u03bb")):
    if number:
      draw.text((x, y), "\u03bb", font=mono, fill=INK_3)
      x += mono.getlength("\u03bb")
    draw.text((x, y), part, font=plex, fill=INK_3)
    x += plex.getlength(part)


def render_post(title: str, byline: str) -> Image.Image:
  """A post's card: the banner as a band across the top (down to the cat's
  chin), the title under it as large as the room allows in at most two lines,
  and a line of who and when."""
  image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), BG)
  draw = ImageDraw.Draw(image)
  cols = 180
  with Image.open(cat.SOURCE) as photo:
    width, height = photo.size
  left, top, right, bottom = cat.CROP
  rows = round(cols / ((width * (right - left)) / (height * (bottom - top))))
  banner_end = draw_banner(draw, cols, rows, keep=rows - 19)

  margin = 64
  room = (WIDTH - 2 * margin) * SCALE
  foot = HEIGHT - 52  # the byline's baseline area
  space = foot - 34 - (banner_end + 26)  # between the banner and the byline
  for size in range(76, 39, -2):
    face = TitleFace(size)
    lines = _wrap(title, face, room)
    leading = size * 1.08
    if len(lines) <= 2 and leading * len(lines) <= space:
      break
  else:
    # too long for two lines even at the smallest size: the second line ends
    # in an ellipsis rather than running into the byline
    lines = lines[:2]
    while len(lines) == 2 and face.length(lines[1] + "\u2026") > room:
      lines[1] = lines[1][:-1].rstrip()
    lines[-1] += "\u2026"
  text_top = banner_end + 26 + (space - leading * len(lines)) / 2 - size * 0.12
  for number, line in enumerate(lines):
    face.draw(draw, margin * SCALE, (text_top + number * leading) * SCALE, line)
  draw_byline(draw, margin, foot - 22, byline)
  plex = _font("IBMPlexMono-Regular.ttf", 22)
  url = "sarrthak.com"
  draw.text(
    ((WIDTH - margin) * SCALE - plex.getlength(url), (foot - 22) * SCALE),
    url,
    font=plex,
    fill=INK_4,
  )
  return image.resize((WIDTH, HEIGHT), Image.LANCZOS)


def _save(image: Image.Image, output: Path) -> None:
  output.parent.mkdir(parents=True, exist_ok=True)
  image.save(output, "JPEG", quality=88, optimize=True, progressive=True)
  print(f"{output}: {image.size[0]}x{image.size[1]}, {output.stat().st_size} bytes")


def card_text(source: Path) -> tuple[str, str, str]:
  """A post's slug, and the title and date its card shows (no reading time,
  so editing the words never leaves a card out of date)."""
  from sitegen.frontmatter import parse_document

  metadata = parse_document(source).metadata
  slug = metadata.slug or source.parent.name
  return slug, metadata.title, metadata.date.strftime("%d %b %Y").lower()


def draw_posts() -> None:
  """A card for every post, named by its slug as the build looks for it, and
  a note of what each shows, which the tests compare with the posts."""
  shown: dict[str, dict[str, str]] = {}
  for source in sorted(BLOGS.glob("*/index.md")):
    slug, title, when = card_text(source)
    _save(render_post(title, f"s\u03bbrthak tomar // {when}"), CARDS / f"{slug}.jpg")
    shown[slug] = {"title": title, "date": when}
  CARD_NOTES.write_text(json.dumps(shown, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--output", type=Path, default=OUTPUT)
  parser.add_argument(
    "--posts", action="store_true", help="also draw a card for every post"
  )
  args = parser.parse_args()
  _save(render(), args.output)
  if args.posts:
    draw_posts()


if __name__ == "__main__":
  main()
