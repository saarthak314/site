import tempfile
import unittest
from pathlib import Path

from sitegen.panic import (
  ALLOWED_GLYPHS,
  COLS,
  CRT_SCREEN,
  LAPTOP,
  LAPTOP_SCREEN,
  PC,
  ROWS,
  hexdump,
  load_panels,
  panic_layers,
)

PANELS = (
  "first panel\n\nPAGE_FAULT_IN_NONPAGED_AREA\n\n*** STOP: 0x00000050",
  "second",
)


class TestPanicScene(unittest.TestCase):
  def test_same_panels_render_the_same_scene(self) -> None:
    first = panic_layers(PANELS)
    second = panic_layers(PANELS)

    self.assertEqual(str(first.near), str(second.near))
    self.assertEqual(first.crt, second.crt)
    self.assertEqual(first.gutter_left, second.gutter_left)

  def test_near_layer_has_the_expected_shape_and_only_shipped_glyphs(self) -> None:
    scene = panic_layers(PANELS)
    text = str(scene.near)
    plain = _strip_tags(text)
    rows = plain.split("\n")

    self.assertEqual(scene.cols, COLS)
    self.assertEqual(scene.rows, ROWS)
    self.assertEqual(len(rows), ROWS)
    self.assertTrue(all(len(row) == COLS for row in rows))
    unexpected = {glyph for glyph in plain if ord(glyph) > 127} - ALLOWED_GLYPHS
    self.assertFalse(unexpected, f"glyphs outside the font subset: {unexpected}")

  def test_scene_places_machines_screens_and_lag_patches(self) -> None:
    scene = panic_layers(PANELS)
    text = str(scene.near)

    self.assertIn('class="disc"', text)
    self.assertEqual(text.count('class="led"'), scene.leds)
    self.assertEqual(scene.leds, 4)
    self.assertEqual(scene.patches, 3)
    self.assertRegex(scene.crt, r"^--c: \d+; --r: \d+; --w: 20; --h: 6$")
    self.assertRegex(scene.lap, r"^--c: \d+; --r: \d+; --w: 36; --h: 11$")
    self.assertEqual(len(scene.crt_text.split("\n")), 30)

  def test_machine_sprites_are_rectangular_with_screens_inside(self) -> None:
    for art, (row, col, width, height) in ((PC, CRT_SCREEN), (LAPTOP, LAPTOP_SCREEN)):
      lines = art.splitlines()
      for offset in range(height):
        line = lines[row + offset]
        self.assertEqual(line[col : col + width], " " * width)
        self.assertNotEqual(line[col - 1], " ")
        self.assertNotEqual(line[col + width], " ")

  def test_panels_are_escaped_and_stop_codes_marked(self) -> None:
    scene = panic_layers(("<script>PAGE_FAULT_IN_NONPAGED_AREA\n*** STOP: 0x50",))

    self.assertEqual(len(scene.panels), 1)
    self.assertIn("&lt;script&gt;", str(scene.panels[0]))
    self.assertIn("<b>PAGE_FAULT_IN_NONPAGED_AREA</b>", str(scene.panels[0]))
    self.assertIn("<b>*** STOP</b>: 0x50", str(scene.panels[0]))

  def test_load_panels_splits_blocks_on_rules_and_tolerates_a_missing_file(
    self,
  ) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      content_dir = Path(temp_dir)
      self.assertEqual(load_panels(content_dir), ())
      (content_dir / "_panic.txt").write_text("one\nline two\n---\n\ntwo\n---\n")

      self.assertEqual(load_panels(content_dir), ("one\nline two", "two"))

  def test_hexdump_is_plain_ascii_with_addresses(self) -> None:
    dump = hexdump(1, 4, 0x80400000)
    rows = dump.split("\n")

    self.assertEqual(len(rows), 4)
    self.assertTrue(rows[0].startswith("80400000 "))
    self.assertTrue(rows[1].startswith("80400008 "))
    self.assertTrue(dump.isascii())
    self.assertEqual(hexdump(1, 4, 0x80400000), dump)


def _strip_tags(text: str) -> str:
  out: list[str] = []
  inside = False
  for char in text:
    if char == "<":
      inside = True
    elif char == ">":
      inside = False
    elif not inside:
      out.append(char)
  return "".join(out).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


if __name__ == "__main__":
  unittest.main()
