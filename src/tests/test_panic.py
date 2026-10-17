import tempfile
import unittest
from pathlib import Path

from sitegen.panic import ALLOWED_GLYPHS, COLS, ROWS, load_panels, panic_layers

PANELS = (
  "first panel\n\nPAGE_FAULT_IN_NONPAGED_AREA\n\n*** STOP: 0x00000050",
  "second",
)


class TestPanicScene(unittest.TestCase):
  def test_same_panels_render_the_same_scene(self) -> None:
    first = panic_layers(PANELS)
    second = panic_layers(PANELS)

    self.assertEqual(str(first.near), str(second.near))
    self.assertEqual(str(first.far), str(second.far))
    self.assertEqual(first.wires, second.wires)

  def test_layers_have_the_expected_shape_and_only_shipped_glyphs(self) -> None:
    scene = panic_layers(PANELS)
    for layer in (scene.near, scene.far):
      plain = _strip_tags(str(layer))
      rows = plain.split("\n")

      self.assertEqual(len(rows), ROWS)
      self.assertTrue(all(len(row) == COLS for row in rows))
      unexpected = {glyph for glyph in plain if ord(glyph) > 127} - ALLOWED_GLYPHS
      self.assertFalse(unexpected, f"glyphs outside the font subset: {unexpected}")
    self.assertEqual(scene.cols, COLS)
    self.assertEqual(scene.rows, ROWS)

  def test_scene_has_poles_wires_birds_packet_lanes_and_lag_patches(self) -> None:
    scene = panic_layers(PANELS)
    near = str(scene.near)
    far = str(scene.far)

    self.assertIn('class="pole"', near)
    self.assertIn('class="ins"', near)
    self.assertIn('class="can"', near)
    self.assertIn('class="wire"', near)
    self.assertIn('class="wire wire--fan"', near)
    self.assertIn('class="bird"', near)
    self.assertIn('class="lamp"', far)
    self.assertIn('class="star"', far)
    self.assertEqual(scene.patches, 3)
    lanes = scene.wires.split(";")
    self.assertGreaterEqual(len(lanes), 6)
    for lane in lanes:
      r0, c0, r1, c1, sag = lane.split(",")
      self.assertLess(int(c0), int(c1))
      self.assertTrue(0 <= int(r0) < ROWS and 0 <= int(r1) < ROWS)
      self.assertGreater(float(sag), 0)

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
