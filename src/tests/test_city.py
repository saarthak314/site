import re
import unittest
from pathlib import Path

from sitegen.city import ALLOWED_GLYPHS, FAR_ROWS, NEAR_ROWS, STAR_ROWS, city_layers

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIGHT_RE = re.compile(r'<rect class="lt')


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
    for layer, rows in (
      (self.city.text.near, NEAR_ROWS),
      (self.city.text.far, FAR_ROWS),
    ):
      lines = layer.split("\n")
      self.assertEqual(len(lines), rows)
      self.assertEqual({len(line) for line in lines}, {self.city.cols})
      for character in "".join(lines):
        if ord(character) >= 0x80:
          self.assertIn(character, ALLOWED_GLYPHS)
      self.assertRegex(lines[-1], r"^[─┴]+$")

  def test_near_layer_mixes_shaded_mass_wireframes_and_solid_cores(self) -> None:
    text = self.city.text.near

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

    # lit windows are the font's squares drawn as squares; beacons pulse as
    # HTML marks over the picture; neon strips, bands and signs stay glyphs
    lights = len(LIGHT_RE.findall(near))
    self.assertTrue(60 <= lights <= 90, lights)
    self.assertEqual(self.city.text.near.count("▪"), lights + 2)
    self.assertLessEqual(near.count("lt--neon"), 8)
    self.assertLess(near.count('<tspan class="'), 40)
    self.assertEqual(near.count('<i class="beacon"'), 2)
    self.assertGreaterEqual(len(re.findall(r'<tspan class="sign"', near)), 1)
    self.assertGreaterEqual(len(re.findall(r'<tspan class="band"', near)), 1)
    self.assertGreaterEqual(len(re.findall(r'<tspan class="strip"', near)), 1)
    self.assertNotIn("lt--twinkle", near)
    self.assertNotIn("▪", near)
    self.assertEqual(LIGHT_RE.findall(far), [])
    self.assertNotIn('<tspan class="', far)
    self.assertRegex(far, r"[.']")
    for markup in (near, far):
      self.assertTrue(markup.startswith('<svg viewBox="0 0 1320 '), markup[:40])
      self.assertNotIn("<span", markup)
      self.assertNotIn("<pre", markup)
      self.assertNotIn("<script", markup)
      self.assertNotIn("&#", markup)

  def test_skyline_carries_no_glitch_patches(self) -> None:
    self.assertNotIn("glitch", str(self.city.near))
    self.assertNotIn("glitch", str(self.city.far))


class TestStars(unittest.TestCase):
  def test_star_layer_is_sparse_with_a_few_twinkles(self) -> None:
    city = city_layers()
    lines = city.text.stars.split("\n")

    self.assertEqual(len(lines), STAR_ROWS)
    self.assertTrue(all(len(line) == 220 for line in lines))
    glyphs = "".join(lines).replace(" ", "")
    self.assertTrue(15 <= len(glyphs) <= 40, len(glyphs))
    self.assertTrue(set(glyphs) <= set(".'+*"), set(glyphs))
    # the three that twinkle are HTML marks over the SVG, not part of it
    stars = str(city.stars)
    self.assertEqual(
      len(re.findall(r'<i class="star" style="--c: \d+; --r: \d+; --i: \d"', stars)), 3
    )
    self.assertEqual(stars, str(city_layers().stars))


class TestCityStaysQuiet(unittest.TestCase):
  def test_footer_is_short_and_only_beacons_stars_and_one_ship_move(self) -> None:
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    script = PROJECT_ROOT.joinpath("static", "site.js").read_text()

    footer = re.search(r"\.footer--city \{[^}]*\}", stylesheet).group(0)
    self.assertIn("height: 280px", footer)
    city_keyframes = set(re.findall(r"@keyframes (city-[a-z-]+)", stylesheet))
    self.assertEqual(city_keyframes, {"city-twinkle", "city-beacon"})
    # only HTML marks pulse: nothing inside the SVG pictures animates
    for name in ("star", "beacon"):
      rule = re.search(rf"\n\.city \.{name} \{{[^}}]*\}}", stylesheet).group(0)
      self.assertIn("animation: city-", rule)
    self.assertNotRegex(
      stylesheet, r"\.city__layer (text|rect|tspan)[^{]*\{[^}]*animation"
    )
    self.assertNotIn("lt--twinkle", stylesheet)
    self.assertIn("state.alive < 1", script)
    self.assertIn("between(18000, 30000)", script)
