import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sitegen.config import SiteConfig
from sitegen.frontmatter import parse_document
from sitegen.models import ContentError


class TestFrontMatter(unittest.TestCase):
  def test_parses_legacy_metadata_without_losing_final_line(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "index.md"
      path.write_text(
        "title: sample post\n"
        "date: 2026-08-20\n"
        "updated: 2026-08-24\n"
        "draft: false\n"
        "slug: sample_post\n"
        "permalink: /notes/sample/\n"
        "description: explicit summary\n"
        "social_image: /images/sample.png\n"
        "aliases: [/writeups/sample/, /notes/old-sample/]\n"
        "noindex: true\n"
        "tags: [systems, inference]\n"
        "template: blog.html\n"
        "-----\n\n"
        "final paragraph without newline"
      )

      document = parse_document(path)

      self.assertEqual(document.metadata.title, "sample post")
      self.assertEqual(document.metadata.date, date(2026, 8, 20))
      self.assertEqual(document.metadata.updated, date(2026, 8, 24))
      self.assertFalse(document.metadata.draft)
      self.assertEqual(document.metadata.slug, "sample_post")
      self.assertEqual(document.metadata.permalink, "/notes/sample/")
      self.assertEqual(document.metadata.description, "explicit summary")
      self.assertEqual(document.metadata.social_image, "/images/sample.png")
      self.assertEqual(
        document.metadata.aliases,
        ("/writeups/sample/", "/notes/old-sample/"),
      )
      self.assertTrue(document.metadata.noindex)
      self.assertEqual(document.metadata.tags, ("systems", "inference"))
      self.assertEqual(document.metadata.template, "blog.html")
      self.assertEqual(document.body, "\nfinal paragraph without newline")

  def test_parses_standard_yaml_front_matter(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "index.md"
      path.write_text(
        "---\n"
        "title: yaml post\n"
        "date: 2026-08-20\n"
        "tags: systems, compilers\n"
        "draft: true\n"
        "---\n"
        "body"
      )

      document = parse_document(path)

      self.assertTrue(document.metadata.draft)
      self.assertEqual(document.metadata.tags, ("systems", "compilers"))
      self.assertEqual(document.body, "body")

  def test_parses_structured_homepage_sections(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "_index.md"
      path.write_text(
        "title: home\n"
        "date: 2026-08-26\n"
        "experience:\n"
        "  - role: systems engineer\n"
        "    company: morph labs\n"
        "    company_url: https://morph.so\n"
        "    company_logo: /images/logos/morph.png\n"
        "    period: jun 2026 — present\n"
        "    highlights:\n"
        "      - agentic workflows and cloud inference systems\n"
        "projects:\n"
        "  - name: paimon\n"
        "    url: https://github.com/saarthak314/paimon\n"
        "    description: an agentic coding harness\n"
        "    tech: [python, agents]\n"
        "  - name: web server\n"
        "    description: nginx-style web server\n"
        "    tech: [c, networking]\n"
        "-----\n"
        "intro"
      )

      document = parse_document(path)

      experience = document.metadata.experience[0]
      self.assertEqual(experience.role, "systems engineer")
      self.assertEqual(experience.company, "morph labs")
      self.assertEqual(experience.company_url, "https://morph.so")
      self.assertEqual(experience.company_logo, "/images/logos/morph.png")
      self.assertEqual(experience.period, "jun 2026 — present")
      self.assertEqual(
        experience.highlights,
        ("agentic workflows and cloud inference systems",),
      )
      project = document.metadata.projects[0]
      self.assertEqual(project.name, "paimon")
      self.assertEqual(project.url, "https://github.com/saarthak314/paimon")
      self.assertEqual(project.description, "an agentic coding harness")
      self.assertEqual(project.tech, ("python", "agents"))
      unlinked_project = document.metadata.projects[1]
      self.assertEqual(unlinked_project.name, "web server")
      self.assertIsNone(unlinked_project.url)

  def test_rejects_invalid_structured_homepage_sections(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "_index.md"
      path.write_text(
        "title: home\ndate: 2026-08-26\nexperience: systems engineer\n-----\nintro"
      )

      with self.assertRaisesRegex(ContentError, "experience must be a list"):
        parse_document(path)

  def test_rejects_company_logos_outside_the_images_tree(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "_index.md"
      path.write_text(
        "title: home\ndate: 2026-08-26\nexperience:\n"
        "  - role: engineer\n    company: acme\n"
        "    company_logo: https://acme.test/logo.png\n    period: jun 2026\n"
        "-----\nintro"
      )

      with self.assertRaisesRegex(
        ContentError, "company_logo must live under /images/"
      ):
        parse_document(path)

  def test_reports_path_for_invalid_metadata(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "broken.md"
      path.write_text("title: broken\ndate: definitely-not-a-date\n-----\nbody")

      with self.assertRaisesRegex(ContentError, r"broken\.md: invalid date"):
        parse_document(path)

  def test_rejects_missing_title_and_invalid_permalink(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      missing_title = Path(temp_dir) / "missing.md"
      missing_title.write_text("date: 2026-08-20\n-----\nbody")
      with self.assertRaisesRegex(ContentError, "missing required title"):
        parse_document(missing_title)

      invalid_permalink = Path(temp_dir) / "invalid.md"
      invalid_permalink.write_text(
        "title: invalid\ndate: 2026-08-20\npermalink: notes/no-slashes\n-----\nbody"
      )
      with self.assertRaisesRegex(ContentError, "permalink must start and end with /"):
        parse_document(invalid_permalink)

      invalid_alias = Path(temp_dir) / "invalid-alias.md"
      invalid_alias.write_text(
        "title: invalid\n"
        "date: 2026-08-20\n"
        "aliases: [writeups/no-leading-slash]\n"
        "-----\n"
        "body"
      )
      with self.assertRaisesRegex(ContentError, "alias must start and end with /"):
        parse_document(invalid_alias)

  def test_rejects_unclosed_front_matter(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "broken.md"
      path.write_text("---\ntitle: broken\ndate: 2026-08-20\nbody")

      with self.assertRaisesRegex(ContentError, "unclosed YAML front matter"):
        parse_document(path)


class TestSiteConfig(unittest.TestCase):
  def test_loads_validated_paths_and_defaults(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      root.joinpath("config.json").write_text(
        json.dumps(
          {
            "site_url": "https://example.com/",
            "email": "hello@example.com",
            "social_image": "/images/social.png",
          }
        )
      )

      config = SiteConfig.load(root)

      self.assertEqual(config.site_url, "https://example.com")
      self.assertEqual(config.posts_per_page, 10)
      self.assertEqual(config.content_dir, root / "content")
      self.assertEqual(config.output_dir, root / "docs")

  def test_rejects_invalid_site_url_and_page_size(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      root.joinpath("config.json").write_text(
        json.dumps(
          {
            "site_url": "example.com",
            "email": "hello@example.com",
            "social_image": "/images/social.png",
            "posts_per_page": 0,
          }
        )
      )

      with self.assertRaisesRegex(
        ContentError, r"site_url must be an absolute http\(s\) URL"
      ):
        SiteConfig.load(root)


if __name__ == "__main__":
  unittest.main()
