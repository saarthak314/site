import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from sitegen.content import ContentIndex, TagPage
from sitegen.feeds import render_rss, render_sitemap
from sitegen.models import Page


def make_page(
  title: str, route: str, published: date, *, post: bool, draft: bool = False
) -> Page:
  return Page(
    source_path=Path(f"content{route}index.md"),
    output_path=Path(route.strip("/")) / "index.html"
    if route != "/"
    else Path("index.html"),
    route=route,
    canonical_url=f"https://example.com{route}",
    title=title,
    date=published,
    updated=None,
    draft=draft,
    noindex=draft,
    slug=title.replace(" ", "-"),
    permalink=None,
    description=f"description for {title}",
    social_image_url="https://example.com/images/social.png",
    social_image_width=1200,
    social_image_height=630,
    social_image_type="image/png",
    tags=(),
    template="blog.html" if post else "home.html",
    markdown="body",
    rendered=SimpleNamespace(
      html="<p>body</p>", reading_time="1 min read", has_math=False, has_code=False
    ),
    is_post=post,
    aliases=(),
  )


class TestFeeds(unittest.TestCase):
  def setUp(self) -> None:
    self.home = make_page("home", "/", date(2026, 8, 20), post=False)
    self.newer = make_page("newer", "/blogs/newer/", date(2026, 8, 24), post=True)
    self.older = make_page("older", "/blogs/older/", date(2026, 7, 10), post=True)
    self.index = ContentIndex(
      pages=(self.home, self.newer, self.older),
      posts=(self.newer, self.older),
      tags=(TagPage("systems", "systems", "/tags/systems/", (self.newer,)),),
      digest="digest",
    )

  def test_rss_uses_index_order_and_absolute_urls(self) -> None:
    root = ET.fromstring(render_rss(self.index, "https://example.com"))
    channel = root.find("channel")
    items = channel.findall("item")

    self.assertEqual([item.findtext("title") for item in items], ["newer", "older"])
    self.assertEqual(items[0].findtext("link"), "https://example.com/blogs/newer/")
    self.assertEqual(items[0].findtext("pubDate"), "Mon, 24 Aug 2026 00:00:00 +0000")

  def test_sitemap_includes_pages_and_tags_once(self) -> None:
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(render_sitemap(self.index, "https://example.com"))
    locations = [
      node.findtext("s:loc", namespaces=namespace)
      for node in root.findall("s:url", namespace)
    ]

    self.assertEqual(
      locations,
      [
        "https://example.com/",
        "https://example.com/blogs/newer/",
        "https://example.com/blogs/older/",
        "https://example.com/tags/systems/",
      ],
    )


if __name__ == "__main__":
  unittest.main()


class TestDraftFeeds(unittest.TestCase):
  def test_drafts_stay_out_of_the_feed_and_sitemap(self) -> None:
    draft = make_page("wip", "/blogs/wip/", date(2026, 9, 1), post=True, draft=True)
    done = make_page("done", "/blogs/done/", date(2026, 8, 1), post=True)
    index = ContentIndex(
      pages=(draft, done),
      posts=(draft, done),
      tags=(),
      digest="x",
    )

    rss = render_rss(index, "https://example.com")
    sitemap = render_sitemap(index, "https://example.com")

    self.assertNotIn("wip", rss)
    self.assertIn("done", rss)
    self.assertNotIn("/blogs/wip/", sitemap)
    self.assertIn("/blogs/done/", sitemap)
