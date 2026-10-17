"""A deterministic ASCII scene for the about page footer: utility poles and
their wires drawn over stop-error panels.

Two layers, like the city: a far one with a street lamp, a distant pole and
lighter wires, and a near one with two poles, insulators, transformer cans,
wires fanning off the frame and birds. The panels' copy comes from
``content/_panic.txt`` so it stays editable without touching code. Everything
is drawn with the same ``Canvas`` as the city and the same glyph allow-list.
"""

from __future__ import annotations

import random
import re
from functools import lru_cache
from html import escape
from pathlib import Path
from types import SimpleNamespace

from markupsafe import Markup

from sitegen.city import Canvas

ALLOWED_GLYPHS = frozenset("▪│─┼┴╭╮▐█▌▝▀▘▄╲╱")
COLS = 200
ROWS = 32
PANEL_SEPARATOR = re.compile(r"(?m)^---[ \t]*$")
_STOP_CODE = re.compile(r"\b[A-Z][A-Z0-9_]{6,}\b")

Wire = tuple[int, int, int, int, float]  # row0, col0, row1, col1, sag in rows


def load_panels(content_dir: Path) -> tuple[str, ...]:
  """Read the stop-error copy: blocks of ``content/_panic.txt`` split on ``---``."""
  path = content_dir / "_panic.txt"
  if not path.is_file():
    return ()
  blocks = PANEL_SEPARATOR.split(path.read_text(encoding="utf-8"))
  return tuple(block.strip("\n") for block in blocks if block.strip())


def _wire(canvas: Canvas, wire: Wire, cls: str) -> None:
  """A sagging wire between two attachment points, drawn with line glyphs."""
  r0, c0, r1, c1, sag = wire
  if c1 < c0:
    r0, c0, r1, c1 = r1, c1, r0, c0
  span = max(1, c1 - c0)
  previous = r0
  for col in range(c0, c1 + 1):
    t = (col - c0) / span
    y = r0 + (r1 - r0) * t + sag * 4 * t * (1 - t)
    row = round(y)
    if row > previous:
      glyph = "╲"
    elif row < previous:
      glyph = "╱"
    else:
      glyph = "─" if abs(y - row) < 0.25 else ("_" if y > row else "─")
    if canvas.glyph(row, col) == " ":
      canvas.put(row, col, glyph, cls)
    previous = row


def _pole(
  canvas: Canvas, col: int, top: int, ground: int, *, arms: int, can: bool = True
) -> list[tuple[int, int]]:
  """A pole with crossarms and insulators; returns the insulator cells."""
  points: list[tuple[int, int]] = []
  for row in range(top, ground):
    canvas.put(row, col, "│", "pole")
  for index in range(arms):
    row = top + 1 + index * 3
    for offset, glyph in enumerate("─┼─────┼─────┼─"):
      canvas.put(row, col - 7 + offset, glyph, "pole")
    for offset in (-6, 0, 6):
      canvas.put(row - 1, col + offset, "▪", "ins")
      points.append((row - 1, col + offset))
  if can:
    for row, text in ((top + 4, "▐██▌"), (top + 5, "▐██▌"), (top + 6, "▝▀▀▘")):
      for offset, glyph in enumerate(text):
        canvas.put(row, col + 1 + offset, glyph, "can")
  canvas.put(ground, col, "┴", "pole")
  return points


def _fan(
  canvas: Canvas,
  top: int,
  col: int,
  direction: int,
  ground: int,
  slopes: tuple[float, ...] = (0.33,),
) -> None:
  """Straight lines from a pole top toward the frame edge and the ground."""
  for slope in slopes:
    c = col
    previous = top
    while 0 <= c + direction < canvas.cols:
      c += direction
      row = round(top + abs(c - col) * slope)
      if row >= ground - 1:
        break
      glyph = ("╲" if direction > 0 else "╱") if row > previous else "─"
      if canvas.glyph(row, c) == " ":
        canvas.put(row, c, glyph, "wire wire--fan")
      previous = row


def _lamp(canvas: Canvas, col: int, top: int, ground: int) -> None:
  for row in range(top + 1, ground):
    canvas.put(row, col, "│", "pole")
  for offset, glyph in enumerate("╭────────╮"):
    canvas.put(top, col + offset, glyph, "pole")
  canvas.put(top + 1, col + 9, "▄", "lamp")
  canvas.put(ground, col, "┴", "pole")


def _far(rng: random.Random) -> Canvas:
  """The distance: a street lamp, one long faint wire, a few stars."""
  canvas = Canvas(COLS, ROWS)
  ground = ROWS - 1
  _lamp(canvas, 40, 9, ground)
  _wire(canvas, (8, 0, 11, COLS - 1, 1.6), "wire")
  for _ in range(10):
    row, col = rng.randint(0, 6), rng.randrange(COLS)
    if canvas.glyph(row, col) == " ":
      canvas.put(row, col, rng.choice(".'"), "star")
  return canvas


