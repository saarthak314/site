import tempfile
import unittest
from pathlib import Path

from sitegen.manifest import BuildManifest, digest_paths


class TestBuildManifest(unittest.TestCase):
  def test_round_trips_entries(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      manifest = BuildManifest(entries={"index.html": "abc", "feed.xml": "def"})

      manifest.write(root)

      self.assertEqual(BuildManifest.load(root), manifest)

  def test_missing_or_invalid_manifest_is_empty(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      self.assertEqual(BuildManifest.load(root), BuildManifest())
      root.joinpath(".sitegen-manifest.json").write_text("not json")
      self.assertEqual(BuildManifest.load(root), BuildManifest())

  def test_digest_paths_changes_with_path_and_content(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      first = root / "first.txt"
      second = root / "second.txt"
      first.write_text("same")
      second.write_text("same")

      digest = digest_paths([first, second], root)
      second.write_text("changed")

      self.assertNotEqual(digest, digest_paths([first, second], root))


if __name__ == "__main__":
  unittest.main()
