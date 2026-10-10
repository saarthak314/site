import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from jinja2 import FileSystemLoader, StrictUndefined, UndefinedError

from sitegen.render import TemplateRenderer
from sitegen.templates import create_environment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = PROJECT_ROOT / "templates"


def namespace(**values: object) -> SimpleNamespace:
  return SimpleNamespace(**values)


def rendered(
  html: str = "",
  *,
  reading_time: str = "1 min read",
  has_math: bool = False,
  has_code: bool = False,
  headings: tuple[tuple[int, str, str], ...] = (),
) -> SimpleNamespace:
  return namespace(
    html=html,
    reading_time=reading_time,
    has_math=has_math,
    has_code=has_code,
    headings=headings,
  )


def page(
  *,
  title: str,
  route: str,
  template: str,
  published: date = date(2026, 8, 24),
  updated: date | None = None,
  description: str = "systems notes",
  social_image_url: str = "https://sarrthak.com/images/social.png",
  social_image_width: int = 1200,
  social_image_height: int = 630,
  social_image_type: str = "image/png",
  noindex: bool = False,
  draft: bool = False,
  tags: tuple[str, ...] = (),
  experience: tuple[SimpleNamespace, ...] = (),
  projects: tuple[SimpleNamespace, ...] = (),
  body: SimpleNamespace | None = None,
) -> SimpleNamespace:
  return namespace(
    title=title,
    date=published,
    updated=updated,
    route=route,
    canonical_url=f"https://sarrthak.com{route}",
    description=description,
    social_image_url=social_image_url,
    social_image_width=social_image_width,
    social_image_height=social_image_height,
    social_image_type=social_image_type,
    noindex=noindex,
    draft=draft,
    tags=tags,
    experience=experience,
    projects=projects,
    rendered=body or rendered(),
    template=template,
  )


def config() -> SimpleNamespace:
  return namespace(
    site_url="https://sarrthak.com",
    email="hey@sarrthak.com",
    social_image="/images/social.png",
    author_name="Sarthak Tomar",
    twitter_handle="@sarthak2143",
  )


def pagination_context(
  items: tuple[SimpleNamespace, ...],
  *,
  page_number: int = 2,
  total_pages: int = 3,
  previous_url: str | None = "/blogs/",
  next_url: str | None = "/blogs/page/3/",
  **extra: object,
) -> SimpleNamespace:
  return namespace(
    config=config(),
    items=items,
    page=page_number,
    total_pages=total_pages,
    previous_url=previous_url,
    next_url=next_url,
    **extra,
  )


class TemplateRenderingTestCase(unittest.TestCase):
  def setUp(self) -> None:
    self.environment = create_environment(TEMPLATE_ROOT)
    self.renderer = TemplateRenderer(self.environment)

  def render(self, target: SimpleNamespace, context: SimpleNamespace) -> str:
    return self.renderer.render_page(target, context)


