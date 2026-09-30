from pathlib import Path

from fontTools import subset

SYMBOL_UNICODES = "U+2500-25FF,U+2190-21FF,U+03BB"
"""Box drawing, block elements, geometric shapes, arrows, and the lambda."""


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
  subsetter = subset.Subsetter(options)
  subsetter.populate(unicodes=subset.parse_unicodes(unicodes))
  subsetter.subset(font)
  output.parent.mkdir(parents=True, exist_ok=True)
  subset.save_font(font, str(output), options)
  return output.stat().st_size


def covered_codepoints(font_dir: Path) -> set[int]:
  """Return the union of Unicode code points mapped by every woff2 in ``font_dir``."""
  from fontTools.ttLib import TTFont

  covered: set[int] = set()
  for path in sorted(font_dir.glob("*.woff2")):
    covered.update(TTFont(str(path)).getBestCmap())
  return covered


__all__ = ["SYMBOL_UNICODES", "covered_codepoints", "subset_font"]
