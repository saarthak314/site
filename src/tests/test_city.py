import re
import unittest
from collections import defaultdict

from sitegen.city import ALLOWED_GLYPHS, FAR_ROWS, NEAR_ROWS, city_layers

TAG_RE = re.compile(r"<[^>]+>")
LIGHT_RE = re.compile(r'class="(?:glitch )?lt')
GLITCH_RE = re.compile(r'class="glitch[^"]*" style="--i: (\d)')


def plain(markup: str) -> str:
  return TAG_RE.sub("", markup)


class TestCity(unittest.TestCase):
  def setUp(self) -> None:
    self.city = city_layers()

  def test_layers_are_deterministic_per_seed(self) -> None:
    again = city_layers()
    other = city_layers(seed=42)

    self.assertEqual(str(self.city.near), str(again.near))
    self.assertEqual(str(self.city.far), str(again.far))
    self.assertNotEqual(str(self.city.near), str(other.near))

  def test_layers_are_rectangular_and_use_only_shipped_glyphs(self) -> None:
    self.assertEqual(self.city.cols, 220)
    for layer, rows in ((self.city.near, NEAR_ROWS), (self.city.far, FAR_ROWS)):
      lines = plain(str(layer)).split("\n")
      self.assertEqual(len(lines), rows)
      self.assertEqual({len(line) for line in lines}, {self.city.cols})
      for character in "".join(lines):
        if ord(character) >= 0x80:
          self.assertIn(character, ALLOWED_GLYPHS)
      self.assertRegex(lines[-1], r"^[─┴]+$")

  def test_near_layer_mixes_shaded_mass_wireframes_and_solid_cores(self) -> None:
    text = plain(str(self.city.near))

    self.assertGreaterEqual(text.count("░"), 300)
    self.assertGreaterEqual(text.count("▒"), 100)
    self.assertGreaterEqual(text.count("┌"), 40)
    self.assertIn("/", text)
    self.assertIn("╭", text)
    cores = text.count("█")
    self.assertGreater(cores, 0)
    self.assertLess(cores, 160)
    self.assertNotIn("▄", text)

  def test_near_layer_is_dressed_and_far_layer_is_dark(self) -> None:
    near = str(self.city.near)
    far = str(self.city.far)

    self.assertGreaterEqual(len(LIGHT_RE.findall(near)), 150)
    self.assertLess(near.count("<span"), 260)
    self.assertEqual(near.count('class="beacon"'), 3)
    self.assertGreaterEqual(near.count('class="sign"'), 3)
    self.assertGreaterEqual(near.count('class="band"'), 2)
    self.assertGreaterEqual(near.count('class="strip"'), 3)
    self.assertRegex(
      near, r'class="(?:glitch )?lt lt--twinkle" style="(?:--i: \d; )?--i: \d"'
    )
    self.assertIn("lt--neon", near)
    self.assertEqual(LIGHT_RE.findall(far), [])
    self.assertLess(far.count("<span"), 60)
    self.assertRegex(far, r"[.']")
    for markup in (near, far):
      self.assertNotIn("<script", markup)
      self.assertNotIn("&#", markup)

  def test_glitch_patches_are_rectangles_that_share_an_index(self) -> None:
    rows_by_index: dict[str, set[int]] = defaultdict(set)
    for row, line in enumerate(str(self.city.near).split("\n")):
      for match in GLITCH_RE.finditer(line):
        rows_by_index[match.group(1)].add(row)

    self.assertGreaterEqual(len(rows_by_index), 5)
    for index, rows in rows_by_index.items():
      self.assertGreaterEqual(len(rows), 3, index)
      self.assertEqual(max(rows) - min(rows) + 1, len(rows), index)  # contiguous
