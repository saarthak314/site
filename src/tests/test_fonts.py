import json
import shutil
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from sitegen.build import BuildOptions, SiteBuilder
from sitegen.font_pipeline import covered_codepoints

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _TextCollector(HTMLParser):
  SKIPPED = {"script", "style"}

  def __init__(self) -> None:
    super().__init__()
    self.text: list[str] = []
    self._skip_depth = 0

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    if tag in self.SKIPPED:
      self._skip_depth += 1

  def handle_endtag(self, tag: str) -> None:
    if tag in self.SKIPPED and self._skip_depth:
      self._skip_depth -= 1

  def handle_data(self, data: str) -> None:
    if not self._skip_depth:
      self.text.append(data)


def is_cjk(codepoint: int) -> bool:
  """Foreign-script quotations are set from system fonts on purpose."""
  return (
    0x2E80 <= codepoint <= 0x9FFF
    or 0xAC00 <= codepoint <= 0xD7AF
    or 0xF900 <= codepoint <= 0xFAFF
    or 0xFF00 <= codepoint <= 0xFFEF
  )


def rendered_text(path: Path) -> str:
  parser = _TextCollector()
  parser.feed(path.read_text())
  return "".join(parser.text)


class TestFontCoverage(unittest.TestCase):
  def setUp(self) -> None:
    self.temp_dir = tempfile.TemporaryDirectory()
    project_root = Path(self.temp_dir.name)
    for directory in ("content", "templates", "static"):
      shutil.copytree(PROJECT_ROOT / directory, project_root / directory)
    project_root.joinpath("config.json").write_text(
      json.dumps(json.loads(PROJECT_ROOT.joinpath("config.json").read_text()))
    )
    self.output_dir = (
      SiteBuilder(project_root).build(BuildOptions(incremental=False)).output_dir
    )

  def tearDown(self) -> None:
    self.temp_dir.cleanup()

  def test_every_rendered_non_ascii_character_has_a_shipped_glyph(self) -> None:
    covered = covered_codepoints(PROJECT_ROOT / "static" / "fonts")
    missing: dict[str, set[str]] = {}

    for page in sorted(self.output_dir.rglob("*.html")):
      for character in rendered_text(page):
        codepoint = ord(character)
        if codepoint < 0x80 or character.isspace() or is_cjk(codepoint):
          continue
        if codepoint in covered:
          continue
        missing.setdefault(f"U+{ord(character):04X} {character}", set()).add(
          str(page.relative_to(self.output_dir))
        )

    self.assertEqual(
      missing,
      {},
      "characters rendered without a shipped glyph (they fall back to system fonts)",
    )
