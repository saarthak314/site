import hashlib
import json
import shutil
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sitegen.config import SiteConfig
from sitegen.content import ContentRepository
from sitegen.feeds import render_rss, render_sitemap
from sitegen.manifest import BuildManifest, digest_paths
from sitegen.models import ContentError

RENDER_PIPELINE_VERSION = 3


class BuildError(RuntimeError):
  """Raised when a site build cannot be safely published."""


@dataclass(frozen=True)
class BuildOptions:
  include_drafts: bool = True
  incremental: bool = True


@dataclass(frozen=True)
class BuildReport:
  rendered: int
  reused: int
  output_dir: Path


class SiteBuilder:
  def __init__(
    self,
    project_root: Path,
    *,
    markdown_renderer=None,
    template_renderer=None,
    validator=None,
  ) -> None:
    self.project_root = project_root.absolute()
    self._markdown_renderer = markdown_renderer
    self._template_renderer = template_renderer
    self._validator = validator

  def build(self, options: BuildOptions | None = None) -> BuildReport:
    options = options or BuildOptions()
    config = SiteConfig.load(self.project_root)
    markdown_renderer = self._markdown_renderer or self._default_markdown_renderer(
      config
    )
    template_renderer = self._template_renderer or self._default_template_renderer(
      config
    )
    validator = self._validator or self._default_validator()
    index = ContentRepository(config, markdown_renderer).discover(
      include_drafts=options.include_drafts
    )

    output_dir = config.output_dir
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
      tempfile.mkdtemp(
        prefix=f".{output_dir.name}.build-",
        dir=output_dir.parent,
      )
    )
    previous_manifest = (
      BuildManifest.load(output_dir)
      if options.incremental and output_dir.is_dir()
      else BuildManifest()
    )
    next_entries: dict[str, str] = {}
    rendered = 0
    reused = 0

    def emit(relative_path: Path, digest: str, producer: Callable[[], str]) -> None:
      nonlocal rendered, reused
      key = relative_path.as_posix()
      destination = staging_dir / relative_path
      previous = output_dir / relative_path
      destination.parent.mkdir(parents=True, exist_ok=True)
      if (
        options.incremental
        and previous_manifest.entries.get(key) == digest
        and previous.is_file()
      ):
        shutil.copy2(previous, destination)
        reused += 1
      else:
        destination.write_text(producer(), encoding="utf-8")
        rendered += 1
      next_entries[key] = digest

    try:
      if not config.static_dir.is_dir():
        raise ContentError(f"{config.static_dir}: static directory not found")
      shutil.copytree(config.static_dir, staging_dir, dirs_exist_ok=True)
      config_digest = _config_digest(config, options)

      archive_page = index.page_for_route("/blogs/")
      for page in index.pages:
        template_digest = self._template_digest(
          template_renderer, config, page.template
        )
        context_digest = index.digest if page.route in {"/", "/blogs/"} else ""
        page_digest = _hash_values(
          config_digest,
          template_digest,
          context_digest,
          page.source_path.read_bytes(),
          page.rendered.html,
        )
        if page.route == "/blogs/":
          pagination = index.pagination[0]
          emit(
            page.output_path,
            page_digest,
            lambda page=page, pagination=pagination: template_renderer.render_archive(
              page, pagination, index
            ),
          )
        else:
          emit(
            page.output_path,
            page_digest,
            lambda page=page: template_renderer.render_page(page, index),
          )

        for alias in page.aliases:
          alias_digest = _hash_values(
            config_digest,
            self._template_digest(template_renderer, config, "redirect.html"),
            alias,
            page.canonical_url,
          )
          emit(
            _route_to_output_path(alias),
            alias_digest,
            lambda alias=alias, page=page: template_renderer.render_redirect(
              alias, page
            ),
          )

      if archive_page is None:
        raise BuildError("content index is missing the /blogs/ archive page")
      archive_template_digest = self._template_digest(
        template_renderer, config, archive_page.template
      )
      for pagination in index.pagination[1:]:
        relative_path = _route_to_output_path(pagination.route)
        digest = _hash_values(
          config_digest,
          archive_template_digest,
          index.digest,
          pagination.route,
        )
        emit(
          relative_path,
          digest,
          lambda pagination=pagination: template_renderer.render_archive(
            archive_page, pagination, index
          ),
        )

      tag_template_digest = self._template_digest(
        template_renderer, config, "tags.html"
      )
      for tag in index.tags:
        digest = _hash_values(
          config_digest,
          tag_template_digest,
          index.digest,
          tag.route,
        )
        emit(
          _route_to_output_path(tag.route),
          digest,
          lambda tag=tag: template_renderer.render_tag(tag, index),
        )

      feed_digest = _hash_values(config_digest, index.digest, "rss-v2")
      emit(
        Path("feed.xml"),
        feed_digest,
        lambda: render_rss(index, config.site_url),
      )
      sitemap_digest = _hash_values(config_digest, index.digest, "sitemap-v2")
      emit(
        Path("sitemap.xml"),
        sitemap_digest,
        lambda: render_sitemap(index, config.site_url),
      )

      BuildManifest(entries=next_entries).write(staging_dir)
      issues = validator.validate(staging_dir)
      if issues:
        details = "\n".join(issue.format() for issue in issues)
        raise BuildError(f"site validation failed:\n{details}")

      self._publish(staging_dir, output_dir)
      return BuildReport(rendered=rendered, reused=reused, output_dir=output_dir)
    except (ContentError, BuildError):
      raise
    except Exception as exc:
      raise BuildError(f"site build failed: {exc}") from exc
    finally:
      if staging_dir.exists():
        shutil.rmtree(staging_dir)

  def _publish(self, staging_dir: Path, output_dir: Path) -> None:
    backup_dir = output_dir.with_name(f".{output_dir.name}.backup-{uuid.uuid4().hex}")
    moved_existing = False
    try:
      if output_dir.exists():
        output_dir.rename(backup_dir)
        moved_existing = True
      staging_dir.rename(output_dir)
    except Exception:
      if output_dir.exists() and moved_existing:
        shutil.rmtree(output_dir)
      if backup_dir.exists():
        backup_dir.rename(output_dir)
      raise
    if backup_dir.exists():
      shutil.rmtree(backup_dir)

  def _template_digest(
    self, template_renderer, config: SiteConfig, template_name: str
  ) -> str:
    digest_method = getattr(template_renderer, "template_digest", None)
    if callable(digest_method):
      return str(digest_method(template_name))
    paths = [config.template_dir / template_name]
    base = config.template_dir / "base.html"
    if base.exists():
      paths.append(base)
    partials = config.template_dir / "partials"
    if partials.is_dir():
      paths.extend(path for path in partials.rglob("*") if path.is_file())
    return digest_paths(paths, config.template_dir)

  def _default_markdown_renderer(self, config: SiteConfig):
    from sitegen.markdown import MarkdownRenderer

    return MarkdownRenderer(static_dir=config.static_dir)

  def _default_template_renderer(self, config: SiteConfig):
    from sitegen.templates import TemplateRenderer

    return TemplateRenderer(config)

  def _default_validator(self):
    from sitegen.validate import SiteValidator

    return SiteValidator()


def _route_to_output_path(route: str) -> Path:
  if route == "/":
    return Path("index.html")
  if route.endswith(".html"):
    return Path(route.strip("/"))
  return Path(route.strip("/")) / "index.html"


def _config_digest(config: SiteConfig, options: BuildOptions) -> str:
  payload = {
    "render_pipeline_version": RENDER_PIPELINE_VERSION,
    "site_url": config.site_url,
    "email": config.email,
    "social_image": config.social_image,
    "author_name": config.author_name,
    "twitter_handle": config.twitter_handle,
    "posts_per_page": config.posts_per_page,
    "include_drafts": options.include_drafts,
    "year": date.today().year,
  }
  return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _hash_values(*values) -> str:
  digest = hashlib.sha256()
  for value in values:
    if isinstance(value, bytes):
      digest.update(value)
    else:
      digest.update(str(value).encode("utf-8"))
    digest.update(b"\0")
  return digest.hexdigest()
