"""Deterministic abstract marks: one per page, seeded from its route."""

from __future__ import annotations

import hashlib
import math
import random

LAVENDER = ("#b4a3e6", "#8f7fc4", "#d9cffa")


def mark_svg(seed: str, size: int = 56) -> str:
  """Return an inline SVG of translucent overlapping shapes for ``seed``.

  The same seed always yields the same drawing. Shapes use only the three
  lavender tones and blend with ``mix-blend-mode: screen`` so overlaps glow.
  """
  rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
  box = 64
  shapes: list[str] = []
  for _ in range(rng.randint(3, 5)):
    kind = rng.choice(("circle", "circle", "polygon", "rect"))
    color = rng.choice(LAVENDER)
    opacity = rng.uniform(0.35, 0.85)
    cx, cy = rng.uniform(14, box - 14), rng.uniform(14, box - 14)
    if kind == "circle":
      shapes.append(
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rng.uniform(7, 18):.1f}" '
        f'fill="{color}" fill-opacity="{opacity:.2f}"/>'
      )
    elif kind == "rect":
      width, height = rng.uniform(10, 26), rng.uniform(10, 26)
      shapes.append(
        f'<rect x="{cx - width / 2:.1f}" y="{cy - height / 2:.1f}" '
        f'width="{width:.1f}" height="{height:.1f}" fill="{color}" '
        f'fill-opacity="{opacity:.2f}" '
        f'transform="rotate({rng.uniform(-30, 30):.0f} {cx:.1f} {cy:.1f})"/>'
      )
    else:
      sides = rng.choice((3, 5, 6))
      radius = rng.uniform(9, 18)
      rotation = rng.uniform(0, math.tau)
      points = " ".join(
        f"{cx + radius * math.cos(rotation + math.tau * k / sides):.1f},"
        f"{cy + radius * math.sin(rotation + math.tau * k / sides):.1f}"
        for k in range(sides)
      )
      shapes.append(
        f'<polygon points="{points}" fill="{color}" fill-opacity="{opacity:.2f}"/>'
      )
  return (
    f'<svg class="mark" viewBox="0 0 {box} {box}" width="{size}" height="{size}" '
    'aria-hidden="true" focusable="false" style="mix-blend-mode:screen">'
    f"{''.join(shapes)}</svg>"
  )


__all__ = ["LAVENDER", "mark_svg"]
