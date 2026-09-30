import tempfile
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont

from sitegen.font_pipeline import SYMBOL_UNICODES, covered_codepoints, subset_font

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FONT = PROJECT_ROOT / "assets" / "fonts" / "JetBrainsMono-Regular.ttf"


class TestFontPipeline(unittest.TestCase):
  def test_symbol_subset_is_small_and_covers_box_drawing_and_lambda(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      output = Path(temp_dir) / "symbols.woff2"
      size = subset_font(SOURCE_FONT, output, SYMBOL_UNICODES)
      cmap = TTFont(str(output)).getBestCmap()

    self.assertLess(size, 12_000)
    for codepoint in (0x03BB, 0x2500, 0x2571, 0x2588, 0x259F, 0x25B6, 0x2192):
      self.assertIn(codepoint, cmap)
    self.assertNotIn(ord("a"), cmap)

  def test_covered_codepoints_unions_every_shipped_font(self) -> None:
    covered = covered_codepoints(PROJECT_ROOT / "static" / "fonts")

    self.assertIn(ord("a"), covered)
    self.assertIn(0x03BB, covered)
    self.assertIn(0x2500, covered)
