import hashlib
import json
import mimetypes
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sitegen.config import SiteConfig
from sitegen.frontmatter import parse_document
from sitegen.markdown import image_dimensions
from sitegen.models import ContentError, Page


class MarkdownRendererProtocol(Protocol):
  def render(self, markdown: str): ...


@dataclass(frozen=True)
class TagPage:
  name: str
  slug: str
  route: str
  items: tuple[Page, ...]


@dataclass(frozen=True)
class ContentIndex:
  pages: tuple[Page, ...]
  posts: tuple[Page, ...]
  tags: tuple[TagPage, ...]
  digest: str

  def page_for_route(self, route: str) -> Page | None:
    return next((page for page in self.pages if page.route == route), None)


class ContentRepository:
  def __init__(self, config: SiteConfig, renderer: MarkdownRendererProtocol) -> None:
    self.config = config
    self.renderer = renderer

  def discover(self, include_drafts: bool = True) -> ContentIndex:
    content_dir = self.config.content_dir
    home_path = content_dir / "_index.md"
    blogs_dir = content_dir / "blogs"
    if not home_path.is_file():
      raise ContentError(f"{home_path}: required content file not found")

    # the home page lists every post; there is no separate archive page
    pages: list[Page] = [
      self._create_page(home_path, "/", "home.html", is_post=False),
    ]
    not_found_path = content_dir / "404.md"
    if not_found_path.is_file():
      pages.append(
        self._create_page(
          not_found_path,
          "/404.html",
          "404.html",
          is_post=False,
        )
      )

    children = (
      sorted(blogs_dir.iterdir(), key=lambda path: path.name)
      if blogs_dir.is_dir()
      else []
    )
    for child in children:
      if not child.is_dir():
        continue
      source_path = child / "index.md"
      if not source_path.is_file():
        raise ContentError(f"{source_path}: blog directory is missing index.md")
      page = self._create_page(
        source_path,
        None,
        "blog.html",
        is_post=True,
        include_drafts=include_drafts,
      )
      if page is None:
        continue
      pages.append(page)

    self._ensure_unique_routes(pages)
    posts = tuple(
      sorted(
        (page for page in pages if page.is_post),
        key=lambda page: (page.date, page.title.casefold()),
        reverse=True,
      )
    )
    tags = self._build_tags(posts)
    digest = self._digest(pages, tags, include_drafts)
    return ContentIndex(
      pages=tuple(pages),
      posts=posts,
      tags=tags,
      digest=digest,
    )

  def _create_page(
    self,
    source_path: Path,
    fixed_route: str | None,
    default_template: str,
    *,
    is_post: bool,
    include_drafts: bool = True,
  ) -> Page | None:
    document = parse_document(source_path)
    metadata = document.metadata
    if metadata.draft and not include_drafts:
      return None
    rendered = self.renderer.render(document.body)
    directory_slug = source_path.parent.name
    slug = metadata.slug or directory_slug
    route = fixed_route
    if route is None:
      route = metadata.permalink or f"/blogs/{slug}/"
    output_path = _route_to_output_path(route)
    social_image = metadata.social_image or self.config.social_image
    social_image_url = _absolute_url(self.config.site_url, social_image)
    social_image_path = self.config.static_dir / social_image.lstrip("/")
    social_dimensions = (
      image_dimensions(social_image_path) if social_image_path.is_file() else None
    )
    social_image_width, social_image_height = social_dimensions or (1200, 630)
    social_image_type = mimetypes.guess_type(social_image_path.name)[0] or "image/jpeg"
    return Page(
      source_path=source_path,
      output_path=output_path,
      route=route,
      canonical_url=f"{self.config.site_url}{route}",
      title=metadata.title,
      date=metadata.date,
      updated=metadata.updated,
      draft=metadata.draft,
      slug=slug,
      permalink=metadata.permalink,
      description=metadata.description or rendered.description,
      social_image_url=social_image_url,
      social_image_width=social_image_width,
      social_image_height=social_image_height,
      social_image_type=social_image_type,
      tags=metadata.tags,
      template=metadata.template or default_template,
      markdown=document.body,
      rendered=rendered,
      is_post=is_post,
      aliases=metadata.aliases,
      noindex=metadata.noindex or metadata.draft,
      experience=metadata.experience,
      projects=metadata.projects,
      copyright=metadata.copyright,
      now_playing=metadata.now_playing,
    )

  def _ensure_unique_routes(self, pages: list[Page]) -> None:
    sources_by_route: dict[str, Path] = {}
    for page in pages:
      for route in (page.route, *page.aliases):
        existing = sources_by_route.get(route)
        if existing:
          raise ContentError(
            f"{page.source_path}: duplicate route or alias {route}; "
            f"already used by {existing}"
          )
        sources_by_route[route] = page.source_path

  def _build_tags(self, posts: tuple[Page, ...]) -> tuple[TagPage, ...]:
    grouped: dict[str, tuple[str, list[Page]]] = {}
    for post in posts:
      for name in post.tags:
        slug = _slugify(name)
        if not slug:
          raise ContentError(f"{post.source_path}: tag {name!r} has no usable slug")
        if slug not in grouped:
          grouped[slug] = (name, [])
        grouped[slug][1].append(post)
    return tuple(
      TagPage(
        name=name,
        slug=slug,
        route=f"/tags/{slug}/",
        items=tuple(items),
      )
      for slug, (name, items) in sorted(grouped.items())
    )

  def _digest(
    self,
    pages: list[Page],
    tags: tuple[TagPage, ...],
    include_drafts: bool,
  ) -> str:
    payload = {
      "include_drafts": include_drafts,
      "pages": [
        {
          "route": page.route,
          "title": page.title,
          "date": page.date.isoformat(),
          "updated": page.updated.isoformat() if page.updated else None,
          "description": page.description,
          "image": page.social_image_url,
          "image_width": page.social_image_width,
          "image_height": page.social_image_height,
          "image_type": page.social_image_type,
          "tags": page.tags,
          "template": page.template,
          "aliases": page.aliases,
          "noindex": page.noindex,
          "copyright": page.copyright,
          "now_playing": page.now_playing,
          "experience": [
            {
              "role": item.role,
              "company": item.company,
              "company_url": item.company_url,
              "period": item.period,
              "highlights": item.highlights,
            }
            for item in page.experience
          ],
          "projects": [
            {
              "name": item.name,
              "url": item.url,
              "description": item.description,
              "tech": item.tech,
            }
            for item in page.projects
          ],
          "markdown": page.markdown,
        }
        for page in pages
      ],
      "tags": [tag.route for tag in tags],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _route_to_output_path(route: str) -> Path:
  if route == "/":
    return Path("index.html")
  if route.endswith(".html"):
    return Path(route.strip("/"))
  return Path(route.strip("/")) / "index.html"


def _absolute_url(site_url: str, value: str) -> str:
  if value.startswith(("https://", "http://")):
    return value
  return f"{site_url}/{value.lstrip('/')}"


def _slugify(value: str) -> str:
  normalized = unicodedata.normalize("NFKD", value)
  ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
  return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