class TestTemplateEnvironment(unittest.TestCase):
  def test_environment_loads_files_strictly_and_autoescapes_html(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      template_dir = Path(temp_dir)
      template_dir.joinpath("escaped.html").write_text("{{ value }}", encoding="utf-8")
      template_dir.joinpath("plain.txt").write_text("{{ value }}", encoding="utf-8")

      environment = create_environment(template_dir)

      self.assertIsInstance(environment.loader, FileSystemLoader)
      self.assertIs(environment.undefined, StrictUndefined)
      self.assertEqual(
        environment.get_template("escaped.html").render(value="<unsafe>"),
        "&lt;unsafe&gt;",
      )
      self.assertEqual(
        environment.get_template("plain.txt").render(value="<unsafe>"),
        "<unsafe>",
      )
      with self.assertRaises(UndefinedError):
        environment.get_template("escaped.html").render()

  def test_renderer_supports_build_facing_construction_and_archives(self) -> None:
    from sitegen.templates import TemplateRenderer as BuildTemplateRenderer

    site_config = namespace(
      template_dir=TEMPLATE_ROOT,
      site_url="https://sarrthak.com",
      email="hey@sarrthak.com",
      social_image="/images/social.png",
      author_name="Sarthak Tomar",
      twitter_handle="@sarthak2143",
    )
    renderer = BuildTemplateRenderer(site_config)
    post = page(
      title="systems post",
      route="/blogs/systems/",
      template="blog.html",
      tags=("systems",),
    )
    index = namespace(posts=(post,), recent_posts=(post,))
    home = page(title="home", route="/", template="home.html")
    archive = page(title="all writings", route="/blogs/", template="writings.html")
    pagination = namespace(
      items=(post,),
      page=1,
      total_pages=1,
      route="/blogs/",
      previous_url=None,
      next_url=None,
    )
    tag = namespace(
      name="systems",
      slug="systems",
      route="/tags/systems/",
      items=(post,),
    )

    self.assertIn("systems post", renderer.render_page(home, index))
    self.assertIn("systems post", renderer.render_archive(archive, pagination, index))
    self.assertIn("systems post", renderer.render_tag(tag, index))
    self.assertTrue(renderer.template_digest("home.html"))


class TestSharedLayout(TemplateRenderingTestCase):
  def test_rendered_pages_do_not_contain_trailing_whitespace(self) -> None:
    home = page(
      title="home",
      route="/",
      template="home.html",
      body=rendered("<p>hello.</p>"),
    )
    context = namespace(
      config=config(),
      index=namespace(posts=(), recent_posts=()),
    )

    html = self.render(home, context)

    self.assertTrue(all(line == line.rstrip() for line in html.splitlines()))

  def test_shared_layout_preserves_metadata_navigation_and_footer(self) -> None:
    home = page(
      title="sλrthak · systems, models, machines",
      route="/",
      template="home.html",
      description="systems, models, and machines",
      body=rendered("<p>hello.</p>"),
    )
    context = namespace(
      config=config(),
      index=namespace(posts=(), recent_posts=()),
    )

    html = self.render(home, context)

    self.assertIn("<title>sλrthak · systems, models, machines</title>", html)
    self.assertIn('<link rel="canonical" href="https://sarrthak.com/"', html)
    self.assertIn('<meta property="og:type" content="website"', html)
    self.assertIn('<meta property="og:site_name" content="sλrthak"', html)
    self.assertIn('<meta property="og:url" content="https://sarrthak.com/"', html)
    self.assertIn(
      '<meta property="og:image" content="https://sarrthak.com/images/social.png"',
      html,
    )
    self.assertIn('<meta property="og:image:width" content="1200"', html)
    self.assertIn('<meta property="og:image:height" content="630"', html)
    self.assertIn('<meta property="og:image:type" content="image/png"', html)
    self.assertIn('<meta name="twitter:card" content="summary_large_image"', html)
    self.assertIn('<meta name="twitter:creator" content="@sarthak2143"', html)
    self.assertIn('"@type": "Person"', html)
    self.assertIn('"name": "Sarthak Tomar"', html)
    self.assertIn('<link rel="describedby" href="/llms.txt"', html)
    self.assertIn('type="application/rss+xml"', html)
    self.assertIn('href="/feed.xml"', html)
    self.assertIn('<body class="home-page">', html)
    self.assertIn('<a class="skip-link" href="#main-content">skip to content</a>', html)
    self.assertIn(
      '<a class="site-title" href="/">s<span class="lam">λ</span>rthak</a>', html
    )
    self.assertIn('<span class="site-name">sarthak tomar</span>', html)
    self.assertIn('<script defer src="/site.js"></script>', html)

    header = html[html.index('<header class="site-header">') : html.index("</header>")]
    self.assertIn('<a href="/blogs/">writing</a>', header)
    self.assertIn('<a href="/about/">about</a>', header)
    self.assertIn('<a href="/feed.xml">rss</a>', header)
    self.assertEqual(header.count("<a "), 4)
    self.assertNotIn('rel="me"', header)

    rail_start = html.index('<aside class="rail rail--home" aria-label="elsewhere">')
    rail = html[rail_start : html.index("</aside>", rail_start)]
    self.assertIn('href="https://github.com/saarthak314" rel="me">github</a>', rail)
    self.assertIn('href="https://x.com/sarthak2143" rel="me">twitter</a>', rail)
    self.assertIn(
      'href="https://linkedin.com/in/sarthaktomar2143" rel="me">linkedin</a>',
      rail,
    )
    self.assertIn(
      'href="https://discord.com/users/1226399791362080820" rel="me">discord</a>',
      rail,
    )
    self.assertIn('href="mailto:hey@sarrthak.com">email</a>', rail)

    footer = html[
      html.index('<footer class="footer footer--city">') : html.index("</footer>")
    ]
    self.assertRegex(footer, r"© \d{4} sarthak tomar\. built with love\.")
    self.assertIn('<div class="city" aria-hidden="true" data-city', footer)
    self.assertIn('<pre class="city__layer city__layer--far">', footer)
    self.assertIn('<div class="city__ships"></div>', footer)
    self.assertIn('<pre class="city__layer city__layer--near">', footer)
    self.assertNotIn("<a ", footer)
    self.assertNotIn("<img", footer)
    self.assertNotIn('aria-label="Footer navigation"', html)

  def test_ordinary_strings_escape_while_markdown_html_remains_safe(self) -> None:
    article = page(
      title="templates <script>alert(1)</script>",
      route="/blogs/templates/",
      template="blog.html",
      description='notes about <templates> & "escaping"',
      tags=("systems",),
      body=rendered("<p><em>trusted markdown</em></p>"),
    )

    html = self.render(article, namespace(config=config()))

    self.assertIn("templates &lt;script&gt;alert(1)&lt;/script&gt;", html)
    self.assertNotIn("templates <script>alert(1)</script>", html)
    self.assertIn(
      "notes about &lt;templates&gt; &amp; &#34;escaping&#34;",
      html,
    )
    self.assertIn("<p><em>trusted markdown</em></p>", html)
    self.assertNotIn("&lt;p&gt;&lt;em&gt;trusted markdown", html)

  def test_math_and_code_assets_follow_rendered_markdown_flags(self) -> None:
    plain_article = page(
      title="plain article",
      route="/blogs/plain/",
      template="blog.html",
      body=rendered("<p>plain.</p>"),
    )
    rich_article = page(
      title="rich article",
      route="/blogs/rich/",
      template="blog.html",
      body=rendered(
        "<p>rich.</p>",
        has_math=True,
        has_code=True,
      ),
    )

    plain_html = self.render(plain_article, namespace(config=config()))
    rich_html = self.render(rich_article, namespace(config=config()))

    self.assertNotIn("mathjax@3.2.2/es5/tex-chtml.js", plain_html)
    self.assertNotIn("highlight.min.js", plain_html)
    self.assertNotIn("/code.css", plain_html)
    self.assertIn("mathjax@3.2.2/es5/tex-chtml.js", rich_html)
    self.assertIn(
      'integrity="sha384-AHAnt9ZhGeHIrydA1Kp1L7FN+2UosbF7RQg6C+9Is/a7kDpQ1684C2iH2VWil6r4"',
      rich_html,
    )
    self.assertIn('crossorigin="anonymous"', rich_html)
    self.assertNotIn("highlight.min.js", rich_html)
    self.assertIn("/code.css", rich_html)

  def test_article_metadata_includes_updates_and_blog_posting_schema(self) -> None:
    article = page(
      title="updated article",
      route="/blogs/updated/",
      template="blog.html",
      published=date(2025, 7, 19),
      updated=date(2026, 8, 26),
    )

    html = self.render(article, namespace(config=config()))

    updated = (
      '<span class="blog-updated">updated '
      '<time datetime="2026-08-26">26 aug 2026</time></span>'
    )
    meta_start = html.index('<p class="blog-meta">')
    metadata = html[meta_start : html.index("</p>", meta_start)]
    self.assertIn(updated, metadata)
    self.assertLess(html.index(updated), html.index("</article>"))
    self.assertIn('"@type": "BlogPosting"', html)
    self.assertIn('"datePublished": "2025-07-19"', html)
    self.assertIn('"dateModified": "2026-08-26"', html)

  def test_noindex_pages_emit_robots_metadata(self) -> None:
    not_found = page(
      title="not found",
      route="/404.html",
      template="404.html",
      noindex=True,
    )

    html = self.render(not_found, namespace(config=config()))

    self.assertIn('<meta name="robots" content="noindex, nofollow"', html)

  def test_template_digest_tracks_every_template_file(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      template_dir = Path(temp_dir)
      partials = template_dir / "partials"
      partials.mkdir()
      template_dir.joinpath("home.html").write_text("home")
      template_dir.joinpath("base.html").write_text("base")
      partials.joinpath("header.html").write_text("header")
      partials.joinpath("footer.html").write_text("footer")
      partials.joinpath("extra.html").write_text("first")
      renderer = TemplateRenderer(create_environment(template_dir))

      first = renderer.template_digest("home.html")
      partials.joinpath("extra.html").write_text("second")
      second = renderer.template_digest("home.html")

    self.assertNotEqual(first, second)


class TestHomeTemplate(TemplateRenderingTestCase):
  def test_home_renders_intro_recent_posts_and_archive_link(self) -> None:
    recent = page(
      title="recent post",
      route="/blogs/recent/",
      template="blog.html",
      published=date(2026, 8, 24),
    )
    older = page(
      title="older post",
      route="/blogs/older/",
      template="blog.html",
      published=date(2025, 7, 19),
    )
    home = page(
      title="sλrthak · systems, models, machines",
      route="/",
      template="home.html",
      body=rendered("<p>trusted <strong>intro</strong>.</p>"),
      experience=(
        namespace(
          role="systems engineer",
          company="morph labs",
          company_url="https://morph.so",
          period="jun 2026 to present",
          highlights=("agentic workflows and cloud inference systems",),
        ),
      ),
      projects=(
        namespace(
          name="paimon",
          url="https://github.com/saarthak314/paimon",
          description="an agentic coding harness",
          tech=("python", "agents"),
        ),
        namespace(
          name="web server",
          url=None,
          description="nginx-style web server",
          tech=("c", "networking"),
        ),
      ),
    )
    context = namespace(
      config=config(),
      index=namespace(posts=(recent, older), recent_posts=(recent,)),
    )

    html = self.render(home, context)

    self.assertIn(
      '<article class="home-intro"><p>trusted <strong>intro</strong>.</p></article>',
      html,
    )
    self.assertIn('<ul class="writing-list">', html)
    self.assertIn('<li class="writing-row">', html)
    self.assertIn('<span class="writing-row__date">aug 2026</span>', html)
    self.assertIn('<span class="writing-row__mark"><svg class="mark"', html)
    self.assertIn(
      '<a class="writing-row__title" href="/blogs/recent/">recent post</a>',
      html,
    )
    self.assertIn('<span class="writing-row__time">1 min read</span>', html)
    self.assertNotIn("older post", html)
    self.assertIn(
      '<pre class="portrait" role="img" aria-label="ascii portrait of asuka langley soryu, chin on her hand, unimpressed"',
      html,
    )
    self.assertIn('<a class="home-writing-all" href="/blogs/">all writings</a>', html)
    self.assertIn('<section class="home-projects" id="projects"', html)
    self.assertIn('class="home-project__tech">python · agents</span>', html)
    self.assertIn('<span class="home-project__name">web server</span>', html)
    self.assertNotIn('href="None">web server</a>', html)
    self.assertIn(
      '<a class="home-projects-all" href="https://github.com/saarthak314">'
      "all projects</a>",
      html,
    )
    projects_start = html.index('<section class="home-projects"')
    projects_end = html.index("</section>", projects_start)
    all_projects = html.index('class="home-projects-all"')
    self.assertLess(projects_start, all_projects)
    self.assertLess(all_projects, projects_end)
    self.assertIn('<section class="home-experience" id="experience"', html)
    self.assertIn('<div class="home-experience__header">', html)
    self.assertIn(
      '<a class="home-experience__company" href="https://morph.so">morph labs</a>',
      html,
    )
    self.assertIn(
      '<span class="home-experience__period">jun 2026 to present</span>',
      html,
    )
    self.assertIn(
      '<span class="home-experience__description">'
      "agentic workflows and cloud inference systems</span>",
      html,
    )
    self.assertNotIn("home-experience__highlights", html)
    self.assertLess(html.index('id="experience"'), html.index('id="writing"'))
    self.assertLess(html.index('id="writing"'), html.index('id="projects"'))


class TestWritingsTemplate(TemplateRenderingTestCase):
  def test_writings_renders_full_dates_and_pagination(self) -> None:
    first = page(
      title="first post",
      route="/blogs/first/",
      template="blog.html",
      published=date(2026, 8, 24),
    )
    second = page(
      title="second post",
      route="/blogs/second/",
      template="blog.html",
      published=date(2026, 7, 3),
    )
    archive = page(
      title="all writings",
      route="/blogs/page/2/",
      template="writings.html",
    )

    html = self.render(archive, pagination_context((first, second)))

    self.assertIn('<body class="writings-page">', html)
    self.assertIn('<h1 class="writings-heading">all writings</h1>', html)
    self.assertNotIn("everything i've written", html)
    self.assertIn('<p class="writing-row__summary">systems notes</p>', html)
    self.assertIn('<h2 class="writings-year__heading" id="year-2026">2026</h2>', html)
    self.assertIn('<span class="writing-row__date">24 aug</span>', html)
    self.assertIn('href="/blogs/first/">first post</a>', html)
    self.assertIn('<span class="writing-row__date">03 jul</span>', html)
    self.assertIn('href="/blogs/second/">second post</a>', html)
    self.assertIn('<nav class="pagination" aria-label="Pagination">', html)
    self.assertIn('rel="prev" href="/blogs/">previous</a>', html)
    self.assertIn("<span>page 2 of 3</span>", html)
    self.assertIn('rel="next" href="/blogs/page/3/">next</a>', html)
    self.assertNotIn('class="tree"', html)

  def test_writings_groups_years_newest_first(self) -> None:
    newer = page(
      title="newer post",
      route="/blogs/newer/",
      template="blog.html",
      published=date(2026, 3, 1),
    )
    older = page(
      title="older post",
      route="/blogs/older/",
      template="blog.html",
      published=date(2025, 7, 19),
    )
    archive = page(
      title="all writings",
      route="/blogs/",
      template="writings.html",
    )
    context = pagination_context(
      (newer, older),
      page_number=1,
      total_pages=1,
      previous_url=None,
      next_url=None,
      index=namespace(posts=(newer, older), recent_posts=(newer,)),
    )

    html = self.render(archive, context)

    self.assertIn('<h2 class="writings-year__heading" id="year-2026">2026</h2>', html)
    self.assertIn('<h2 class="writings-year__heading" id="year-2025">2025</h2>', html)
    self.assertLess(html.index('id="year-2026"'), html.index('id="year-2025"'))
    self.assertNotIn('aria-label="Pagination"', html)

    self.assertNotIn('class="tree"', html)


class TestBlogTemplate(TemplateRenderingTestCase):
  def test_blog_renders_article_metadata_content_and_tags(self) -> None:
    article = page(
      title="strict templates",
      route="/blogs/strict-templates/",
      template="blog.html",
      published=date(2026, 8, 24),
      updated=date(2026, 8, 25),
      description="strict rendering without surprises",
      social_image_url="https://sarrthak.com/images/templates.png",
      tags=("systems", "inference"),
      body=rendered(
        '<p id="trusted">rendered <code>markdown</code>.</p>',
        reading_time="4 min read",
      ),
    )

    html = self.render(article, namespace(config=config()))

    self.assertIn('<body class="blog-page">', html)
    self.assertIn("<title>strict templates · sλrthak</title>", html)
    self.assertIn('<meta property="og:type" content="article"', html)
    self.assertIn('<meta property="article:published_time" content="2026-08-24"', html)
    self.assertIn('<meta property="article:modified_time" content="2026-08-25"', html)
    self.assertIn(
      '<meta name="twitter:description" content="strict rendering without surprises"',
      html,
    )
    self.assertIn(
      '<meta name="twitter:image" content="https://sarrthak.com/images/templates.png"',
      html,
    )
    self.assertIn('<a class="rail__back" href="/blogs/">&lt;- writing</a>', html)
    self.assertNotIn('class="blog-back"', html)
    self.assertIn(
      '<time class="blog-date" datetime="2026-08-24">24 aug 2026</time>', html
    )
    self.assertIn('<span class="blog-reading-time">4 min read</span>', html)
    self.assertIn('<h1 class="blog-heading">strict templates</h1>', html)
    self.assertIn('<p class="blog-deck">strict rendering without surprises</p>', html)
    self.assertLess(
      html.index('<svg class="mark"'),
      html.index('<h1 class="blog-heading">strict templates</h1>'),
    )
    meta_start = html.index('<p class="blog-meta">')
    metadata = html[meta_start : html.index("</p>", meta_start)]
    self.assertIn(
      '<span class="blog-updated">updated '
      '<time datetime="2026-08-25">25 aug 2026</time></span>',
      metadata,
    )
    self.assertIn('<nav class="rail rail--article" aria-label="contents">', html)
    self.assertNotIn("rail__fold", html)
    self.assertIn(
      '<article class="blog-article"><p id="trusted">rendered <code>markdown</code>.</p></article>',
      html,
    )
    self.assertIn('<nav class="blog-tags" aria-label="Article tags">', html)
    self.assertIn('href="/tags/systems/">systems</a>', html)
    self.assertIn('href="/tags/inference/">inference</a>', html)
    self.assertIn('href="/blogs/">all writings</a>', html)
    self.assertIn('href="#main-content">top</a>', html)
    self.assertRegex(html, r"© \d{4} sarthak tomar\. built by hand\.")

  def test_blog_rail_lists_second_and_third_level_headings(self) -> None:
    article = page(
      title="sectioned",
      route="/blogs/sectioned/",
      template="blog.html",
      body=rendered(
        "<p>x</p>",
        headings=(
          (1, "title", "title"),
          (2, "first", "first"),
          (3, "a sub", "a-sub"),
          (2, "second", "second"),
          (4, "deep", "deep"),
        ),
      ),
    )

    html = self.render(article, namespace(config=config()))

    self.assertIn('<details class="rail__fold" open>', html)
    self.assertIn('<summary class="rail__summary">contents</summary>', html)
    self.assertIn('<li class="rail__item"><a href="#first">first</a></li>', html)
    self.assertIn(
      '<li class="rail__item rail__item--sub"><a href="#a-sub">a sub</a></li>', html
    )
    self.assertIn('<li class="rail__item"><a href="#second">second</a></li>', html)
    self.assertNotIn('href="#title"', html)
    self.assertNotIn('href="#deep"', html)
    self.assertIn('<a class="rail__back" href="/blogs/">&lt;- writing</a>', html)

  def test_blog_rail_skips_the_fold_for_a_single_heading(self) -> None:
    article = page(
      title="short",
      route="/blogs/short/",
      template="blog.html",
      body=rendered("<p>x</p>", headings=((2, "only", "only"),)),
    )

    html = self.render(article, namespace(config=config()))

    self.assertNotIn("rail__fold", html)
    self.assertNotIn('href="#only"', html)
    self.assertIn('<a class="rail__back" href="/blogs/">&lt;- writing</a>', html)


class TestDraftTemplates(TemplateRenderingTestCase):
  def test_draft_articles_carry_a_notice_and_ledger_rows_a_badge(self) -> None:
    draft = page(
      title="unfinished",
      route="/blogs/unfinished/",
      template="blog.html",
      draft=True,
    )
    finished = page(title="done", route="/blogs/done/", template="blog.html")
    home = page(
      title="home",
      route="/",
      template="home.html",
      body=rendered("<p>hi</p>"),
    )

    draft_html = self.render(draft, namespace(config=config()))
    finished_html = self.render(finished, namespace(config=config()))
    home_html = self.render(
      home,
      namespace(
        config=config(),
        index=namespace(posts=(draft, finished), recent_posts=(draft, finished)),
      ),
    )

    self.assertIn(
      '<p class="blog-draft" role="note"><strong>draft.</strong>', draft_html
    )
    self.assertNotIn("blog-draft", finished_html)
    self.assertIn(
      'href="/blogs/unfinished/">unfinished <span class="writing-row__draft">draft</span></a>',
      home_html,
    )
    self.assertIn('href="/blogs/done/">done</a>', home_html)


class TestTagsTemplate(TemplateRenderingTestCase):
  def test_tags_archive_does_not_require_pagination(self) -> None:
    tagged = page(
      title="tagged post",
      route="/blogs/tagged/",
      template="blog.html",
    )
    archive = page(
      title="systems",
      route="/tags/systems/",
      template="tags.html",
      description="writing tagged systems",
    )
    tag = namespace(name="systems", items=(tagged,))

    html = self.render(archive, namespace(config=config(), tag=tag))

    self.assertIn('<h1 class="tags-heading">systems</h1>', html)
    self.assertIn('href="/blogs/tagged/">tagged post</a>', html)
    self.assertNotIn('aria-label="Pagination"', html)

  def test_tags_archive_renders_items_and_pagination(self) -> None:
    tagged = page(
      title="tagged post",
      route="/blogs/tagged/",
      template="blog.html",
      published=date(2026, 8, 24),
    )
    archive = page(
      title="systems",
      route="/tags/systems/page/2/",
      template="tags.html",
      description="writing tagged systems",
    )
    context = pagination_context(
      (tagged,),
      previous_url="/tags/systems/",
      next_url="/tags/systems/page/3/",
      tag="systems",
    )

    html = self.render(archive, context)

    self.assertIn('<body class="tags-page">', html)
    self.assertIn('<h1 class="tags-heading">systems</h1>', html)
    self.assertIn('href="/blogs/tagged/">tagged post</a>', html)
    self.assertIn('<span class="writing-row__date">24 aug 2026</span>', html)
    self.assertIn('rel="prev" href="/tags/systems/">previous</a>', html)
    self.assertIn("<span>page 2 of 3</span>", html)
    self.assertIn('rel="next" href="/tags/systems/page/3/">next</a>', html)


if __name__ == "__main__":
  unittest.main()


class TestNotFoundTemplate(TemplateRenderingTestCase):
  def test_not_found_renders_figlet_code_heading_and_links(self) -> None:
    not_found = page(
      title="nothing here",
      route="/404.html",
      template="404.html",
      noindex=True,
      body=rendered("<p>wrong turn.</p>"),
    )

    html = self.render(not_found, namespace(config=config()))

    self.assertIn('<pre class="not-found-figlet" aria-hidden="true">', html)
    self.assertIn('<p class="not-found-code">404</p>', html)
    self.assertIn('<h1 class="not-found-heading" id="not-found-title">', html)
    self.assertIn('href="/">go home</a>', html)
    self.assertIn('href="/blogs/">all writings</a>', html)


class TestAboutTemplate(TemplateRenderingTestCase):
  def test_about_renders_prose_and_the_elsewhere_links(self) -> None:
    about = page(
      title="about me",
      route="/about/",
      template="about.html",
      body=rendered("<p>hey.</p>"),
    )

    html = self.render(about, namespace(config=config()))

    self.assertIn('<h1 class="about-heading">about me</h1>', html)
    self.assertIn('<article class="about-article"><p>hey.</p></article>', html)
    self.assertIn('<aside class="rail rail--home" aria-label="elsewhere">', html)
    self.assertIn('<pre class="portrait" role="img"', html)
    self.assertNotIn("about-elsewhere", html)
    self.assertIn('href="https://github.com/saarthak314" rel="me">github</a>', html)
    self.assertIn('href="mailto:hey@sarrthak.com">email</a>', html)
    self.assertIn('<a href="/about/" aria-current="page">about</a>', html)
