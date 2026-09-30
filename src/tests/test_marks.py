import re
import unittest

from sitegen.marks import LAVENDER, mark_svg


class TestMarks(unittest.TestCase):
  def test_marks_are_deterministic_per_seed_and_differ_between_seeds(self) -> None:
    first = mark_svg("/blogs/randomness_impl/", 56)

    self.assertEqual(first, mark_svg("/blogs/randomness_impl/", 56))
    self.assertNotEqual(first, mark_svg("/blogs/learn_ocaml/", 56))

  def test_marks_are_decorative_inline_svgs_in_lavender_only(self) -> None:
    svg = mark_svg("/about/", 18)

    self.assertTrue(
      svg.startswith('<svg class="mark" viewBox="0 0 64 64" width="18" height="18"')
    )
    self.assertIn('aria-hidden="true"', svg)
    self.assertTrue(svg.endswith("</svg>"))
    self.assertGreaterEqual(len(re.findall(r"<(circle|polygon|rect)\b", svg)), 3)
    for color in re.findall(r'fill="(#[0-9a-f]{6})"', svg):
      self.assertIn(color, LAVENDER)
