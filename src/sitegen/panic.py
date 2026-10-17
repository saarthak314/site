"""A deterministic ASCII kernel-panic scene for the about page footer.

Retro machines sit on a ground line under three stop-error panels: a crt whose
screen scrolls a hex stream, a laptop whose screen shows the portrait, a stack
of floppies, and a disc in a tray. The panels' copy comes from
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

ALLOWED_GLYPHS = frozenset("▪◶│─┌┐└┘├┤┬┴╭╮╯╰╞╡═▐▌▝▀▘█░▒")
COLS = 200
ROWS = 32
PANEL_SEPARATOR = re.compile(r"(?m)^---[ \t]*$")
_STOP_CODE = re.compile(r"\b[A-Z][A-Z0-9_]{6,}\b")

CRT = """
 ┌────────────────────┐
 │ ╭────────────────╮ │
 │ │                │ │
 │ │                │ │
 │ │                │ │
 │ │                │ │
 │ │                │ │
 │ ╰────────────────╯ │
 │  ▪ ▪       ▪▪▪▪▪▪  │
 └──────┬──────┬──────┘
        └──────┘
    ────┴──────┴────
"""
CRT_SCREEN = (2, 4, 16, 5)  # sprite row, sprite col, width, height of the inner screen

LAPTOP = """
 ┌──────────────────────────────────────┐
 │ ┌──────────────────────────────────┐ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ │                                  │ │
 │ └──────────────────────────────────┘ │
 ╞══════════════════════════════════════╡
 │ ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪ │
 │ ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪ │
 │ ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪ │
 │ ▪▪▪  ▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪  ▪▪▪ │
 │               ╭────────╮             │
 └───────────────┴────────┴─────────────┘
"""
LAPTOP_SCREEN = (2, 4, 36, 11)

FLOPPIES = """
 ┌────┐
 │▐▌  │
 ├────┤
 │▐▌  │
 ├────┤
 │▐▌  │
 └────┘
"""

DISC = """
 ╭──────────╮
 │ ╭──────╮ │
 │ │      │ │
 │ ╰──────╯ │
 ╰──────────╯
"""

HEXES = """   __    __    __
  /  \\__/  \\__/  \\
  \\__/  \\__/  \\__/
  /  \\__/  \\__/  \\
  \\__/  \\__/  \\__/
     \\__/  \\__/"""


def load_panels(content_dir: Path) -> tuple[str, ...]:
  """Read the stop-error copy: blocks of ``content/_panic.txt`` split on ``---``."""
  path = content_dir / "_panic.txt"
  if not path.is_file():
    return ()
  blocks = PANEL_SEPARATOR.split(path.read_text(encoding="utf-8"))
  return tuple(block.strip("\n") for block in blocks if block.strip())


def hexdump(seed: int, lines: int, base: int = 0x8054C8A0) -> str:
  """Plain-text memory dump lines: address, four words, printable bytes."""
  rng = random.Random(seed)
  out: list[str] = []
  for index in range(lines):
    data = [rng.randrange(256) for _ in range(8)]
    if index % 9 == 4:
      data[:4] = [0x4D, 0x5A, 0x90, 0x00]
    words = " ".join(f"{data[i]:02x}{data[i + 1]:02x}" for i in range(0, 8, 2))
    text = "".join(chr(b) if 0x21 <= b <= 0x7E else "." for b in data)
    out.append(f"{base + index * 8:08x} {words} {text}")
  return "\n".join(out)


def _block(canvas: Canvas, row: int, col: int, art: str, cls: str) -> None:
  for r, line in enumerate(art.strip("\n").splitlines()):
    for c, glyph in enumerate(line):
      if glyph != " ":
        canvas.put(row + r, col + c, glyph, cls)


def _screen_style(top: int, left: int, box: tuple[int, int, int, int]) -> str:
  """Place a clipped screen layer over a sprite drawn at (top, left), in cells."""
  r, c, w, h = box
  bottom = ROWS - (top + r + h)
  return f"--c: {left + c}; --r: {bottom}; --w: {w}; --h: {h}"


def _glitch_patches(rng: random.Random, canvas: Canvas, count: int) -> int:
  placed, attempts = 0, 0
  taken: list[tuple[int, int, int, int]] = []
  while placed < count and attempts < 2000:
    attempts += 1
    height, width = rng.randint(4, 7), rng.randint(20, 34)
    row0 = rng.randint(8, canvas.rows - 2 - height)
    col0 = rng.randint(0, canvas.cols - width)
    row1, col1 = row0 + height, col0 + width
    if any(
      not (row1 <= r0 or r1 <= row0 or col1 <= c0 or c1 <= col0)
      for r0, r1, c0, c1 in taken
    ):
      continue
    cells = [canvas.cells[r][c] for r in range(row0, row1) for c in range(col0, col1)]
    if sum(1 for cell in cells if cell[0] != " ") < len(cells) // 4:
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
  """Return the scene: near layer, screen placements, crt stream, panels, gutters."""
  rng = random.Random(seed)
  near = Canvas(COLS, ROWS)
  ground = ROWS - 1
  for col in range(COLS):
    near.put(ground, col, "─", "ground")
  crt_top, crt_left = ground - 11, 100
  lap_top, lap_left = ground - 20, 134
  _block(near, crt_top, crt_left, CRT, "frame")
  _block(near, lap_top, lap_left, LAPTOP, "frame")
  _block(near, ground - 6, 176, FLOPPIES, "frame")
  _block(near, ground - 4, 187, DISC, "frame")
  near.put(ground - 2, 194, "◶", "disc")
  near.put(crt_top + 8, crt_left + 4, "▪", "led", "--i: 0")
  near.put(crt_top + 8, crt_left + 6, "▪", "led", "--i: 1")
  patches = _glitch_patches(rng, near, 3)
  return SimpleNamespace(
    cols=COLS,
    rows=ROWS,
    near=Markup(near.render()),
    crt=_screen_style(crt_top, crt_left, CRT_SCREEN),
    lap=_screen_style(lap_top, lap_left, LAPTOP_SCREEN),
    crt_text=hexdump(seed + 1, 30, 0x80400000),
    panels=tuple(_panel_markup(panel) for panel in panels),
    hexes=HEXES,
    patches=patches,
    gutter_left=hexdump(seed + 2, 160, 0x8054C8A0),
    gutter_right=hexdump(seed + 3, 160, 0x80400000),
  )


__all__ = ["ALLOWED_GLYPHS", "COLS", "ROWS", "hexdump", "load_panels", "panic_layers"]
