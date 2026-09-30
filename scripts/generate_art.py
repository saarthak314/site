"""Generate the site's static SVG art: the footer sea and the Monte Carlo dartboard.

Both drawings are seeded so every run produces byte-identical output.
"""

import math
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_IMAGE_DIR = PROJECT_ROOT / "static" / "images"

INK = "#f2f0ea"
INK_3 = "#85827c"
ACCENT = "#b4a3e6"


def sea_svg(
  width: int = 1200,
  height: int = 220,
  rows: int = 44,
  seed: int = 7,
  color: str = INK,
  horizon_inset: int = 160,
  ease: float = 2.4,
) -> str:
  """A trapezoid of horizontal dashes, dense at the horizon and sparse in front."""
  rng = random.Random(seed)
  paths = []
  for row in range(rows):
    depth = (row / (rows - 1)) ** ease
    y = 12 + depth * (height - 24)
    inset = (1 - depth) * horizon_inset - 24
    x_start, x_end = inset, width - inset
    opacity = 0.06 + 0.22 * depth
    stroke = 0.7 + 0.5 * depth
    wavelength = 140 + 260 * depth
    segments = []
    x = x_start + rng.random() * 30
    while x < x_end:
      phase = 0.85 * row
      swell = (math.sin(x / wavelength * math.tau + phase) + 1) / 2
      ripple = (math.sin(x / (wavelength * 0.37) * math.tau - phase) + 1) / 2
      dash = 4 + (swell * 0.7 + ripple * 0.3) ** 1.35 * (10 + 44 * depth)
      dash *= 0.6 + rng.random() * 0.8
      gap = 6 + rng.random() * (10 + 26 * depth)
      segments.append(f"M{x:.1f} {y:.1f}h{min(dash, x_end - x):.1f}")
      x += dash + gap
    paths.append(
      f'<path d="{"".join(segments)}" stroke-opacity="{opacity:.3f}" '
      f'stroke-width="{stroke:.2f}"/>'
    )
  return (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
    f'width="{width}" height="{height}" preserveAspectRatio="xMidYMax slice" '
    f'aria-hidden="true" focusable="false">'
    f'<g fill="none" stroke="{color}" stroke-linecap="butt">{"".join(paths)}</g></svg>\n'
  )


def dartboard_svg(darts: int = 180, seed: int = 3) -> str:
  """A square dartboard with an inscribed circle and seeded random darts."""
  rng = random.Random(seed)
  points = []
  for _ in range(darts):
    x, y = rng.uniform(-1, 1), rng.uniform(-1, 1)
    points.append((x, y, x * x + y * y < 1))
  inside = sum(1 for point in points if point[2])
  estimate = 4 * inside / darts
  dots = "".join(
    f'<circle cx="{110 + x * 100:.1f}" cy="{110 + y * 100:.1f}" r="1.6" '
    f'fill="{ACCENT if hit else INK_3}"/>'
    for x, y, hit in points
  )
  label = (
    f"a square dartboard with an inscribed circle and {darts} random darts, "
    f"{inside} inside the circle, so 4 × {inside}/{darts} ≈ {estimate:.3f}"
  )
  return (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" width="320" '
    f'height="220" role="img" aria-label="{label}">'
    f'<rect x="10" y="10" width="200" height="200" fill="none" stroke="{INK}" '
    'stroke-opacity=".35" stroke-width="1"/>'
    f'<circle cx="110" cy="110" r="100" fill="none" stroke="{ACCENT}" stroke-width="1"/>'
    f"{dots}"
    f'<g font-family="IBM Plex Mono, ui-monospace, monospace" font-size="11" fill="{INK_3}">'
    f'<text x="228" y="100">darts   {darts}</text>'
    f'<text x="228" y="118" fill="{ACCENT}">inside  {inside}</text>'
    f'<text x="228" y="136">4 × {inside}/{darts}</text>'
    f'<text x="228" y="154" fill="{INK}">≈ {estimate:.3f}</text></g></svg>\n'
  )


def main() -> None:
  sea = OUTPUT_IMAGE_DIR / "sea.svg"
  sea.write_text(sea_svg())
  dartboard = OUTPUT_IMAGE_DIR / "diagrams" / "dartboard.svg"
  dartboard.parent.mkdir(parents=True, exist_ok=True)
  dartboard.write_text(dartboard_svg())
  for path in (sea, dartboard):
    print(f"{path.relative_to(PROJECT_ROOT)}: {path.stat().st_size} bytes")


if __name__ == "__main__":
  main()