def _near(rng: random.Random) -> tuple[Canvas, list[Wire]]:
  canvas = Canvas(COLS, ROWS)
  ground = ROWS - 1
  for col in range(COLS):
    canvas.put(ground, col, "─", "ground")
  # Seven wires in all: three between the poles, one off each edge, one drop
  # line from the left pole, and the faint one in the far layer.
  left = _pole(canvas, 62, 7, ground, arms=1, can=False)
  right = _pole(canvas, 150, 6, ground, arms=1)
  spans: list[Wire] = []
  for index, ((lr, lc), (rr, rc)) in enumerate(zip(left, right, strict=False)):
    wire: Wire = (lr, lc, rr, rc, 1.2 + index * 0.4)
    _wire(canvas, wire, "wire")
    spans.append(wire)
  _wire(canvas, (left[0][0], left[0][1], left[0][0] + 1, 0, 0.9), "wire")
  _wire(canvas, (right[2][0], right[2][1], right[2][0] + 1, COLS - 1, 0.9), "wire")
  _fan(canvas, 7, 62, -1, ground)
  for col in (88, 91, 121):
    row = next((r for r in range(ROWS) if canvas.glyph(r, col) in "─_"), None)
    if row and canvas.glyph(row - 1, col) == " ":
      canvas.put(row - 1, col, "v", "bird")
  _hum(rng, canvas, count=10)
  return canvas, spans


def _hum(rng: random.Random, canvas: Canvas, *, count: int) -> None:
  """Mark short stretches of wire that flicker on their own cycle."""
  placed, attempts = 0, 0
  while placed < count and attempts < 400:
    attempts += 1
    row, col = rng.randint(5, 14), rng.randint(0, canvas.cols - 12)
    length = rng.randint(5, 11)
    if any(canvas.cls(row, c) != "wire" for c in range(col, col + length)):
      continue
    for c in range(col, col + length):
      canvas.put(row, c, canvas.glyph(row, c), "wire wire--hum", f"--i: {placed}")
    placed += 1


def _glitch_patches(rng: random.Random, canvas: Canvas, count: int) -> int:
  """Lag patches over the wire rows, so the shaking lands on the lines."""
  placed, attempts = 0, 0
  taken: list[tuple[int, int, int, int]] = []
  while placed < count and attempts < 3000:
    attempts += 1
    height, width = rng.randint(3, 6), rng.randint(18, 34)
    row0 = rng.randint(5, 15 - height)
    col0 = rng.randint(0, canvas.cols - width)
    row1, col1 = row0 + height, col0 + width
    if any(
      not (row1 <= r0 or r1 <= row0 or col1 <= c0 or c1 <= col0)
      for r0, r1, c0, c1 in taken
    ):
      continue
    cells = [canvas.cells[r][c] for r in range(row0, row1) for c in range(col0, col1)]
    if sum(1 for cell in cells if cell[0] != " ") < len(cells) // 12:
      continue
    style = f"--i: {placed}"
    for r in range(row0, row1):
      for c in range(col0, col1):
        glyph, cls, cell_style = canvas.cells[r][c]
        if cls is None:
          canvas.put(r, c, glyph, "glitch", style)
        else:
          canvas.put(
            r,
            c,
            glyph,
            f"glitch {cls}",
            f"{style}; {cell_style}" if cell_style else style,
          )
    taken.append((row0, row1, col0, col1))
    placed += 1
  return placed


def _panel_markup(text: str) -> Markup:
  """Escape a panel and brighten its stop codes and ``*** STOP`` lines."""
  escaped = escape(text, quote=False)
  escaped = _STOP_CODE.sub(lambda match: f"<b>{match.group(0)}</b>", escaped)
  escaped = escaped.replace("*** STOP", "<b>*** STOP</b>")
  return Markup(escaped)


@lru_cache(maxsize=4)
def panic_layers(panels: tuple[str, ...], seed: int = 413) -> SimpleNamespace:
  """Return the scene: far and near layers, the wires packets can ride, panels."""
  rng = random.Random(seed)
  far = _far(rng)
  near, spans = _near(rng)
  patches = _glitch_patches(rng, near, 6)
  return SimpleNamespace(
    cols=COLS,
    rows=ROWS,
    far=Markup(far.render()),
    near=Markup(near.render()),
    wires=";".join(f"{r0},{c0},{r1},{c1},{sag:.1f}" for r0, c0, r1, c1, sag in spans),
    panels=tuple(_panel_markup(panel) for panel in panels),
    patches=patches,
  )


__all__ = ["ALLOWED_GLYPHS", "COLS", "ROWS", "load_panels", "panic_layers"]
