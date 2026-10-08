import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from sitegen.build import BuildOptions, SiteBuilder

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestSiteRendering(unittest.TestCase):
  def setUp(self) -> None:
    self.temp_dir = tempfile.TemporaryDirectory()
    self.project_root = Path(self.temp_dir.name)
    for directory in ("content", "templates", "static"):
      shutil.copytree(PROJECT_ROOT / directory, self.project_root / directory)

    config = json.loads(PROJECT_ROOT.joinpath("config.json").read_text())
    self.project_root.joinpath("config.json").write_text(json.dumps(config))
    self.output_dir = (
      SiteBuilder(self.project_root).build(BuildOptions(incremental=False)).output_dir
    )

  def tearDown(self) -> None:
    self.temp_dir.cleanup()

  def test_real_site_renders_shared_metadata_and_complete_archive(self) -> None:
    home = self.output_dir.joinpath("index.html").read_text()
    archive = self.output_dir.joinpath("blogs/index.html").read_text()
    article = self.output_dir.joinpath("blogs/learn_ocaml/index.html").read_text()
    not_found = self.output_dir.joinpath("404.html").read_text()

    for page in (home, archive, article):
      self.assertIn('type="application/rss+xml"', page)
      self.assertIn('property="og:title"', page)
      self.assertIn('name="twitter:card" content="summary_large_image"', page)
      self.assertIn('href="/feed.xml">rss</a>', page)
    self.assertIn('href="mailto:hey@sarrthak.com">email</a>', home)
    self.assertNotIn('href="mailto:hey@sarrthak.com">email</a>', article)

    for page in (home, archive, article):
      footer = page[
        page.index('<footer class="footer footer--city">') : page.index("</footer>")
      ]
      self.assertIn('<div class="city" aria-hidden="true" data-city', footer)
      self.assertIn('<pre class="city__layer city__layer--near">', footer)
      self.assertIn('<div class="city__ships"></div>', footer)
      self.assertNotIn("<a ", footer)
      self.assertNotIn("<img", footer)
    self.assertIn('rel="canonical" href="https://sarrthak.com/"', home)
    self.assertIn('property="og:type" content="website"', home)
    self.assertIn(
      'property="og:image" content="https://sarrthak.com/images/social-card.jpg"',
      home,
    )
    self.assertIn('property="og:image:width" content="1200"', home)
    self.assertIn('property="og:image:height" content="630"', home)
    self.assertIn('property="og:type" content="article"', article)
    self.assertIn('property="article:modified_time" content="2026-08-26"', article)
    self.assertIn('type="application/ld+json"', article)
    self.assertIn('name="robots" content="noindex, nofollow"', not_found)
    self.assertIn('class="home-writing-all" href="/blogs/">all writings</a>', home)
    self.assertIn(
      'class="home-projects-all" href="https://github.com/saarthak314">'
      "all projects</a>",
      home,
    )
    self.assertIn('href="https://www.math.inc">math.inc</a>', home)
    self.assertIn(
      '<img class="home-experience__logo" src="/images/logos/mathinc.png"', home
    )
    self.assertIn('class="home-project__tech">python · agents</span>', home)
    self.assertLess(home.index(">kurama</a>"), home.index(">sakura</a>"))
    self.assertLess(home.index(">sakura</a>"), home.index(">web server</span>"))
    self.assertLess(home.index(">web server</span>"), home.index(">paimon</a>"))
    for removed_project in ("pixel editor", "redis clone", "rag pipeline", "cf-parser"):
      self.assertNotIn(removed_project, home)
    self.assertLess(home.index('id="experience"'), home.index('id="writing"'))
    self.assertLess(home.index('id="writing"'), home.index('id="projects"'))
    for slug in ("make_cool_stuff", "learn_ocaml", "randomness_impl"):
      self.assertIn(f'href="/blogs/{slug}/"', archive)
    for published in ("30 aug", "30 jul", "19 jul"):
      self.assertIn(f'<span class="writing-row__date">{published}</span>', archive)
    self.assertIn(
      '<h2 class="writings-year__heading" id="year-2025">2025</h2>', archive
    )
    self.assertNotIn('class="tree"', archive)
    self.assertIn('<p class="writing-row__summary">', archive)
    self.assertNotIn("&lt;- home", archive)

  def test_about_page_keeps_personal_details_and_setup_discoverable(self) -> None:
    about_path = self.output_dir.joinpath("about/index.html")
    self.assertTrue(about_path.is_file())

    about = about_path.read_text()
    home = self.output_dir.joinpath("index.html").read_text()
    llms = self.output_dir.joinpath("llms.txt").read_text()
    locations = [
      element.text
      for element in ET.parse(self.output_dir / "sitemap.xml").getroot().iter()
      if element.tag.endswith("loc")
    ]

    self.assertIn('<body class="about-page">', about)
    self.assertIn('<h1 class="about-heading">about me</h1>', about)
    for marker in (
      "outside work",
      "silence rarely wins",
      "current setup",
      "14-inch macbook pro with m5 pro",
      "dell s2725dc",
      "aula f75",
      "razer deathadder essential",
      "airpods pro 2",
      "zen",
      "zed",
      "ghostty + tmux",
      "herdr",
      "obsidian",
      "codex as primary, claude code as secondary",
    ):
      self.assertIn(marker, about)
    self.assertIn('<a href="/about/">about</a>', home)
    header = home[home.index('<header class="site-header">') : home.index("</header>")]
    self.assertIn(">writing</a>", header)
    self.assertIn(">about</a>", header)
    self.assertIn(">rss</a>", header)
    self.assertNotIn('rel="me"', header)
    self.assertIn('<aside class="rail rail--home" aria-label="elsewhere">', about)
    self.assertIn('rel="me">github</a>', about)
    self.assertIn("https://sarrthak.com/about/", locations)
    self.assertIn("[about](/about/)", llms)

  def test_real_articles_preserve_accessibility_and_image_stability(self) -> None:
    ocaml = self.output_dir.joinpath("blogs/learn_ocaml/index.html").read_text()
    randomness = self.output_dir.joinpath(
      "blogs/randomness_impl/index.html"
    ).read_text()

    self.assertIn(
      'more<span class="visually-hidden"> at cs3110.github.io</span>',
      ocaml,
    )
    self.assertRegex(
      randomness,
      r'<figure class="figure"><img src="/images/reddit-meme\.webp" alt="random number" loading="lazy" decoding="async" width="\d+" height="\d+"[^>]*/>',
    )
    self.assertNotIn("highlight.min.js", randomness)
    self.assertIn('class="k">', randomness)
    self.assertIn('<nav class="rail rail--article" aria-label="contents">', randomness)
    self.assertIn('<details class="rail__fold" open>', randomness)
    self.assertIn('<span class="blog-updated">updated', randomness)

  def test_legacy_writing_routes_redirect_to_the_blog_namespace(self) -> None:
    for slug in ("learn_ocaml", "make_cool_stuff", "randomness_impl"):
      redirect = self.output_dir.joinpath(f"writeups/{slug}/index.html").read_text()

      self.assertIn('http-equiv="refresh"', redirect)
      self.assertIn(f"url=/blogs/{slug}/", redirect)
      self.assertIn(
        f'rel="canonical" href="https://sarrthak.com/blogs/{slug}/"', redirect
      )
      self.assertIn(
        'rel="icon" href="/images/favicon.ico" type="image/x-icon"', redirect
      )

  def test_custom_404_uses_the_dedicated_minimal_layout(self) -> None:
    not_found = self.output_dir.joinpath("404.html").read_text()
    short_route = self.output_dir.joinpath("404/index.html").read_text()

    self.assertIn('<body class="not-found-page">', not_found)
    self.assertIn('<main class="not-found"', not_found)
    self.assertIn('<pre class="not-found-figlet" aria-hidden="true">', not_found)
    self.assertIn('<p class="not-found-code">404</p>', not_found)
    self.assertIn('<h1 class="not-found-heading"', not_found)
    self.assertIn('class="not-found-links"', not_found)
    self.assertIn('href="/">go home</a>', not_found)
    self.assertIn('href="/blogs/">all writings</a>', not_found)
    self.assertNotIn('class="writings-header"', not_found)
    self.assertNotIn('class="home-intro"', not_found)
    self.assertIn("url=/404.html", short_route)

  def test_feed_and_sitemap_use_the_shared_content_index(self) -> None:
    channel = ET.parse(self.output_dir / "feed.xml").getroot().find("channel")
    self.assertIsNotNone(channel)
    items = channel.findall("item")
    self.assertEqual(
      [item.findtext("title") for item in items],
      [
        "how to get #3 in amazon ml hackathon under 24 hrs w/ free compute",
        "make cool stuff",
        "why you should learn ocaml",
        "on randomness and its implementation",
      ],
    )

    locations = [
      element.text
      for element in ET.parse(self.output_dir / "sitemap.xml").getroot().iter()
      if element.tag.endswith("loc")
    ]
    self.assertEqual(
      locations,
      [
        "https://sarrthak.com/",
        "https://sarrthak.com/blogs/",
        "https://sarrthak.com/about/",
        "https://sarrthak.com/blogs/amazon_ml_hackathon/",
        "https://sarrthak.com/blogs/learn_ocaml/",
        "https://sarrthak.com/blogs/make_cool_stuff/",
        "https://sarrthak.com/blogs/randomness_impl/",
      ],
    )

  def test_repository_specific_static_files_and_article_measure_are_preserved(
    self,
  ) -> None:
    robots = self.output_dir.joinpath("robots.txt").read_text()
    llms = self.output_dir.joinpath("llms.txt").read_text()
    css = self.output_dir.joinpath("index.css").read_text()

    self.assertEqual(
      robots,
      "User-agent: *\nAllow: /\nSitemap: https://sarrthak.com/sitemap.xml\n",
    )
    self.assertEqual(self.output_dir.joinpath("CNAME").read_text(), "sarrthak.com\n")
    self.assertIn("# sλrthak", llms)
    self.assertIn("┏━┓┏━┓┏━┓", llms)
    self.assertIn("[all writings](/blogs/)", llms)
    self.assertTrue(self.output_dir.joinpath("site.js").is_file())
    self.assertRegex(css, r"\.blog-article p \{\s+max-width: 68ch;")
    self.assertIn('font-family: "IBM Plex Mono";', css)
    self.assertIn("/fonts/instrument-serif-400.woff2", css)
    self.assertIn("/fonts/jetbrains-mono-400.woff2", css)

  def test_home_listings_use_reflow_safe_grid_boundaries(self) -> None:
    css = self.output_dir.joinpath("index.css").read_text()
    home = self.output_dir.joinpath("index.html").read_text()

    self.assertIn('<div class="home-experience__header">', home)
    self.assertRegex(
      css,
      r"\.home-project__header,\s+\.home-experience__header \{[^}]+"
      r"grid-template-columns: minmax\(0, 1fr\) auto;",
    )
    self.assertRegex(
      css,
      r"\.home-project__header,\s+\.home-experience__header,\s+"
      r"\.home-experience__position \{[^}]+min-width: 0;",
    )
    self.assertRegex(
      css,
      r"\.home-project__description,\s+\.home-experience__description \{[^}]+"
      r"max-width: min\(64ch, 100%\);[^}]+overflow-wrap: anywhere;",
    )
    self.assertRegex(
      css,
      r"@media \(max-width: 760px\) \{[^}]+\.home-project__header,\s+"
      r"\.home-experience__header \{[^}]+grid-template-columns: 1fr;",
    )


if __name__ == "__main__":
  unittest.main()
