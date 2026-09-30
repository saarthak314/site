"""A deterministic ASCII night skyline for the footer.

Two layers of wireframe buildings are drawn from box-drawing characters and
slashes, then dressed with lit windows, neon strips, bands, billboard signs,
beacons, and glitch slices as ``<span>`` hooks the stylesheet animates. The
same seed always yields the same city.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from types import SimpleNamespace

from markupsafe import Markup

ALLOWED_GLYPHS = frozenset("▪│┃━▓░▒█▀┌┐└┘╭╮╯╰─┴")

Cell = tuple[str, str | None, str | None]  # glyph, class, style
NEAR_ROWS = 26
FAR_ROWS = 20
STAR_ROWS = 40


@dataclass
class Building:
  x: int
  width: int
  height: int
  kind: str  # spire, tall, mid, low, core
  antenna: int = 0
  beacon: bool = False
  rounded: bool = False
  fill: str = " "  # interior: " " hollow, "░" shaded, "▒" dense, "█" solid core


class Canvas:
  def __init__(self, cols: int, rows: int) -> None:
    self.cols = cols
    self.rows = rows
    self.cells: list[list[Cell]] = [
      [(" ", None, None) for _ in range(cols)] for _ in range(rows)
    ]

  def put(
    self,
    row: int,
    col: int,
    glyph: str,
    cls: str | None = None,
    style: str | None = None,
  ) -> None:
    if 0 <= row < self.rows and 0 <= col < self.cols:
      self.cells[row][col] = (glyph, cls, style)

  def glyph(self, row: int, col: int) -> str:
    return self.cells[row][col][0]

  def cls(self, row: int, col: int) -> str | None:
    return self.cells[row][col][1]

  def render(self) -> str:
    return "\n".join(_render_row(row) for row in self.cells)


def _render_row(row: list[Cell]) -> str:
  parts: list[str] = []
  run: list[str] = []
  run_key: tuple[str | None, str | None] = (None, None)

  def flush() -> None:
    if not run:
      return
    text = escape("".join(run), quote=False)
    cls, style = run_key
    if cls is None:
      parts.append(text)
    else:
      attributes = f' class="{cls}"' + (f' style="{style}"' if style else "")
      parts.append(f"<span{attributes}>{text}</span>")
    run.clear()

  for glyph, cls, style in row:
    key = (cls, style)
    if key != run_key:
      flush()
      run_key = key
    run.append(glyph)
  flush()
  return "".join(parts)


def _plan_buildings(
  rng: random.Random, cols: int, rows: int, spires: int, gap_chance: float
) -> list[Building]:
  buildings: list[Building] = []
  x = 0
  targets = [int(cols * 0.42), int(cols * 0.74), int(cols * 0.88)][:spires]
  cluster_start = int(cols * 0.70)
  usable = rows - 1  # the last row is the ground line
  while x < cols - 3:
    due_spire = bool(targets) and x >= targets[0] and x + 9 <= cols
    in_cluster = x >= cluster_start
    if due_spire:
      targets.pop(0)
      width = 9
      height = usable - 4 if len(targets) == spires - 1 else usable - rng.randint(5, 6)
      kind = "spire"
    elif in_cluster and spires > 1 and rng.random() < 0.3:
      width = rng.choice((3, 4, 5))
      height = rng.randint(int(usable * 0.15), int(usable * 0.35))
      kind = "core"
    elif in_cluster:
      width = rng.choice((4, 5, 6, 7, 8))
      height = rng.randint(int(usable * 0.5), int(usable * 0.8))
      kind = "tall" if height >= usable * 0.6 else "mid"
    else:
      roll = rng.random()
      if roll < 0.18:
        width = rng.choice((6, 7, 8, 9, 10))
        height = rng.randint(int(usable * 0.55), int(usable * 0.75))
        kind = "tall"
      elif roll < 0.7:
        width = rng.choice((4, 5, 6, 7))
        height = rng.randint(int(usable * 0.3), int(usable * 0.5))
        kind = "mid"
      else:
        width = rng.choice((3, 4, 5))
        height = rng.randint(2, max(3, int(usable * 0.25)))
        kind = "low"
    if targets and x + width > targets[0] and kind != "spire":
      width = max(4, targets[0] - x)
    width = min(width, cols - x)
    if width < 3:
      break
    building = Building(x=x, width=width, height=height, kind=kind)
    if kind == "spire":
      building.antenna = rng.randint(2, 3)
    elif kind == "tall" and rng.random() < 0.4:
      building.antenna = rng.randint(1, 2)
    if kind in {"mid", "low"} and rng.random() < 0.2:
      building.rounded = True
    buildings.append(building)
    x += width + (1 if rng.random() < gap_chance else 0)
  return buildings


def _draw_frame(
  canvas: Canvas, x: int, width: int, top: int, rounded: bool, fill: str = " "
) -> None:
  """A box outline from ``top`` down to the ground row, filled with ``fill``."""
  ground = canvas.rows - 1
  left, right = x, x + width - 1
  cap = "▀" if fill in {"░", "▒"} else "─"
  canvas.put(top, left, "╭" if rounded else "┌")
  canvas.put(top, right, "╮" if rounded else "┐")
  for col in range(left + 1, right):
    canvas.put(top, col, cap)
  for row in range(top + 1, ground):
    canvas.put(row, left, "│")
    canvas.put(row, right, "│")
    for col in range(left + 1, right):
      canvas.put(row, col, fill)
  canvas.put(ground, left, "┴")
  canvas.put(ground, right, "┴")


def _draw_core(canvas: Canvas, building: Building) -> None:
  """A short solid mass with no frame: weight in the cluster."""
  ground = canvas.rows - 1
  top = ground - building.height
  for col in range(building.x, building.x + building.width):
    canvas.put(top, col, "▀")
    for row in range(top + 1, ground):
      canvas.put(row, col, "█")
    canvas.put(ground, col, "─")


def _draw_block(canvas: Canvas, building: Building) -> None:
  top = canvas.rows - 1 - building.height
  _draw_frame(canvas, building.x, building.width, top, building.rounded, building.fill)
  if building.width >= 6 and top >= 1:
    # a rooftop penthouse box, offset from centre like the reference's mechanical floors
    center = building.x + building.width // 2
    offset = (building.x * 7) % (building.width - 4)
    left = building.x + 1 + offset
    if building.antenna and left <= center <= left + 2:
      left = (
        building.x + 1 if center > building.x + 3 else building.x + building.width - 4
      )
    if not (building.antenna and left <= center <= left + 2):
      canvas.put(top - 1, left, "┌")
      canvas.put(top - 1, left + 1, "─")
      canvas.put(top - 1, left + 2, "┐")
  _draw_antenna(canvas, building, top, building.x + building.width // 2)


def _draw_spire(canvas: Canvas, building: Building) -> None:
  """A wireframe body whose roof tapers with ASCII slopes to an antenna."""
  center = building.x + building.width // 2
  ground = canvas.rows - 1
  reach_max = building.width // 2 - 1  # 3 for a 9-wide spire
  body_top = ground - building.height + reach_max + 1
  _draw_frame(canvas, building.x, building.width, body_top, False, building.fill)
  for col in range(building.x + 1, building.x + building.width - 1):
    canvas.put(body_top, col, " ")
  canvas.put(body_top, center - reach_max, "┘")
  canvas.put(body_top, center + reach_max, "└")
  for reach in range(reach_max, 0, -1):
    row = body_top - (reach_max - reach + 1)
    canvas.put(row, center - reach, "/")
    canvas.put(row, center + reach, "\\")
    for col in range(center - reach + 1, center + reach):
      canvas.put(row, col, building.fill if building.fill != " " else " ")
  apex = body_top - reach_max - 1
  canvas.put(apex, center, "│")
  _draw_antenna(canvas, building, apex, center)


def _draw_antenna(canvas: Canvas, building: Building, top: int, center: int) -> None:
  for offset in range(1, building.antenna + 1):
    row = top - offset
    if row < 0:
      break
    if offset == building.antenna and building.beacon:
      canvas.put(row, center, "▪", "beacon")
    else:
      canvas.put(row, center, "│")


def _window_columns(building: Building) -> list[int]:
  inner_left = building.x + 2
  inner_right = building.x + building.width - 2
  return list(range(inner_left, inner_right + 1, 2))


def _dress_windows(
  rng: random.Random, canvas: Canvas, buildings: list[Building], budget: int, lit: bool
) -> int:
  count = 0
  ground = canvas.rows - 1
  for building in buildings:
    if building.kind == "core" or (building.kind == "low" and rng.random() < 0.5):
      continue
    columns = _window_columns(building)
    if not columns:
      continue
    top = ground - building.height
    if building.kind == "spire":
      top += building.width // 2
    probability = {"spire": 0.85, "tall": 0.85, "mid": 0.7, "low": 0.5}[building.kind]
    for row in range(top + 2, ground - 1, 2):
      for col in columns:
        if canvas.glyph(row, col) not in {" ", "░", "▒"}:
          continue
        if lit and count < budget and rng.random() < probability:
          cls = "lt"
          if count % 8 == 5:
            cls += " lt--neon"
          elif count % 4 == 1:
            cls += " lt--bright"
          style = None
          if count % 7 == 2:
            cls += " lt--twinkle"
            style = f"--i: {rng.randint(0, 7)}"
          canvas.put(row, col, "▪", cls, style)
          count += 1
        elif building.fill == " ":
          canvas.put(row, col, rng.choice("..:"))
  return count


def _dress_texture(
  rng: random.Random, canvas: Canvas, buildings: list[Building]
) -> None:
  wide = [b for b in buildings if b.width >= 8 and b.kind in {"tall", "mid"}]
  rng.shuffle(wide)
  ground = canvas.rows - 1
  for building in wide[:3]:
    glyph = rng.choice("=#")
    top = ground - building.height
    rows = rng.sample(range(top + 1, ground - 1), k=min(2, max(1, ground - 2 - top)))
    for row in rows:
      for col in range(building.x + 1, building.x + building.width - 1):
        if canvas.glyph(row, col) in {" ", ".", ":", "░"}:
          canvas.put(row, col, glyph)


def _dress_neon(
  rng: random.Random,
  canvas: Canvas,
  buildings: list[Building],
  *,
  strips: int,
  bands: int,
  signs: int,
) -> None:
  ground = canvas.rows - 1
  talls = [b for b in buildings if b.kind in {"spire", "tall"}]
  mids = [b for b in buildings if b.kind == "mid" and b.width >= 5]
  rng.shuffle(talls)
  for building in talls[:strips]:
    edge = building.x if rng.random() < 0.5 else building.x + building.width - 1
    top = (
      ground
      - building.height
      + (building.width // 2 if building.kind == "spire" else 0)
    )
    start = top + rng.randint(1, 3)
    length = rng.randint(3, 6)
    for row in range(start, min(ground, start + length)):
      if canvas.glyph(row, edge) == "│":
        canvas.put(row, edge, "┃", "strip")
  rng.shuffle(talls)
  for building in talls[:bands]:
    top = (
      ground
      - building.height
      + (building.width // 2 if building.kind == "spire" else 0)
    )
    row = rng.randint(top + 2, ground - 3)
    for col in range(building.x + 1, building.x + building.width - 1):
      if canvas.cls(row, col) is None:
        canvas.put(row, col, "━", "band")
  rng.shuffle(mids)
  for index, building in enumerate(mids[:signs]):
    width = min(rng.randint(2, 4), building.width - 2)
    height = rng.choice((1, 1, 2))
    top = ground - building.height
    row0 = min(top + 1, ground - height - 1)
    col0 = building.x + 1 + rng.randint(0, max(0, building.width - 2 - width))
    for row in range(row0, row0 + height):
      for col in range(col0, col0 + width):
        if canvas.cls(row, col) is None and canvas.glyph(row, col) not in {"│", "┃"}:
          canvas.put(row, col, "▓", "sign", f"--i: {index}")


def _dress_glitches(rng: random.Random, canvas: Canvas, count: int) -> int:
  """Wrap rectangular patches in glitch spans, one ``--i`` per patch.

  Every row segment of a patch shares the patch's ``--i`` so the stylesheet can
  shake the rectangle as one laggy region. Lit windows inside a patch are kept
  as nested spans; other neon spans are avoided.
  """
  placed = 0
  attempts = 0
  taken: list[tuple[int, int, int, int]] = []  # row0, row1, col0, col1
  while placed < count and attempts < 3000:
    attempts += 1
    height = rng.randint(5, 8)
    width = rng.randint(24, 40)
    row0 = rng.randint(4, min(24, canvas.rows - 2) - height)
    col0 = rng.randint(0, canvas.cols - width)
    row1, col1 = row0 + height, col0 + width
    if any(
      not (row1 <= r0 or r1 <= row0 or col1 <= c0 or c1 <= col0)
      for r0, r1, c0, c1 in taken
    ):
      continue
    cells = [canvas.cells[r][c] for r in range(row0, row1) for c in range(col0, col1)]
    if any(cell[1] is not None and cell[1].startswith("beacon") for cell in cells):
      continue
    if sum(1 for cell in cells if cell[0] != " ") < len(cells) // 3:
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


def _draw_ground(canvas: Canvas) -> None:
  row = canvas.rows - 1
  for col in range(canvas.cols):
    if canvas.glyph(row, col) == " ":
      canvas.put(row, col, "─")


def _stars(cols: int, rows: int, seed: int, count: int = 46, twinkling: int = 6) -> str:
  """A sparse field of plain-text stars for the sky band above the skyline."""
  rng = random.Random(seed)
  canvas = Canvas(cols, rows)
  placed = 0
  attempts = 0
  while placed < count and attempts < count * 20:
    attempts += 1
    row, col = rng.randrange(rows), rng.randrange(cols)
    if canvas.glyph(row, col) != " ":
      continue
    if any(
      canvas.glyph(r, c) != " "
      for r in range(max(0, row - 1), min(rows, row + 2))
      for c in range(max(0, col - 3), min(cols, col + 4))
    ):
      continue
    glyph = rng.choices(".'+*", weights=(7, 1, 1, 1))[0]
    if placed < twinkling:
      canvas.put(row, col, glyph, "star star--twinkle", f"--i: {placed}")
    else:
      canvas.put(row, col, glyph)
    placed += 1
  return canvas.render()


def _scatter_sky_lights(rng: random.Random, canvas: Canvas, count: int) -> None:
  """Distant plain-text lights around the far roofline."""
  placed = 0
  attempts = 0
  while placed < count and attempts < 300:
    attempts += 1
    col = rng.randrange(canvas.cols)
    # find the first drawn cell in this column and sit a little above it
    roof = next((r for r in range(canvas.rows) if canvas.glyph(r, col) != " "), None)
    row = (roof if roof is not None else canvas.rows - 1) - rng.randint(1, 3)
    if row < 0 or canvas.glyph(row, col) != " ":
      continue
    canvas.put(row, col, rng.choice(".'"))
    placed += 1


def _assign_fills(rng: random.Random, buildings: list[Building], *, near: bool) -> None:
  """Shade most facades, densify the spires and tallest towers, keep a quarter hollow."""
  talls = sorted(
    (b for b in buildings if b.kind == "tall"), key=lambda b: b.height, reverse=True
  )
  dense = {id(b) for b in talls[: rng.randint(2, 3)]}
  for building in buildings:
    if building.kind == "core":
      building.fill = "█"
    elif building.kind == "spire" or id(building) in dense:
      building.fill = "▒"
    elif rng.random() < (0.25 if near else 0.5):
      building.fill = " "
    else:
      building.fill = "░"


def _layer(cols: int, rows: int, seed: int, *, near: bool) -> str:
  rng = random.Random(seed)
  canvas = Canvas(cols, rows)
  buildings = _plan_buildings(
    rng, cols, rows, spires=3 if near else 1, gap_chance=0.35 if near else 0.55
  )
  if near:
    for building in sorted(
      (b for b in buildings if b.kind == "spire"), key=lambda b: b.height, reverse=True
    )[:3]:
      building.beacon = True
  _assign_fills(rng, buildings, near=near)
  for building in buildings:
    if building.kind == "spire":
      _draw_spire(canvas, building)
    elif building.kind == "core":
      _draw_core(canvas, building)
    else:
      _draw_block(canvas, building)
  _draw_ground(canvas)
  if near:
    _dress_windows(rng, canvas, buildings, budget=172, lit=True)
    _dress_texture(rng, canvas, buildings)
    _dress_neon(rng, canvas, buildings, strips=4, bands=3, signs=5)
    _dress_glitches(rng, canvas, count=5)
  else:
    _dress_windows(rng, canvas, buildings, budget=0, lit=False)
    _dress_neon(rng, canvas, buildings, strips=2, bands=0, signs=0)
    _scatter_sky_lights(rng, canvas, count=18)
  return canvas.render()


@lru_cache(maxsize=4)
def city_layers(cols: int = 220, seed: int = 1701) -> SimpleNamespace:
  """Return the far and near skyline layers as HTML, plus the column count."""
  return SimpleNamespace(
    cols=cols,
    stars=Markup(_stars(cols, STAR_ROWS, seed + 2)),
    far=Markup(_layer(cols, FAR_ROWS, seed + 1, near=False)),
    near=Markup(_layer(cols, NEAR_ROWS, seed, near=True)),
  )


__all__ = ["ALLOWED_GLYPHS", "FAR_ROWS", "NEAR_ROWS", "STAR_ROWS", "city_layers"]
