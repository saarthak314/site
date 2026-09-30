"""Generate the site's static SVG art: the Monte Carlo dartboard.

The drawing is seeded so every run produces byte-identical output.
"""

import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_IMAGE_DIR = PROJECT_ROOT / "static" / "images"

INK = "#f2f0ea"
INK_3 = "#85827c"
ACCENT = "#b4a3e6"


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
  dartboard = OUTPUT_IMAGE_DIR / "diagrams" / "dartboard.svg"
  dartboard.parent.mkdir(parents=True, exist_ok=True)
  dartboard.write_text(dartboard_svg())
  print(f"{dartboard.relative_to(PROJECT_ROOT)}: {dartboard.stat().st_size} bytes")


if __name__ == "__main__":
  main()
