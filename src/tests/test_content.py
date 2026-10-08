import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sitegen.config import SiteConfig
from sitegen.content import ContentRepository
from sitegen.models import ContentError


class FakeRenderer:
  def __init__(self) -> None:
    self.calls: list[str] = []

  def render(self, markdown: str):
    self.calls.append(markdown)
    return SimpleNamespace(
      html=f"<p>{markdown.strip()}</p>",
      description=markdown.strip()[:160],
      reading_time="1 min read",
      has_math=False,
      has_code=False,
      headings=(),
    )


class TestContentRepository(unittest.TestCase):
  def setUp(self) -> None:
    self.temp_dir = tempfile.TemporaryDirectory()
    self.root = Path(self.temp_dir.name)
    self.root.joinpath("config.json").write_text(
      json.dumps(
        {
          "site_url": "https://example.com",
          "email": "hello@example.com",
          "social_image": "/images/default.png",
          "posts_per_page": 2,
        }
      )
    )
    blogs = self.root / "content" / "blogs"
    blogs.mkdir(parents=True)
    self.root.joinpath("content/_index.md").write_text(
      "title: home\ndate: 2026-08-20\n-----\nhome body"
    )
    blogs.joinpath("_index.md").write_text("title: writings\ndate: 2026-08-20\n-----\n")
    self._write_post(
      "alpha",
      "title: alpha\ndate: 2026-08-24\ntags: [systems, inference]",
    )
    self._write_post(
      "beta",
      "title: beta\ndate: 2026-08-23\nupdated: 2026-08-25\n"
      "slug: custom_beta\nsocial_image: /images/beta.png\ntags: systems",
    )
    self._write_post(
      "gamma",
      "title: gamma\ndate: 2026-08-22\npermalink: /notes/gamma/\ntags: compilers",
    )
    self._write_post(
      "draft",
      "title: draft\ndate: 2026-08-25\ndraft: true\ntags: systems",
    )
    self.config = SiteConfig.load(self.root)
    self.renderer = FakeRenderer()

  def tearDown(self) -> None:
    self.temp_dir.cleanup()

  def _write_post(self, directory: str, metadata: str) -> None:
    post_dir = self.root / "content" / "blogs" / directory
    post_dir.mkdir()
    post_dir.joinpath("index.md").write_text(f"{metadata}\n-----\n{directory} body")

  def test_discovers_typed_pages_once_and_builds_views(self) -> None:
    index = ContentRepository(self.config, self.renderer).discover(include_drafts=False)

    self.assertEqual([post.title for post in index.posts], ["alpha", "beta", "gamma"])
    self.assertEqual(
      [post.route for post in index.posts],
      ["/blogs/alpha/", "/blogs/custom_beta/", "/notes/gamma/"],
    )
    self.assertEqual(len(index.pages), 5)
    self.assertEqual(len(self.renderer.calls), 5)
    self.assertEqual(
      index.posts[0].social_image_url, "https://example.com/images/default.png"
    )
    self.assertEqual(
      index.posts[1].social_image_url, "https://example.com/images/beta.png"
    )

    self.assertEqual(
      [page.route for page in index.pagination], ["/blogs/", "/blogs/page/2/"]
    )
    self.assertEqual(index.pagination[0].next_url, "/blogs/page/2/")
    self.assertEqual(index.pagination[1].previous_url, "/blogs/")
    systems = next(tag for tag in index.tags if tag.slug == "systems")
    self.assertEqual([post.title for post in systems.items], ["alpha", "beta"])
    self.assertTrue(index.digest)

  def test_includes_drafts_by_default_and_keeps_them_out_of_search(self) -> None:
    index = ContentRepository(self.config, self.renderer).discover()

    self.assertEqual(index.posts[0].title, "draft")
    self.assertEqual(len(index.posts), 4)
    self.assertTrue(index.posts[0].draft)
    self.assertTrue(index.posts[0].noindex)
    self.assertFalse(index.posts[1].noindex)

  def test_carries_structured_homepage_sections_to_the_home_page(self) -> None:
    self.root.joinpath("content/_index.md").write_text(
      "title: home\n"
      "date: 2026-08-20\n"
      "experience:\n"
      "  - role: systems engineer\n"
      "    company: morph labs\n"
      "    company_url: https://morph.so\n"
      "    period: jun 2026 — present\n"
      "    highlights: [agentic workflows and cloud inference systems]\n"
      "projects:\n"
      "  - name: paimon\n"
      "    url: https://github.com/saarthak314/paimon\n"
      "    description: agentic coding harness\n"
      "    tech: [python, agents]\n"
      "  - name: web server\n"
      "    description: nginx-style web server\n"
      "    tech: [c, networking]\n"
      "-----\n"
      "home body"
    )

    index = ContentRepository(self.config, self.renderer).discover()
    home = index.page_for_route("/")

    self.assertEqual(home.experience[0].company, "morph labs")
    self.assertEqual(
      home.experience[0].highlights,
      ("agentic workflows and cloud inference systems",),
    )
    self.assertEqual(home.projects[0].tech, ("python", "agents"))
    self.assertIsNone(home.projects[1].url)

  def test_rejects_duplicate_routes(self) -> None:
    self._write_post(
      "collision",
      "title: collision\ndate: 2026-08-21\npermalink: /notes/gamma/",
    )

    with self.assertRaisesRegex(ContentError, "duplicate route or alias /notes/gamma/"):
      ContentRepository(self.config, self.renderer).discover()

  def test_rejects_blog_directory_without_index(self) -> None:
    self.root.joinpath("content/blogs/empty").mkdir()

    with self.assertRaisesRegex(
      ContentError, "empty/index.md: blog directory is missing index.md"
    ):
      ContentRepository(self.config, self.renderer).discover()

  def test_discovers_not_found_page_and_post_aliases(self) -> None:
    self.root.joinpath("content/404.md").write_text(
      "title: not found\ndate: 2026-08-26\nnoindex: true\n-----\nnothing here"
    )
    self._write_post(
      "aliased",
      "title: aliased\ndate: 2026-08-25\naliases: [/writeups/aliased/]",
    )

    index = ContentRepository(self.config, self.renderer).discover()

    not_found = index.page_for_route("/404.html")
    self.assertIsNotNone(not_found)
    self.assertTrue(not_found.noindex)
    aliased = index.page_for_route("/blogs/aliased/")
    self.assertEqual(aliased.aliases, ("/writeups/aliased/",))

  def test_discovers_optional_about_page(self) -> None:
    self.root.joinpath("content/about.md").write_text(
      "title: about me\n"
      "date: 2026-08-30\n"
      "description: the person outside the terminal\n"
      "-----\n"
      "about body"
    )

    index = ContentRepository(self.config, self.renderer).discover()

    about = index.page_for_route("/about/")
    self.assertIsNotNone(about)
    self.assertEqual(about.template, "about.html")
    self.assertEqual(about.output_path, Path("about/index.html"))
    self.assertFalse(about.is_post)

  def test_rejects_alias_that_collides_with_a_route(self) -> None:
    self._write_post(
      "colliding",
      "title: colliding\ndate: 2026-08-25\naliases: [/notes/gamma/]",
    )

    with self.assertRaisesRegex(ContentError, "duplicate route or alias"):
      ContentRepository(self.config, self.renderer).discover()


if __name__ == "__main__":
  unittest.main()
