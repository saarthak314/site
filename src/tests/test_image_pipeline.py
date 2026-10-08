import tempfile
import unittest
from pathlib import Path

from PIL import Image

from sitegen.image_pipeline import (
  optimize_image,
  write_favicon,
  write_responsive_variants,
  write_social_card,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestImagePipeline(unittest.TestCase):
  def test_repository_uses_the_original_dedicated_favicon_source(self) -> None:
    source = PROJECT_ROOT / "assets" / "images" / "favicon.png"
    script = PROJECT_ROOT.joinpath("scripts/optimize_images.py").read_text()

    self.assertTrue(source.is_file())
    with Image.open(source) as favicon:
      self.assertEqual(favicon.size, (256, 256))
      self.assertEqual(favicon.convert("RGBA").getpixel((0, 0))[3], 0)
    self.assertIn('SOURCE_IMAGE_DIR / "favicon.png"', script)
    self.assertNotIn(
      'write_favicon(SOURCE_IMAGE_DIR / "ritsuko.png"',
      script,
    )

  def test_source_rasters_are_kept_out_of_the_published_static_tree(self) -> None:
    source_names = {
      "ritsuko.png",
      "immutability.jpg",
      "frieren-studying.jpg",
      "lain_studying.png",
      "gojo.jpeg",
      "reddit-meme.jpg",
      "lain-meme.jpeg",
      "amazon-ml-third.png",
      "amazon-ml-submission.jpg",
      "amazon-ml-workflow.png",
      "amazon-ml-system.png",
      "amazon-ml-timeline.png",
      "amazon-ml-journey.png",
    }

    source_dir = PROJECT_ROOT / "assets" / "images"
    static_dir = PROJECT_ROOT / "static" / "images"
    self.assertTrue(all(source_dir.joinpath(name).is_file() for name in source_names))
    self.assertTrue(
      all(not static_dir.joinpath(name).exists() for name in source_names)
    )

  def test_optimize_image_resizes_and_writes_webp(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      source = root / "source.png"
      output = root / "optimized.webp"
      Image.new("RGB", (1200, 800), "#282828").save(source)

      optimize_image(source, output, max_width=600)

      with Image.open(output) as optimized:
        self.assertEqual(optimized.format, "WEBP")
        self.assertEqual(optimized.size, (600, 400))

  def test_responsive_variants_only_include_smaller_widths(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      source = root / "source.png"
      output = root / "article.webp"
      Image.new("RGB", (800, 400), "#282828").save(source)

      variants = write_responsive_variants(source, output, widths=(480, 960))

      self.assertEqual(variants, (root / "article-480w.webp",))
      with Image.open(variants[0]) as optimized:
        self.assertEqual(optimized.size, (480, 240))

  def test_social_card_uses_standard_preview_dimensions(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      source = root / "source.png"
      output = root / "social.jpg"
      Image.new("RGB", (1920, 1080), "#282828").save(source)

      write_social_card(source, output)

      with Image.open(output) as card:
        self.assertEqual(card.format, "JPEG")
        self.assertEqual(card.size, (1200, 630))

  def test_favicon_is_reduced_to_browser_sized_frames(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      source = root / "source.png"
      output = root / "favicon.ico"
      Image.new("RGB", (512, 512), "#282828").save(source)

      write_favicon(source, output)

      self.assertLess(output.stat().st_size, 20_000)
      with Image.open(output) as favicon:
        self.assertEqual(favicon.format, "ICO")
        self.assertIn(favicon.size, {(16, 16), (32, 32), (48, 48)})


if __name__ == "__main__":
  unittest.main()
