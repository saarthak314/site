from pathlib import Path

from fontTools import subset

SYMBOL_UNICODES = (
  "U+0020,U+0023,U+0027,U+002A,U+002B,U+002E,U+002F,U+003A,U+005C,"
  "U+00B7,U+2022,U+2500-25FF,U+2190-21FF,U+03BB"
)
"""Box drawing, block elements, geometric shapes, arrows, and the lambda, plus
the space, the two dots, and the few ASCII marks the home banner, city footer,
and ships are drawn with: the home page needs no other JetBrains Mono file."""


def subset_font(source: Path, output: Path, unicodes: str = SYMBOL_UNICODES) -> int:
  """Write a woff2 subset of ``source`` covering ``unicodes`` and return its size."""
  options = subset.Options()
  options.flavor = "woff2"
  options.hinting = False
  options.desubroutinize = True
  options.layout_features = []
  options.name_IDs = ["*"]
  options.notdef_outline = True
  font = subset.load_font(str(source), options)
  try:
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=subset.parse_unicodes(unicodes))
    subsetter.subset(font)
    output.parent.mkdir(parents=True, exist_ok=True)
    subset.save_font(font, str(output), options)
  finally:
    font.close()
  return output.stat().st_size


def covered_codepoints(font_dir: Path) -> set[int]:
  """Return the union of Unicode code points mapped by every woff2 in ``font_dir``."""
  from fontTools.ttLib import TTFont

  covered: set[int] = set()
  for path in sorted(font_dir.glob("*.woff2")):
    with TTFont(str(path)) as font:
      covered.update(font.getBestCmap())
  return covered


__all__ = ["SYMBOL_UNICODES", "covered_codepoints", "subset_font"]
