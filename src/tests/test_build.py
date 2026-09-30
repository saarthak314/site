import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sitegen.build import BuildError, BuildOptions, SiteBuilder


class FakeMarkdownRenderer:
  def render(self, markdown: str):
    return SimpleNamespace(
      html=f"<p>{markdown.strip()}</p>",
      description=markdown.strip(),
      reading_time="1 min read",
      has_math=False,
      has_code=False,
    )


class FakeTemplateRenderer:
  def render_page(self, page, index) -> str:
    return f"<html><head><link rel='canonical' href='{page.canonical_url}'></head><body>{page.title}</body></html>"

  def render_archive(self, page, pagination, index) -> str:
    titles = ",".join(item.title for item in pagination.items)
    canonical = f"https://example.com{pagination.route}"
    return f"<html><head><link rel='canonical' href='{canonical}'></head><body>{titles}</body></html>"

  def render_tag(self, tag, index) -> str:
    return f"<html><head><link rel='canonical' href='https://example.com{tag.route}'></head><body>{tag.name}</body></html>"

  def render_redirect(self, alias: str, page) -> str:
    return (
      "<html><head><meta name='robots' content='noindex'>"
      f"<link rel='canonical' href='{page.canonical_url}'></head>"
      f"<body><a href='{page.route}'>{alias}</a></body></html>"
    )

  def template_digest(self, template_name: str) -> str:
    return f"template:{template_name}"


class FakeValidator:
  def __init__(self, issues=None) -> None:
    self.issues = issues or []

  def validate(self, root: Path):
    return list(self.issues)


class TestSiteBuilder(unittest.TestCase):
  def setUp(self) -> None:
    self.temp_dir = tempfile.TemporaryDirectory()
    self.root = Path(self.temp_dir.name)
    self.root.joinpath("config.json").write_text(
      json.dumps(
        {
          "site_url": "https://example.com",
          "email": "hello@example.com",
          "social_image": "/images/social.png",
          "posts_per_page": 1,
        }
      )
    )
    blogs = self.root / "content" / "blogs"
    blogs.mkdir(parents=True)
    self.root.joinpath("content/_index.md").write_text(
      "title: home\ndate: 2026-08-20\n-----\nhome"
    )
    blogs.joinpath("_index.md").write_text("title: writings\ndate: 2026-08-20\n-----\n")
    self.root.joinpath("content/404.md").write_text(
      "title: not found\ndate: 2026-08-26\nnoindex: true\n-----\nmissing"
    )
    self._write_post("newer", "2026-08-24", "systems")
    self._write_post("older", "2026-08-23", "systems")
    self.root.joinpath("static/images").mkdir(parents=True)
    self.root.joinpath("static/index.css").write_text("body {}")
    self.root.joinpath("static/images/social.png").write_bytes(b"png")
    self.root.joinpath("templates").mkdir()
    for name in ("home.html", "writings.html", "blog.html", "tags.html"):
      self.root.joinpath("templates", name).write_text(name)

  def tearDown(self) -> None:
    self.temp_dir.cleanup()

  def _write_post(self, slug: str, published: str, tag: str) -> None:
    post = self.root / "content" / "blogs" / slug
    post.mkdir()
    post.joinpath("index.md").write_text(
      f"title: {slug}\ndate: {published}\ntags: [{tag}]\n"
      + ("aliases: [/writeups/newer/]\n" if slug == "newer" else "")
      + f"-----\n{slug} body"
    )

  def _builder(self, validator=None) -> SiteBuilder:
    return SiteBuilder(
      self.root,
      markdown_renderer=FakeMarkdownRenderer(),
      template_renderer=FakeTemplateRenderer(),
      validator=validator or FakeValidator(),
    )

  def test_build_writes_complete_site_and_removes_stale_outputs(self) -> None:
    report = self._builder().build(BuildOptions(incremental=False))

    self.assertTrue(report.output_dir.joinpath("index.html").is_file())
    self.assertTrue(report.output_dir.joinpath("404.html").is_file())
    self.assertTrue(report.output_dir.joinpath("blogs/newer/index.html").is_file())
    self.assertTrue(report.output_dir.joinpath("writeups/newer/index.html").is_file())
    self.assertTrue(report.output_dir.joinpath("blogs/page/2/index.html").is_file())
    self.assertTrue(report.output_dir.joinpath("tags/systems/index.html").is_file())
    self.assertTrue(report.output_dir.joinpath("feed.xml").is_file())
    self.assertTrue(report.output_dir.joinpath("sitemap.xml").is_file())
    self.assertTrue(report.output_dir.joinpath(".sitegen-manifest.json").is_file())

    stale = report.output_dir / "stale.html"
    stale.write_text("stale")
    self._builder().build(BuildOptions(incremental=False))
    self.assertFalse(stale.exists())

  def test_failed_validation_preserves_previous_output(self) -> None:
    output = self.root / "docs"
    output.mkdir()
    output.joinpath("sentinel.txt").write_text("old build")
    issue = SimpleNamespace(format=lambda: "broken link")

    with self.assertRaisesRegex(BuildError, "broken link"):
      self._builder(FakeValidator([issue])).build()

    self.assertEqual(output.joinpath("sentinel.txt").read_text(), "old build")

  def test_second_incremental_build_reuses_generated_outputs(self) -> None:
    first = self._builder().build()
    second = self._builder().build()

    self.assertGreater(first.rendered, 0)
    self.assertEqual(second.rendered, 0)
    self.assertGreater(second.reused, 0)

  def test_pipeline_version_change_invalidates_cached_outputs(self) -> None:
    self._builder().build()

    with patch("sitegen.build.RENDER_PIPELINE_VERSION", "next"):
      rebuilt = self._builder().build()

    self.assertGreater(rebuilt.rendered, 0)


if __name__ == "__main__":
  unittest.main()
