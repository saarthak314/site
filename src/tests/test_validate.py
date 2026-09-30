import tempfile
import unittest
from pathlib import Path

from sitegen.validate import SiteValidator


class TestSiteValidator(unittest.TestCase):
  def setUp(self) -> None:
    self.temp_dir = tempfile.TemporaryDirectory()
    self.root = Path(self.temp_dir.name)

  def tearDown(self) -> None:
    self.temp_dir.cleanup()

  def write(self, relative_path: str, content: str = "") -> Path:
    path = self.root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path

  def html(self, canonical: str, body: str = "") -> str:
    return (
      "<!doctype html><html><head>"
      f'<link rel="canonical" href="{canonical}">'
      f"</head><body>{body}</body></html>"
    )

  def test_valid_site_has_no_issues(self) -> None:
    self.write(
      "index.html",
      self.html(
        "https://example.com/",
        '<h1 id="home">home</h1>'
        '<a href="/blogs/#post">post</a>'
        '<a href="#home">home section</a>'
        '<a href="https://other.example/page">external</a>'
        '<a href="mailto:hello@example.com">email</a>'
        '<a href="tel:+15555555555">phone</a>'
        '<a href="javascript:void(0)">script action</a>'
        '<img src="/images/avatar.png" alt="avatar">',
      ),
    )
    self.write(
      "blogs/index.html",
      self.html("https://example.com/blogs/", '<h2 id="post">post</h2>'),
    )
    self.write("images/avatar.png", "image")
    self.write(
      "feed.xml",
      '<?xml version="1.0"?><rss version="2.0"><channel /></rss>',
    )
    self.write(
      "sitemap.xml",
      '<?xml version="1.0"?>'
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
      "<url><loc>https://example.com/</loc></url>"
      "</urlset>",
    )

    self.assertEqual(SiteValidator().validate(self.root), [])

  def test_reports_unresolved_jinja_markers_with_source_path(self) -> None:
    html_path = self.write(
      "index.html",
      self.html("https://example.com/", "{{ title }}{% if published %}"),
    )

    issues = SiteValidator().validate(self.root)

    self.assertEqual({issue.path for issue in issues}, {html_path})
    self.assertTrue(any("{{" in issue.message for issue in issues))
    self.assertTrue(any("{%" in issue.message for issue in issues))

  def test_reports_missing_and_non_absolute_canonical_links(self) -> None:
    missing_path = self.write("index.html", "<html><head></head><body></body></html>")
    relative_path = self.write(
      "about/index.html",
      self.html("/about/"),
    )

    issues = SiteValidator().validate(self.root)

    self.assertTrue(
      any(
        issue.path == missing_path and "missing canonical" in issue.message
        for issue in issues
      )
    )
    self.assertTrue(
      any(
        issue.path == relative_path and "absolute canonical" in issue.message
        for issue in issues
      )
    )

  def test_checks_internal_directory_routes_and_fragments(self) -> None:
    source_path = self.write(
      "index.html",
      self.html(
        "https://example.com/",
        '<h1 id="local">home</h1>'
        '<a href="/blogs/">valid directory</a>'
        '<a href="/missing/">missing directory</a>'
        '<a href="#local">valid local fragment</a>'
        '<a href="#absent">missing local fragment</a>'
        '<a href="/blogs/#entry">valid remote fragment</a>'
        '<a href="/blogs/#absent">missing remote fragment</a>',
      ),
    )
    self.write(
      "blogs/index.html",
      self.html("https://example.com/blogs/", '<h2 id="entry">entry</h2>'),
    )

    issues = SiteValidator().validate(self.root)
    source_messages = [issue.message for issue in issues if issue.path == source_path]

    self.assertEqual(
      sum("broken internal href" in message for message in source_messages), 1
    )
    self.assertEqual(
      sum("missing fragment" in message for message in source_messages), 2
    )
    self.assertTrue(any("/missing/" in message for message in source_messages))
    self.assertTrue(any("#absent" in message for message in source_messages))

  def test_checks_same_origin_absolute_links_and_ignores_external_http(self) -> None:
    source_path = self.write(
      "index.html",
      self.html(
        "https://example.com/",
        '<a href="https://example.com/missing/">missing local page</a>'
        '<a href="https://external.example/missing/">external page</a>',
      ),
    )

    issues = SiteValidator().validate(self.root)
    source_messages = [issue.message for issue in issues if issue.path == source_path]

    self.assertEqual(
      sum("broken internal href" in message for message in source_messages), 1
    )
    self.assertTrue(
      any("example.com/missing" in message for message in source_messages)
    )
    self.assertFalse(any("external.example" in message for message in source_messages))

  def test_reports_missing_local_src_assets_and_ignores_remote_sources(self) -> None:
    source_path = self.write(
      "posts/index.html",
      self.html(
        "https://example.com/posts/",
        '<img src="../images/present.png">'
        '<img src="/images/missing.png">'
        '<img src="">'
        '<script src="https://cdn.example/app.js"></script>'
        '<img src="data:image/png;base64,AAAA">',
      ),
    )
    self.write("images/present.png", "image")

    issues = SiteValidator().validate(self.root)
    source_messages = [issue.message for issue in issues if issue.path == source_path]

    self.assertEqual(
      sum("missing local src" in message for message in source_messages), 2
    )
    self.assertTrue(
      any("/images/missing.png" in message for message in source_messages)
    )
    self.assertTrue(any('""' in message for message in source_messages))

  def test_reports_unparseable_rss_and_sitemap_xml(self) -> None:
    feed_path = self.write("feed.xml", "<rss><channel></rss>")
    sitemap_path = self.write("sitemap.xml", "<urlset><url></urlset>")

    issues = SiteValidator().validate(self.root)

    self.assertTrue(
      any(issue.path == feed_path and "RSS XML" in issue.message for issue in issues)
    )
    self.assertTrue(
      any(
        issue.path == sitemap_path and "sitemap XML" in issue.message
        for issue in issues
      )
    )

  def test_reports_non_absolute_sitemap_locations(self) -> None:
    sitemap_path = self.write(
      "sitemap.xml",
      '<?xml version="1.0"?>'
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
      "<url><loc>https://example.com/</loc></url>"
      "<url><loc>/blogs/</loc></url>"
      "<url><loc></loc></url>"
      "</urlset>",
    )

    issues = SiteValidator().validate(self.root)
    sitemap_messages = [issue.message for issue in issues if issue.path == sitemap_path]

    self.assertEqual(
      sum("absolute sitemap loc" in message for message in sitemap_messages), 2
    )
    self.assertTrue(any("/blogs/" in message for message in sitemap_messages))

  def test_every_issue_identifies_its_source_output_path(self) -> None:
    html_path = self.write(
      "index.html",
      '<html><body>{{ unresolved }}<a href="/missing/">missing</a></body></html>',
    )
    feed_path = self.write("feed.xml", "<rss>")

    issues = SiteValidator().validate(self.root)

    self.assertGreater(len(issues), 0)
    self.assertTrue(all(issue.path in {html_path, feed_path} for issue in issues))

  def test_issue_format_includes_source_path_and_message(self) -> None:
    html_path = self.write("index.html", "<html></html>")

    issue = SiteValidator().validate(self.root)[0]

    self.assertEqual(issue.format(), f"{html_path}: missing canonical link")


if __name__ == "__main__":
  unittest.main()
