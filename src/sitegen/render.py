import hashlib
from collections.abc import Mapping
from datetime import date
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit

from jinja2 import Environment
from markupsafe import Markup

from sitegen.city import city_layers

SITE_TITLE = "sλrthak"


class TemplateRenderer:
  def __init__(self, environment_or_config: Any) -> None:
    if isinstance(environment_or_config, Environment):
      self.environment = environment_or_config
      self.config = None
    else:
      from sitegen.templates import create_environment

      self.config = environment_or_config
      self.environment = create_environment(environment_or_config.template_dir)

  def render_page(self, page: Any, context: Any) -> str:
    values = _context_values(context)
    if _is_content_index(context):
      values["index"] = context
    if self.config is not None:
      values.setdefault("config", self.config)
    _normalize_tag(values)
    footer_phrase = (
      "built by hand." if page.template == "blog.html" else "built with love."
    )
    values.update(
      page=page,
      city=city_layers(),
      content=Markup(page.rendered.html),
      current_year=date.today().year,
      document_title=_document_title(page),
      meta_description=_meta_description(page),
      og_type="article" if page.template == "blog.html" else "website",
      body_class=_body_class(page.template),
      footer_phrase=footer_phrase,
      footer_line=getattr(page, "copyright", None)
      or f"© {date.today().year} sarthak tomar. {footer_phrase}",
      now_origin=_origin(getattr(page, "now_playing", None)),
      structured_data=_structured_data(page, values.get("config")),
    )
    output = self.environment.get_template(page.template).render(**values)
    return "\n".join(line.rstrip() for line in output.splitlines()) + "\n"

  def render_tag(self, tag: Any, index: Any) -> str:
    items = tuple(tag.items)
    published = items[0].date if items else date.today()
    rendered = SimpleNamespace(
      html="",
      reading_time="1 min read",
      has_math=False,
      has_code=False,
      headings=(),
    )
    page = SimpleNamespace(
      title=tag.name,
      date=published,
      updated=None,
      route=tag.route,
      canonical_url=f"{self._site_url()}{tag.route}",
      description=f"writing tagged {tag.name}",
      social_image_url=_absolute_url(self._site_url(), self._config().social_image),
      social_image_width=1200,
      social_image_height=630,
      social_image_type="image/jpeg",
      tags=(),
      rendered=rendered,
      template="tags.html",
      noindex=False,
    )
    return self.render_page(
      page,
      {
        "config": self._config(),
        "index": index,
        "tag": tag,
      },
    )

  def template_digest(self, template_name: str) -> str:
    digest = hashlib.sha256()
    names = sorted(set([template_name, *self.environment.list_templates()]))
    for name in names:
      source, _, _ = self.environment.loader.get_source(self.environment, name)
      digest.update(name.encode("utf-8"))
      digest.update(b"\0")
      digest.update(source.encode("utf-8"))
      digest.update(b"\0")
    return digest.hexdigest()

  def render_redirect(self, alias: str, page: Any) -> str:
    output = self.environment.get_template("redirect.html").render(
      alias=alias,
      page=page,
    )
    return "\n".join(line.rstrip() for line in output.splitlines()) + "\n"

  def _config(self) -> Any:
    if self.config is None:
      raise ValueError("tag rendering requires a site configuration")
    return self.config

  def _site_url(self) -> str:
    return self._config().site_url.rstrip("/")


def _context_values(context: Any) -> dict[str, Any]:
  if isinstance(context, Mapping):
    return dict(context)
  if hasattr(context, "__dict__"):
    return dict(vars(context))
  fields = getattr(context, "__dataclass_fields__", {})
  return {name: getattr(context, name) for name in fields}


def _is_content_index(context: Any) -> bool:
  return all(hasattr(context, name) for name in ("posts", "tags"))


def _normalize_tag(values: dict[str, Any]) -> None:
  tag = values.get("tag")
  if tag is None or isinstance(tag, str):
    return
  values["tag"] = getattr(tag, "name", tag)
  values.setdefault("items", getattr(tag, "items", ()))


def _document_title(page: Any) -> str:
  """A post's tab reads its own title alone; every other page reads the name."""
  if page.template == "blog.html":
    return page.title
  return SITE_TITLE


def _meta_description(page: Any) -> str:
  return page.description


def _origin(url: Any) -> str:
  """Scheme and host of a URL, for a preconnect hint."""
  if not url:
    return ""
  parts = urlsplit(str(url))
  return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def _body_class(template_name: str) -> str:
  return {
    "home.html": "home-page",
    "blog.html": "blog-page",
    "tags.html": "tags-page",
    "404.html": "not-found-page",
  }[template_name]


def _structured_data(page: Any, config: Any) -> dict[str, Any]:
  author_name = getattr(config, "author_name", "Sarthak Tomar")
  site_url = getattr(config, "site_url", "https://sarrthak.com").rstrip("/")
  if page.template == "blog.html":
    payload = {
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "headline": page.title,
      "description": page.description,
      "image": page.social_image_url,
      "datePublished": page.date.isoformat(),
      "dateModified": (page.updated or page.date).isoformat(),
      "mainEntityOfPage": page.canonical_url,
      "author": {
        "@type": "Person",
        "name": author_name,
        "url": site_url,
      },
    }
  elif page.route == "/":
    payload = {
      "@context": "https://schema.org",
      "@type": "Person",
      "name": author_name,
      "url": site_url,
      "sameAs": [
        "https://github.com/saarthak314",
        "https://x.com/sarthak2143",
        "https://linkedin.com/in/sarthaktomar2143",
      ],
    }
  else:
    payload = {
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": page.title,
      "description": page.description,
      "url": page.canonical_url,
    }
  return payload


def _absolute_url(site_url: str, value: str) -> str:
  if value.startswith(("https://", "http://")):
    return value
  return f"{site_url}/{value.lstrip('/')}"
