import html
import json
import re
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

  def test_real_site_renders_shared_metadata_and_every_post_on_home(self) -> None:
    home = self.output_dir.joinpath("index.html").read_text()
    article = self.output_dir.joinpath("blogs/learn_ocaml/index.html").read_text()
    not_found = self.output_dir.joinpath("404.html").read_text()

    for page in (home, article):
      self.assertIn('type="application/rss+xml"', page)
      self.assertIn('property="og:title"', page)
      self.assertIn('name="twitter:card" content="summary_large_image"', page)
      self.assertNotIn('href="/feed.xml">rss</a>', page)
      self.assertNotIn('href="/blogs/"', page)
    self.assertIn('href="mailto:hey@sarrthak.com"><svg class="logo"', home)
    self.assertNotIn('href="mailto:hey@sarrthak.com"><svg class="logo"', article)

    home_footer = home[
      home.index('<footer class="footer footer--plain">') : home.index("</footer>")
    ]
    self.assertIn("sarthak tomar. built with love.", home_footer)
    self.assertNotIn("data-city", home)
    for page in (article,):
      footer = page[
        page.index('<footer class="footer footer--city">') : page.index("</footer>")
      ]
      self.assertIn('<div class="city" aria-hidden="true" data-city', footer)
      self.assertIn(
        '<div class="city__layer city__layer--near" style="--rows: 18">', footer
      )
      self.assertIn('<div class="city__ships"></div>', footer)
      self.assertNotIn("<a ", footer)
      self.assertNotIn("<img", footer)
    self.assertIn('rel="canonical" href="https://sarrthak.com/"', home)
    self.assertIn('property="og:type" content="website"', home)
    self.assertIn(
      'property="og:image" content="https://sarrthak.com/images/social-card-cat.jpg"',
      home,
    )
    self.assertIn('property="og:image:width" content="1200"', home)
    self.assertIn('property="og:image:height" content="630"', home)
    self.assertIn('property="og:type" content="article"', article)
    self.assertIn('property="article:modified_time" content="2026-08-26"', article)
    self.assertIn('type="application/ld+json"', article)
    self.assertIn('name="robots" content="noindex, nofollow"', not_found)
    self.assertNotIn("all writings", home)
    self.assertIn('<a href="/">home</a>', article)
    self.assertIn(
      'class="home-projects-all" href="https://github.com/saarthak314">'
      "all projects</a>",
      home,
    )
    self.assertIn('href="https://www.math.inc">math.inc</a>', home)
    self.assertIn(
      '<img class="home-experience__logo" src="/images/logos/mathinc.png"', home
    )
    # the role runs straight into the company's mark, with no "@" between
    self.assertIn("<strong>systems engineer</strong> <img", home)
    self.assertNotIn("<span> @ </span>", home)
    self.assertIn('class="home-project__tech">python, agents</span>', home)
    self.assertLess(home.index(">kurama</a>"), home.index(">sakura</a>"))
    self.assertLess(home.index(">sakura</a>"), home.index(">web server</span>"))
    self.assertLess(home.index(">web server</span>"), home.index(">paimon</a>"))
    for removed_project in ("pixel editor", "redis clone", "rag pipeline", "cf-parser"):
      self.assertNotIn(removed_project, home)
    self.assertLess(home.index('id="experience"'), home.index('id="writing"'))
    self.assertLess(home.index('id="writing"'), home.index('id="projects"'))
    # with no archive page, home lists every post
    for slug in (
      "amazon_ml_hackathon",
      "make_cool_stuff",
      "learn_ocaml",
      "randomness_impl",
    ):
      self.assertIn(f'href="/blogs/{slug}/"', home)
    for published in ("oct 2026", "aug 2025", "jul 2025"):
      self.assertIn(f'<span class="writing-row__date">{published}</span>', home)

  def test_home_art_draws_only_from_the_preloaded_symbol_font(self) -> None:
    from fontTools.ttLib import TTFont

    home = self.output_dir.joinpath("index.html").read_text()
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    with TTFont(
      str(PROJECT_ROOT / "static" / "fonts" / "jetbrains-mono-symbols.woff2")
    ) as font:
      cmap = font.getBestCmap()
    article = self.output_dir.joinpath("blogs/learn_ocaml/index.html").read_text()
    city = re.search(r'<div class="city".*?</footer>', article, re.S).group(0)
    # the city's pictures set glyphs in SVG text; the cat is dots, no glyphs
    glyphs = "".join(re.findall(r"<text[^>]*>(.*?)</text>", city, re.S))
    glyphs += "".join(re.findall(r'data-glyph="([^"]*)"', city))
    drawn = set(html.unescape(re.sub(r"<[^>]+>", "", glyphs))) - {"\n"}
    drawn |= {"λ"}
    cat = re.search(r'<svg class="cat".*?</svg>', home, re.S).group(0)
    self.assertEqual(re.sub(r"<[^>]+>", "", cat), "")

    self.assertEqual(sorted(c for c in drawn if ord(c) not in cmap), [])
    self.assertIn('--art: "JBM Symbols", "JetBrains Mono"', stylesheet)
    self.assertIn(
      '<link rel="preload" href="/fonts/jetbrains-mono-symbols.woff2"', home
    )

  def test_the_sky_twinkles_without_any_script(self) -> None:
    home = self.output_dir.joinpath("index.html").read_text()
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    script = PROJECT_ROOT.joinpath("static", "site.js").read_text()
    art = re.search(r'<svg class="cat" viewBox="0 0 (\d+) (\d+)"', home)
    stars = re.search(
      r'<span class="cat-stars" aria-hidden="true" style="--cols: (\d+); '
      r'--rows: (\d+)">(.*?)</span>',
      home,
      re.S,
    )

    # the star layer sits on the art's grid, as small dots, not text
    self.assertEqual(stars.group(1, 2), art.group(1, 2))
    self.assertGreaterEqual(stars.group(3).count("<i "), 20)
    self.assertRegex(
      stars.group(3), r'<i class="s[1-6]( hi)?" style="--x: \d+; --y: \d+"></i>'
    )
    self.assertEqual(re.sub(r"<[^>]+>", "", stars.group(3)), "")
    self.assertIn('<span class="meteor" aria-hidden="true"></span>', home)
    self.assertIn("@keyframes cat-twinkle", stylesheet)
    self.assertIn("@keyframes meteor", stylesheet)
    self.assertIn(".banner--still .cat-stars i", stylesheet)
    self.assertIn(
      'banner.classList.toggle("banner--still", !entry.isIntersecting)', script
    )

  def test_the_player_spectrum_moves_only_while_a_track_plays_on_screen(self) -> None:
    script = PROJECT_ROOT.joinpath("static", "site.js").read_text()
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()

    # drawn on a small canvas in the cat's two dot sizes and its colours
    self.assertIn('viz.querySelector("canvas")', script)
    self.assertIn("pen.arc(x, y, r, 0, Math.PI * 2)", script)
    self.assertIn("(big ? 0.3 : 0.205) * cell * scale", script)
    viz = re.search(r"\n\.now__viz \{[^}]*\}", stylesheet).group(0)
    for colour in (
      "--bar: var(--accent-2)",
      "--peak: var(--warm)",
      "--rest: var(--ink-4)",
    ):
      self.assertIn(colour, viz)
    self.assertIn("contain: strict", viz)
    self.assertNotIn("textContent = lines", script)
    # it runs only while the block is on screen, the tab is open, and a track
    # plays (or the bars are still settling); reduced motion gets one still frame
    self.assertRegex(
      script,
      r"const moving = \(\) =>\s*visible && !document\.hidden && "
      r"\(box\.classList\.contains\(\"now--playing\"\) \|\| caps\.some",
    )
    self.assertIn('window.matchMedia("(prefers-reduced-motion: reduce)")', script)
    self.assertIn("step(true);", script)
    self.assertNotIn("requestAnimationFrame(animate", script)
    # the reserved space sits on the slot, never as empty room inside the frame
    frame = re.search(r"\n\.now \{[^}]*\}", stylesheet).group(0)
    self.assertNotIn("min-height", frame)
    self.assertIn(".now-slot:has(.now--off)", stylesheet)

  def test_audit_holds_colour_overflow_glyph_and_label_rules(self) -> None:
    from fontTools.ttLib import TTFont

    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    code = PROJECT_ROOT.joinpath("static", "code.css").read_text()
    home = self.output_dir.joinpath("index.html").read_text()

    # every colour goes through a token: no literal past the :root block
    body = stylesheet[stylesheet.index(":root {") :]
    body = body[body.index("}") + 1 :]
    for sheet in (body, code):
      self.assertNotRegex(sheet, r"#[0-9a-fA-F]{3,8}\b|rgba?\(")
    # full-bleed without 100vw; sideways overflow clipped on html and body
    self.assertNotIn("100vw;", stylesheet)
    self.assertNotIn("50vw", stylesheet)
    self.assertRegex(stylesheet, r"\nbody \{[^}]*overflow-x: clip;")
    self.assertRegex(stylesheet, r"\nhtml \{[^}]*overflow-x: clip;")
    # no tracked small labels and no gradient text in the player
    self.assertNotIn("letter-spacing: 0.04em", stylesheet)
    self.assertNotIn("background-clip", stylesheet)
    # the disc is a glyph the preloaded subset really has, so the page never
    # reaches for the full code font or a system fallback
    with TTFont(
      PROJECT_ROOT.joinpath("static", "fonts", "jetbrains-mono-symbols.woff2")
    ) as font:
      symbols = font.getBestCmap()
    for escape in re.findall(r'content: "\\(25[0-9A-Fa-f]{2})"', stylesheet):
      self.assertIn(int(escape, 16), symbols, escape)
    self.assertNotIn("\\25D0", stylesheet)
    # tags read as a list, not a middle-dot meta string
    self.assertNotIn(" · ", home)
    # decorative marks are silent to screen readers
    self.assertIn('content: "##" / "";', stylesheet)
    self.assertIn('content: "-" / "";', stylesheet)

  def test_banner_wave_loads_only_when_a_mouse_or_a_finger_arrives(self) -> None:
    home = self.output_dir.joinpath("index.html").read_text()
    script = PROJECT_ROOT.joinpath("static", "site.js").read_text()
    hover = self.output_dir.joinpath("cat.js").read_text()

    self.assertNotIn("cat.js", home)
    # a real mouse move loads it, and so does a touch; the page scrolling under
    # a resting cursor does not
    self.assertIn(
      'banner.addEventListener("pointermove", wake, { passive: true })', script
    )
    self.assertIn(
      'banner.addEventListener("pointerdown", wake, { passive: true })', script
    )
    self.assertIn("event.movementX || event.movementY", script)
    self.assertIn('import("/cat.js")', script)
    self.assertNotIn("pointer: fine", script)
    self.assertIn("prefers-reduced-motion: no-preference", script)
    self.assertIn("export function start", hover)
    self.assertIn("requestAnimationFrame", hover)
    # one simple wave that follows the cursor or the finger
    self.assertIn("centre", hover)
    self.assertIn("Math.sin", hover)
    self.assertNotIn("Math.cos", hover)
    self.assertRegex(hover, r"move\.screenX\s*!==\s*screen\.x")
    self.assertIn("pointerdown", hover)
    self.assertIn("pointercancel", hover)
    self.assertNotIn("click", hover)
    # the canvas takes each dot's size from the stylesheet, which phones enlarge
    self.assertIn("strokeWidth", hover)
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    banner = re.search(r"\n\.banner \{[^}]*\}", stylesheet).group(0)
    self.assertNotIn("mask-image", banner)
    # vertical drags on the banner still scroll the page, and pinching zooms
    self.assertIn("touch-action: pan-y pinch-zoom", banner)

  def test_shipped_script_and_stylesheet_are_minified_copies(self) -> None:
    script = self.output_dir.joinpath("site.js").read_text()
    stylesheet = self.output_dir.joinpath("index.css").read_text()
    source_script = PROJECT_ROOT.joinpath("static", "site.js").read_text()
    source_stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()

    self.assertLess(len(script), len(source_script) * 0.8)
    self.assertLess(len(stylesheet), len(source_stylesheet) * 0.9)
    self.assertIn("data-now", script)
    self.assertIn("ship--left", script)
    self.assertIn(".city__ships", stylesheet)
    self.assertNotIn("hexpatch", script + stylesheet)
    self.assertNotIn("Each ship is one CSS transform animation", script)
    self.assertNotIn("/* ledger */", stylesheet)

  def test_social_links_read_as_one_balanced_line_of_text(self) -> None:
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    links = re.search(r"\n\.socials a \{[^}]*\}", stylesheet).group(0)
    items = re.search(r"\n\.socials li \{[^}]*\}", stylesheet).group(0)
    block = re.search(r"\n\.socials \{[^}]*\}", stylesheet).group(0)

    self.assertNotIn("underline", links)
    home_links = re.search(r"\n\.home a \{[^}]*\}", stylesheet).group(0)
    self.assertIn("text-decoration: none", home_links)
    self.assertIn(
      "color: var(--accent)",
      re.search(r"\n\.home a:hover \{[^}]*\}", stylesheet).group(0),
    )
    self.assertIn("display: inline", items)
    self.assertIn("white-space: nowrap", items)
    self.assertIn("text-wrap: balance", block)
    # no "/" between the links; the logos set them apart
    self.assertNotIn('content: " /"', stylesheet)
    self.assertRegex(
      stylesheet, r"\.socials li:not\(:last-child\) \{\s*margin-right: 1rem;"
    )
    # the spotify block is last in the page itself, so no width reorders it
    self.assertNotRegex(stylesheet, r"\.now-slot \{[^}]*(?<![-\w])order:")

  def test_about_route_redirects_home_and_the_header_drops_it(self) -> None:
    redirect = self.output_dir.joinpath("about/index.html").read_text()
    home = self.output_dir.joinpath("index.html").read_text()
    llms = self.output_dir.joinpath("llms.txt").read_text()
    locations = [
      element.text
      for element in ET.parse(self.output_dir / "sitemap.xml").getroot().iter()
      if element.tag.endswith("loc")
    ]

    self.assertIn('<meta http-equiv="refresh" content="0; url=/" />', redirect)
    self.assertIn('<meta name="robots" content="noindex, follow" />', redirect)
    header = home[home.index('<header class="site-header">') : home.index("</header>")]
    self.assertNotIn("<nav", header)
    self.assertNotIn(">writing</a>", header)
    self.assertNotIn(">rss</a>", header)
    self.assertNotIn("/about/", header)
    self.assertNotIn('rel="me"', header)
    self.assertIn('<ul class="socials" aria-label="elsewhere">', home)
    self.assertIn('rel="me"><svg class="logo"', home)
    self.assertIn("</svg>github</a>", home)
    self.assertNotIn('class="city" aria-hidden="true" data-city', home)
    for removed in (
      "page--annotated",
      "portrait-bracket",
      "rail__tag",
      "rail__stamp",
      "rail__readout",
      "city--panic",
      'class="glitch',
    ):
      self.assertNotIn(removed, home)
    self.assertNotIn("https://sarrthak.com/about/", locations)
    self.assertNotIn("/about/", llms)

  def test_writing_page_is_gone_and_its_address_redirects_home(self) -> None:
    redirect = self.output_dir.joinpath("blogs/index.html").read_text()
    llms = self.output_dir.joinpath("llms.txt").read_text()
    script = self.output_dir.joinpath("site.js").read_text()
    stylesheet = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    locations = [
      element.text
      for element in ET.parse(self.output_dir / "sitemap.xml").getroot().iter()
      if element.tag.endswith("loc")
    ]

    self.assertIn('<meta http-equiv="refresh" content="0; url=/" />', redirect)
    self.assertIn('<meta name="robots" content="noindex, follow" />', redirect)
    self.assertFalse(self.output_dir.joinpath("blogs/page").exists())
    self.assertFalse(PROJECT_ROOT.joinpath("templates", "writings.html").exists())
    self.assertFalse(PROJECT_ROOT.joinpath("content", "blogs", "_index.md").exists())
    self.assertNotIn("https://sarrthak.com/blogs/", locations)
    self.assertNotIn("(/blogs/)", llms)
    self.assertNotIn('"/blogs/"', script)
    for removed in (".site-nav", ".writings-", ".pagination", ".home-writing-all"):
      self.assertNotIn(removed, stylesheet)
    for page in self.output_dir.rglob("*.html"):
      if page.name == "index.html" and page.parent.name == "blogs":
        continue
      self.assertNotIn('href="/blogs/"', page.read_text(), page)

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
      r'<figure class="figure"><img src="/images/reddit-meme\.webp" alt="random number" loading="eager" fetchpriority="high" decoding="async" width="\d+" height="\d+"[^>]*/>',
    )
    self.assertNotIn("highlight.min.js", randomness)
    self.assertIn('class="k">', randomness)
    self.assertIn('<nav class="rail rail--article" aria-label="contents">', randomness)
    self.assertIn('<details class="rail__fold" open>', randomness)
    self.assertIn('<span class="blog-updated">updated', randomness)

  def test_drafts_publish_with_a_notice_but_stay_out_of_feed_and_sitemap(self) -> None:
    draft_dir = self.project_root / "content" / "blogs" / "wip"
    draft_dir.mkdir()
    draft_dir.joinpath("index.md").write_text(
      "title: wip\ndate: 2026-10-09\ndraft: true\n-----\nstill writing."
    )
    output_dir = (
      SiteBuilder(self.project_root).build(BuildOptions(incremental=False)).output_dir
    )
    draft = output_dir.joinpath("blogs/wip/index.html").read_text()
    home = output_dir.joinpath("index.html").read_text()
    feed = output_dir.joinpath("feed.xml").read_text()
    sitemap = output_dir.joinpath("sitemap.xml").read_text()

    self.assertIn('<p class="blog-draft" role="note">', draft)
    self.assertIn('name="robots" content="noindex, nofollow"', draft)
    self.assertIn('<span class="writing-row__draft">draft</span>', home)
    self.assertNotIn("/blogs/wip/", feed)
    self.assertNotIn("/blogs/wip/", sitemap)

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
    self.assertNotIn("all writings", not_found)
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
        "winning #3 in amazon ml challenge",
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
    # the shipped stylesheet is minified; the rules are checked in the source
    css = PROJECT_ROOT.joinpath("static", "index.css").read_text()

    self.assertEqual(
      robots,
      "User-agent: *\nAllow: /\nSitemap: https://sarrthak.com/sitemap.xml\n",
    )
    self.assertEqual(self.output_dir.joinpath("CNAME").read_text(), "sarrthak.com\n")
    self.assertIn("# sλrthak", llms)
    self.assertIn("┏━┓┏━┓┏━┓", llms)
    self.assertNotIn("all writings", llms)
    self.assertTrue(self.output_dir.joinpath("site.js").is_file())
    self.assertRegex(css, r"\.blog-article p \{\s+max-width: 68ch;")
    self.assertIn('font-family: "IBM Plex Mono";', css)
    self.assertIn("/fonts/instrument-serif-400.woff2", css)
    self.assertIn("/fonts/jetbrains-mono-400.woff2", css)

  def test_home_listings_use_reflow_safe_grid_boundaries(self) -> None:
    css = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    home = self.output_dir.joinpath("index.html").read_text()

    self.assertIn('<div class="home-experience__header">', home)
    self.assertRegex(
      css,
      r"\n\.home-experience__header \{[^}]+"
      r"grid-template-columns: minmax\(0, 1fr\) auto;",
    )
    self.assertRegex(
      css,
      r"\.home-experience__header,\s+"
      r"\.home-experience__position \{[^}]+min-width: 0;",
    )
    self.assertRegex(
      css,
      r"\n\.home-experience__description \{[^}]+"
      r"max-width: min\(64ch, 100%\);[^}]+overflow-wrap: anywhere;",
    )
    self.assertRegex(
      css,
      r"@media \(max-width: 760px\) \{[^}]+"
      r"\.home-experience__header \{[^}]+grid-template-columns: 1fr;",
    )

  def test_projects_are_set_like_the_writing_list(self) -> None:
    css = PROJECT_ROOT.joinpath("static", "index.css").read_text()
    home = self.output_dir.joinpath("index.html").read_text()
    projects = home[home.index('<ul class="home-project-list">') :]
    projects = projects[: projects.index("</ul>")]

    self.assertNotIn("home-project__header", projects)
    self.assertIn('<p class="home-project__description">', projects)
    for shared in (
      r"\.writing-row,\s+\.home-project \{[^}]+grid-template-areas:",
      r"\.writing-row__meta,\s+\.home-project__tech \{",
      r"\.writing-row__title,\s+\.home-project__name \{",
      r"\.writing-row__summary,\s+\.home-project__description \{",
    ):
      self.assertRegex(css, shared)


if __name__ == "__main__":
  unittest.main()
