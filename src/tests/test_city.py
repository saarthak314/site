import re
import unittest
from pathlib import Path

from sitegen.city import ALLOWED_GLYPHS, FAR_ROWS, NEAR_ROWS, STAR_ROWS, city_layers

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAG_RE = re.compile(r"<[^>]+>")
LIGHT_RE = re.compile(r'class="lt')


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

    self.assertGreaterEqual(text.count("░"), 250)
    self.assertGreaterEqual(text.count("▒"), 100)
    self.assertGreaterEqual(text.count("┌"), 30)
    self.assertIn("/", text)
    self.assertIn("╭", text)
    cores = text.count("█")
    self.assertGreater(cores, 0)
    self.assertLess(cores, 160)
    self.assertNotIn("▄", text)

  def test_near_layer_is_sparsely_lit_and_far_layer_is_dark(self) -> None:
    near = str(self.city.near)
    far = str(self.city.far)

    lights = len(LIGHT_RE.findall(near))
    self.assertTrue(60 <= lights <= 90, lights)
    self.assertLessEqual(near.count("lt--neon"), 8)
    self.assertLess(near.count("<span"), 140)
    self.assertEqual(near.count('class="beacon"'), 2)
    self.assertGreaterEqual(len(re.findall(r'class="sign"', near)), 1)
    self.assertGreaterEqual(len(re.findall(r'class="band"', near)), 1)
    self.assertGreaterEqual(len(re.findall(r'class="strip"', near)), 1)
    self.assertNotIn("lt--twinkle", near)
    self.assertEqual(LIGHT_RE.findall(far), [])
    self.assertNotIn("<span", far)
    self.assertRegex(far, r"[.']")
    for markup in (near, far):
      self.assertNotIn("<script", markup)
      self.assertNotIn("&#", markup)

  def test_skyline_carries_no_glitch_patches(self) -> None:
    self.assertNotIn("glitch", str(self.city.near))
    self.assertNotIn("glitch", str(self.city.far))


class TestStars(unittest.TestCase):
  def test_star_layer_is_sparse_plain_text_with_a_few_twinkles(self) -> None:
    stars = str(city_layers().stars)
    lines = stars.split("\n")
    stripped = [re.sub(r"<[^>]+>", "", line) for line in lines]

    self.assertEqual(len(lines), STAR_ROWS)
    self.assertTrue(all(len(line) == 220 for line in stripped))
    glyphs = "".join(stripped).replace(" ", "")
    self.assertTrue(15 <= len(glyphs) <= 40, len(glyphs))
    self.assertTrue(set(glyphs) <= set(".'+*"), set(glyphs))
    self.assertEqual(stars.count('class="star star--twinkle"'), 3)
    self.assertEqual(stars, str(city_layers().stars))


class TestCityStaysQuiet(unittest.TestCase):
  def test_footer_is_short_and_only_beacons_stars_and_one_ship_move(self) -> None:
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    script = PROJECT_ROOT.joinpath("static", "site.js").read_text()

    footer = re.search(r"\.footer--city \{[^}]*\}", stylesheet).group(0)
    self.assertIn("height: 280px", footer)
    city_keyframes = set(re.findall(r"@keyframes (city-[a-z-]+)", stylesheet))
    self.assertEqual(city_keyframes, {"city-twinkle", "city-beacon"})
    self.assertNotIn("lt--twinkle", stylesheet)
    self.assertIn("state.alive < 1", script)
    self.assertIn("between(18000, 30000)", script)
