from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from sitegen.markdown import RenderedMarkdown


class ContentError(ValueError):
  """Raised when source content or configuration is invalid."""


@dataclass(frozen=True)
class ExperienceItem:
  role: str
  company: str | None
  company_url: str | None
  period: str
  highlights: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectItem:
  name: str
  url: str | None
  description: str
  tech: tuple[str, ...]


@dataclass(frozen=True)
class PageMetadata:
  title: str
  date: date
  updated: date | None = None
  draft: bool = False
  slug: str | None = None
  permalink: str | None = None
  description: str | None = None
  social_image: str | None = None
  tags: tuple[str, ...] = ()
  template: str | None = None
  aliases: tuple[str, ...] = ()
  noindex: bool = False
  experience: tuple[ExperienceItem, ...] = ()
  projects: tuple[ProjectItem, ...] = ()


@dataclass(frozen=True)
class ParsedDocument:
  metadata: PageMetadata
  body: str


@dataclass(frozen=True)
class Page:
  source_path: Path
  output_path: Path
  route: str
  canonical_url: str
  title: str
  date: date
  updated: date | None
  draft: bool
  slug: str
  permalink: str | None
  description: str
  social_image_url: str
  social_image_width: int
  social_image_height: int
  social_image_type: str
  tags: tuple[str, ...]
  template: str
  markdown: str
  rendered: "RenderedMarkdown"
  is_post: bool
  aliases: tuple[str, ...]
  noindex: bool
  experience: tuple[ExperienceItem, ...] = ()
  projects: tuple[ProjectItem, ...] = ()
